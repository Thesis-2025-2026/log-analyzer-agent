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
import time
import requests
from typing import List, Dict, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import os
from contextvars import ContextVar
from agent_system.core.tracing import get_trace_id, get_parent_event_id, instrument_http_call
from agent_system.core.rate_limit import looks_rate_limited, compute_sleep_seconds

logger = logging.getLogger(__name__)

# Configuration from environment
PROXY_URL = os.getenv("PROXY_URL", "http://localhost:8000")
REQUEST_TIMEOUT = int(os.getenv("CROSS_SERVICE_TIMEOUT", "60"))
CURRENT_SERVICE_NAME = os.getenv("SERVICE_NAME", "").strip()

# Rate limit handling
RATE_LIMIT_MAX_RETRIES = int(os.getenv("CROSS_SERVICE_RATE_LIMIT_MAX_RETRIES", "3"))
RATE_LIMIT_MAX_SLEEP_SECONDS = float(os.getenv("CROSS_SERVICE_RATE_LIMIT_MAX_SLEEP_SECONDS", "30"))
RATE_LIMIT_BASE_SLEEP_SECONDS = float(os.getenv("CROSS_SERVICE_RATE_LIMIT_BASE_SLEEP_SECONDS", "1.0"))

# Track visited services per request to avoid cycles/self-calls
_visited_services_ctx: ContextVar[List[str]] = ContextVar(
    "_visited_services_ctx", default=[]
)


def set_visited_services(visited: Optional[List[str]] = None) -> None:
    """Set the current visited-services list for this request context."""
    safe_list = list(visited or [])
    _visited_services_ctx.set(safe_list)


def _get_visited_services() -> List[str]:
    try:
        return list(_visited_services_ctx.get())
    except Exception:
        return []


def _with_current_service(visited: List[str]) -> List[str]:
    if CURRENT_SERVICE_NAME and CURRENT_SERVICE_NAME not in visited:
        return visited + [CURRENT_SERVICE_NAME]
    return visited


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
        
        url = f"{PROXY_URL}/discover"
        response = instrument_http_call(
            target_service="proxy",
            method="GET",
            url=url,
            request_body={"params": params},
            call_fn=lambda: requests.get(url, params=params, timeout=10),
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
    visited = _get_visited_services()

    # Prevent self-calls and cycles
    if CURRENT_SERVICE_NAME and service_name == CURRENT_SERVICE_NAME:
        return f"Skipping '{service_name}' to avoid self-call recursion."
    if service_name in visited:
        return f"Skipping '{service_name}' because it was already visited in this request."

    try:
        # First, get service info from proxy
        svc_url = f"{PROXY_URL}/services/{service_name}"
        svc_response = instrument_http_call(
            target_service="proxy",
            method="GET",
            url=svc_url,
            request_body=None,
            call_fn=lambda: requests.get(svc_url, timeout=10),
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

        outgoing_visited = _with_current_service(visited)
        set_visited_services(outgoing_visited)
        
        trace_id = get_trace_id()
        parent_event_id = get_parent_event_id()
        query_body = {
            "query": f"Analyze this error from the perspective of {service_name}. "
                    f"Provide relevant context from your service's logs and knowledge base.\n\n"
                    f"Error context:\n{error_context}",
            "visited_services": outgoing_visited,
            "trace_id": trace_id,
            "parent_event_id": parent_event_id,
            "persist_report": False,
        }
        query_url = f"{service_url}/api/query"

        last_reply: Optional[str] = None
        for attempt in range(1, RATE_LIMIT_MAX_RETRIES + 1):
            query_response = instrument_http_call(
                target_service=service_name,
                method="POST",
                url=query_url,
                request_body=query_body,
                call_fn=lambda: requests.post(query_url, json=query_body, timeout=REQUEST_TIMEOUT),
            )

            if query_response.status_code != 200:
                return f"Service '{service_name}' query failed: status {query_response.status_code}"

            result = query_response.json()
            reply = result.get("reply", "No response from service")
            last_reply = reply

            # Remote services may return a 200 with an error report inside content.
            # If it looks like an OpenAI rate-limit, wait and retry to get a real report.
            if isinstance(reply, str) and looks_rate_limited(reply) and attempt < RATE_LIMIT_MAX_RETRIES:
                sleep_s = compute_sleep_seconds(
                    reply,
                    attempt=attempt,
                    base_seconds=RATE_LIMIT_BASE_SLEEP_SECONDS,
                    max_seconds=RATE_LIMIT_MAX_SLEEP_SECONDS,
                )
                logger.warning(
                    "Service '%s' appears rate-limited; sleeping %.2fs before retry (%d/%d).",
                    service_name,
                    sleep_s,
                    attempt,
                    RATE_LIMIT_MAX_RETRIES,
                )
                time.sleep(sleep_s)
                continue

            break
        
        # Format the response
        formatted = f"[Report from {service_name}]\n"
        formatted += f"Service: {service_name}\n"
        formatted += f"Capabilities: {', '.join(service_info.get('capabilities', []))}\n"
        formatted += "-" * 40 + "\n"
        formatted += last_reply or "No response from service"
        
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
        visited = _get_visited_services()

        # Determine which services to query
        if service_names:
            target_services = [s.strip() for s in service_names.split(",") if s.strip()]
        else:
            # Discover all healthy services
            url = f"{PROXY_URL}/services"
            response = instrument_http_call(
                target_service="proxy",
                method="GET",
                url=url,
                request_body={"params": {"healthy_only": True}},
                call_fn=lambda: requests.get(url, params={"healthy_only": True}, timeout=10),
            )
            
            if response.status_code != 200:
                return "Failed to discover services from proxy"
            
            data = response.json()
            services = data.get("services", [])
            target_services = [s.get("name") for s in services if s.get("name")]
        
        if not target_services:
            return "No services available to query"

        # Remove already-visited services to avoid ping-pong cycles
        if visited:
            target_services = [svc for svc in target_services if svc not in visited]
        if not target_services:
            return "All candidate services were already visited; skipping cross-service queries."
        
        # Query services in parallel
        reports = {}
        errors = {}

        visited_snapshot = _with_current_service(visited)

        with ThreadPoolExecutor(max_workers=min(5, len(target_services))) as executor:
            def _call_service(service: str) -> str:
                # Ensure visited context is available in worker threads
                set_visited_services(visited_snapshot)
                return get_service_report(service, error_context)

            future_to_service = {
                executor.submit(_call_service, svc): svc
                for svc in target_services
            }
            
            def _is_error_report(text: str) -> bool:
                if not isinstance(text, str):
                    return True
                lowered = text.strip().lower()
                if looks_rate_limited(text):
                    return True
                return (
                    lowered.startswith("error ")
                    or lowered.startswith("error:")
                    or lowered.startswith("failed ")
                    or " query failed:" in lowered
                    or "failed to connect" in lowered
                    or "timed out" in lowered
                )

            for future in as_completed(future_to_service):
                service = future_to_service[future]
                try:
                    report = future.result()
                    if _is_error_report(report):
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
