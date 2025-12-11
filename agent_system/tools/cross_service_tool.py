"""
Cross-Service Communication Tool for the Main Agent.

This tool enables the Main Agent to:
1. Discover available services from the proxy
2. Get analysis reports from specific services
3. Gather reports from multiple services for comprehensive analysis

The Main Agent can use these tools to leverage knowledge from other deployed
service clusters and produce comprehensive final reports that incorporate
cross-service context.
"""
import logging
import requests
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

logger = logging.getLogger(__name__)

# Configuration from environment
PROXY_URL = os.getenv("PROXY_URL", "http://localhost:8000")
REQUEST_TIMEOUT = int(os.getenv("CROSS_SERVICE_TIMEOUT", "60"))


def discover_services(capability: Optional[str] = None) -> str:
    """
    Discover available services registered with the proxy.
    
    This tool queries the proxy/dispatcher to get a list of all registered
    services. Use this to understand what services are available in the
    distributed system and their capabilities.
    
    Args:
        capability: Optional filter to only return services with a specific
                   capability (e.g., "payment", "order", "inventory").
                   If not provided, returns all healthy services.
    
    Returns:
        A formatted string describing available services including:
        - Service names
        - Service URLs
        - Capabilities
        - Health status
        
        If no services are found or proxy is unavailable, returns an
        appropriate message.
    
    Example:
        >>> discover_services()
        "Found 3 services: payment-service (payment, billing), 
         order-service (order, fulfillment), inventory-service (inventory)"
        
        >>> discover_services(capability="payment")
        "Found 1 service with capability 'payment': payment-service"
    """
    try:
        params = {}
        if capability:
            params["capability"] = capability
        
        response = requests.get(
            f"{PROXY_URL}/discover",
            params=params,
            timeout=10
        )
        
        if response.status_code != 200:
            return f"Failed to discover services: Proxy returned status {response.status_code}"
        
        data = response.json()
        services = data.get("services", [])
        
        if not services:
            if capability:
                return f"No services found with capability '{capability}'"
            return "No services currently registered with the proxy"
        
        # Format the response
        service_descriptions = []
        for svc in services:
            name = svc.get("name", "unknown")
            caps = ", ".join(svc.get("capabilities", []))
            status = svc.get("status", "unknown")
            url = svc.get("url", "")
            service_descriptions.append(
                f"- {name}: capabilities=[{caps}], status={status}, url={url}"
            )
        
        result = f"Found {len(services)} service(s)"
        if capability:
            result += f" with capability '{capability}'"
        result += ":\n" + "\n".join(service_descriptions)
        
        return result
        
    except requests.exceptions.ConnectionError:
        return "Failed to connect to proxy service. Proxy may be unavailable."
    except requests.exceptions.Timeout:
        return "Proxy request timed out. Try again later."
    except Exception as e:
        logger.error(f"Error discovering services: {e}")
        return f"Error discovering services: {str(e)}"


def get_service_report(service_name: str, error_context: str) -> str:
    """
    Get an analysis report from a specific service's agent.
    
    This tool discovers a service via the proxy, sends the error context
    to that service's Main Agent for analysis, and returns their report.
    The remote service will analyze the error from its perspective using
    its own Internal Knowledge Agent and local databases.
    
    Use this tool when you need context from a specific service about an
    error that may be related to or affected by that service.
    
    Args:
        service_name: The name of the service to query (e.g., "order-service",
                     "payment-service"). Must be a registered service.
        error_context: The error log or context to analyze. This will be
                      sent to the remote service for analysis.
    
    Returns:
        A formatted string containing:
        - The remote service's analysis report
        - Any relevant historical context from that service
        - Recommendations from that service's perspective
        
        If the service is unavailable, returns an error message.
    
    Example:
        >>> get_service_report("order-service", "Payment timeout error...")
        "[order-service report]
         Found 5 orders stuck in PENDING_PAYMENT state.
         Order #12345 waiting for payment since 10:00 AM.
         Recommendation: Check payment gateway connectivity."
    """
    try:
        # First, get service info from proxy
        svc_response = requests.get(
            f"{PROXY_URL}/services/{service_name}",
            timeout=10
        )
        
        if svc_response.status_code == 404:
            return f"Service '{service_name}' not found in proxy registry"
        
        if svc_response.status_code != 200:
            return f"Failed to get service info: status {svc_response.status_code}"
        
        service_info = svc_response.json()
        service_url = service_info.get("url")
        
        if not service_url:
            return f"Service '{service_name}' has no URL registered"
        
        # Check if service is healthy
        if service_info.get("status") != "healthy":
            return f"Service '{service_name}' is currently {service_info.get('status', 'unavailable')}"
        
        # Query the service's agent
        logger.info(f"Querying service {service_name} at {service_url}")
        
        query_response = requests.post(
            f"{service_url}/api/query",
            json={
                "query": f"Analyze this error from the perspective of {service_name}. "
                        f"Provide relevant context from your service's logs and knowledge base.\n\n"
                        f"Error context:\n{error_context}"
            },
            timeout=REQUEST_TIMEOUT
        )
        
        if query_response.status_code != 200:
            return f"Service '{service_name}' query failed: status {query_response.status_code}"
        
        result = query_response.json()
        reply = result.get("reply", "No response from service")
        
        # Format the response
        formatted = f"[Report from {service_name}]\n"
        formatted += f"Service: {service_name}\n"
        formatted += f"Capabilities: {', '.join(service_info.get('capabilities', []))}\n"
        formatted += "-" * 40 + "\n"
        formatted += reply
        
        return formatted
        
    except requests.exceptions.ConnectionError:
        return f"Failed to connect to service '{service_name}'. Service may be unavailable."
    except requests.exceptions.Timeout:
        return f"Request to service '{service_name}' timed out."
    except Exception as e:
        logger.error(f"Error querying service {service_name}: {e}")
        return f"Error querying service '{service_name}': {str(e)}"


def gather_cross_service_reports(
    error_context: str,
    service_names: Optional[str] = None
) -> str:
    """
    Gather analysis reports from multiple services in parallel.
    
    This tool discovers available services (or uses specified ones),
    queries each service for their analysis of the error, and aggregates
    all reports into a comprehensive cross-service context.
    
    Use this tool when you need a holistic view of an error's impact
    across multiple services in the distributed system.
    
    Args:
        error_context: The error log or context to analyze. This will be
                      sent to each service for analysis.
        service_names: Optional comma-separated list of service names to query
                      (e.g., "order-service,inventory-service").
                      If not provided, queries all available healthy services.
    
    Returns:
        A formatted string containing:
        - Summary of services queried
        - Individual reports from each service
        - Aggregated insights
        
        Reports are gathered in parallel for efficiency.
    
    Example:
        >>> gather_cross_service_reports("Database connection error...")
        "Cross-Service Analysis Report
         =============================
         Services queried: 3
         
         [order-service]: No related issues detected
         [payment-service]: 2 transactions pending
         [inventory-service]: Database read errors observed
         
         Summary: Error may be affecting payment and inventory services."
    """
    try:
        # Determine which services to query
        if service_names:
            target_services = [s.strip() for s in service_names.split(",") if s.strip()]
        else:
            # Discover all healthy services
            response = requests.get(
                f"{PROXY_URL}/services",
                params={"healthy_only": True},
                timeout=10
            )
            
            if response.status_code != 200:
                return "Failed to discover services from proxy"
            
            data = response.json()
            services = data.get("services", [])
            target_services = [s.get("name") for s in services if s.get("name")]
        
        if not target_services:
            return "No services available to query"
        
        # Query services in parallel
        reports = {}
        errors = {}
        
        with ThreadPoolExecutor(max_workers=min(5, len(target_services))) as executor:
            future_to_service = {
                executor.submit(get_service_report, svc, error_context): svc
                for svc in target_services
            }
            
            for future in as_completed(future_to_service):
                service = future_to_service[future]
                try:
                    report = future.result()
                    if "failed" in report.lower() or "error" in report.lower()[:50]:
                        errors[service] = report
                    else:
                        reports[service] = report
                except Exception as e:
                    errors[service] = str(e)
        
        # Format the aggregated response
        result_parts = []
        result_parts.append("=" * 60)
        result_parts.append("CROSS-SERVICE ANALYSIS REPORT")
        result_parts.append("=" * 60)
        result_parts.append(f"\nServices queried: {len(target_services)}")
        result_parts.append(f"Successful responses: {len(reports)}")
        result_parts.append(f"Failed queries: {len(errors)}")
        result_parts.append("\n" + "-" * 60)
        
        # Add successful reports
        if reports:
            result_parts.append("\n[SUCCESSFUL SERVICE REPORTS]\n")
            for service, report in reports.items():
                result_parts.append(report)
                result_parts.append("\n" + "-" * 40 + "\n")
        
        # Add error summary
        if errors:
            result_parts.append("\n[SERVICES WITH ERRORS]\n")
            for service, error in errors.items():
                result_parts.append(f"- {service}: {error[:100]}...")
        
        result_parts.append("\n" + "=" * 60)
        
        return "\n".join(result_parts)
        
    except Exception as e:
        logger.error(f"Error gathering cross-service reports: {e}")
        return f"Error gathering cross-service reports: {str(e)}"

