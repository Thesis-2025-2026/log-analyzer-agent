from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import logging
import atexit

from agent_system.agents.main_agent import analyze_log_with_main_agent
from agent_system.core.storage import list_reports, get_report, insert_report
from agent_system.core.tracing import (
    emit_simple_event,
    init_trace,
    new_trace_id,
    reset_trace_context,
    set_trace_context,
    trace_tool_bound,
)
from agent_system.tools.log_parser import summarize_log
from agent_system.tools.report_title_tool import generate_report_title
from agent_api.config import service_config
from agent_api.service_client import proxy_client
from agent_api.health_monitor import (
    health_monitor,
    register_with_proxy,
    unregister_from_proxy
)

logger = logging.getLogger(__name__)

# Track if we've registered
_registered = False


def create_app() -> Flask:
    # Serve the static frontend from ../web (index.html, assets, etc.)
    app = Flask(__name__, static_folder="../web", static_url_path="")
    # Enable permissive CORS for simple local development
    CORS(app)
    
    # Register with proxy on first request
    @app.before_request
    def ensure_registered():
        global _registered
        if not _registered and proxy_client.is_configured:
            if register_with_proxy(max_retries=3):
                health_monitor.start_threaded()
                _registered = True
    
    # Unregister on shutdown
    def shutdown_handler():
        logger.info("Shutting down, unregistering from proxy...")
        health_monitor.stop()
        unregister_from_proxy()
    
    atexit.register(shutdown_handler)

    @app.get("/")
    def index():
        return app.send_static_file("index.html")

    @app.get("/reports")
    def reports_page():
        # Single-page app; routing handled client-side.
        return app.send_static_file("index.html")

    @app.get("/report/<rid>")
    def report_page(rid: str):
        # Single-page app; routing handled client-side.
        return app.send_static_file("index.html")

    @app.get("/health")
    def health():
        return jsonify({
            "status": "ok",
            "service_name": service_config.SERVICE_NAME,
            "capabilities": service_config.capabilities,
            "proxy_configured": proxy_client.is_configured,
        }), 200
    
    @app.get("/api/service-info")
    def service_info():
        """Get information about this service."""
        return jsonify({
            "name": service_config.SERVICE_NAME,
            "url": service_config.SERVICE_URL,
            "version": service_config.SERVICE_VERSION,
            "description": service_config.SERVICE_DESCRIPTION,
            "capabilities": service_config.capabilities,
            "proxy_url": service_config.PROXY_URL,
            "proxy_enabled": proxy_client.is_configured,
        }), 200
    
    @app.get("/api/discover-services")
    def discover_services():
        """Discover other services via the proxy."""
        capability = request.args.get("capability")
        services = proxy_client.discover_services(capability=capability)
        return jsonify({
            "services": services,
            "count": len(services),
            "filter": capability,
        }), 200
    
    @app.post("/api/query-service/<service_name>")
    def query_remote_service(service_name: str):
        """Query another service's agent for analysis."""
        data = request.get_json(silent=True) or {}
        query = data.get("query") or data.get("text") or data.get("log")
        trace_id = data.get("trace_id")
        parent_event_id = data.get("parent_event_id")
        visited_services = data.get("visited_services")
        persist_report = data.get("persist_report")
        
        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Missing 'query' in JSON body"}), 400
        
        start = time.time()
        
        try:
            result = proxy_client.query_service(
                service_name,
                query,
                trace_id=trace_id if isinstance(trace_id, str) else None,
                parent_event_id=int(parent_event_id) if isinstance(parent_event_id, int) or (isinstance(parent_event_id, str) and parent_event_id.isdigit()) else None,
                visited_services=visited_services if isinstance(visited_services, list) else None,
                persist_report=persist_report if isinstance(persist_report, bool) else None,
            )
            duration_ms = int((time.time() - start) * 1000)
            
            if result:
                return jsonify({
                    "success": True,
                    "service": service_name,
                    "result": result,
                    "duration_ms": duration_ms,
                }), 200
            else:
                return jsonify({
                    "success": False,
                    "error": f"Failed to query service '{service_name}'",
                }), 502
        except Exception as e:
            return jsonify({
                "error": "Failed to query remote service",
                "details": str(e),
            }), 500

    @app.post("/api/query")
    def api_query():
        data = request.get_json(silent=True) or {}
        query = data.get("query") or data.get("text") or data.get("log")
        visited_services = data.get("visited_services")
        incoming_trace_id = data.get("trace_id")
        incoming_parent_event_id = data.get("parent_event_id")
        persist_report = data.get("persist_report")
        if persist_report is None:
            persist_report = True
        if not isinstance(visited_services, list):
            visited_services = []

        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Missing 'query' in JSON body"}), 400

        start = time.time()
        report_id = None

        try:
            trace_id = incoming_trace_id if isinstance(incoming_trace_id, str) and incoming_trace_id.strip() else new_trace_id()
            parent_event_id = None
            if isinstance(incoming_parent_event_id, int):
                parent_event_id = incoming_parent_event_id
            elif isinstance(incoming_parent_event_id, str) and incoming_parent_event_id.isdigit():
                parent_event_id = int(incoming_parent_event_id)

            tokens1 = set_trace_context(
                trace_id,
                parent_event_id=parent_event_id,
                service_name=service_config.SERVICE_NAME,
                agent_name=None,
            )
            init_trace(trace_id, root_service=service_config.SERVICE_NAME)
            root_event_id = emit_simple_event(event_type="run", agent_name="main_agent_workflow")
            tokens2 = None
            if root_event_id is not None:
                # Make all subsequent events children of this run node.
                tokens2 = set_trace_context(
                    trace_id,
                    parent_event_id=root_event_id,
                    service_name=service_config.SERVICE_NAME,
                    agent_name=None,
                )

            # Use the new Main Agent for log analysis
            reply = analyze_log_with_main_agent(
                query,
                visited_services=visited_services,
            )
            duration_ms = int((time.time() - start) * 1000)
            logger.info(f"we got reply {reply}")
            # Persist report to the service-specific database
            try:
                if persist_report:
                    title = trace_tool_bound(
                        generate_report_title,
                        trace_id=trace_id,
                        parent_event_id=root_event_id,
                        service_name=service_config.SERVICE_NAME,
                        agent_name="Main Agent",
                        tool_name="generate_report_title",
                    )(query)
                    meta = summarize_log(query)
                    level = str(meta.get("level", "unknown"))
                    # Store the current service name (stable) instead of trying to infer it from the log payload.
                    service = service_config.SERVICE_NAME
                    row = insert_report(level=level, service=service, title=title, content=reply, raw_log=query, trace_id=trace_id)
                    if isinstance(row, dict) and row.get("id") is not None:
                        report_id = int(row["id"])
            except Exception as db_err:
                print("error", db_err)
                logger.warning("Failed to store report: %s", db_err)

            return jsonify({
                "reply": reply,
                "agent": "main_agent",
                "duration_ms": duration_ms,
                "trace_id": trace_id,
                "report_id": report_id,
            }), 200
        except Exception as e:
            return jsonify({
                "error": "Failed to process query",
                "details": str(e),
            }), 500
        finally:
            try:
                if tokens2 is not None:
                    reset_trace_context(tokens2)
                reset_trace_context(tokens1)
            except Exception:
                pass

    @app.get("/api/reports")
    def api_list_reports():
        try:
            # pagination params
            try:
                limit = int(request.args.get("limit", "50"))
                offset = int(request.args.get("offset", "0"))
            except ValueError:
                limit, offset = 50, 0
            items = list_reports(limit=limit, offset=offset)
            return jsonify({"items": items, "limit": limit, "offset": offset}), 200
        except Exception as e:
            return jsonify({"error": "Failed to fetch reports", "details": str(e)}), 500

    @app.get("/api/reports/<rid>")
    def api_get_report(rid: str):
        try:
            try:
                rid_int = int(rid)
            except ValueError:
                return jsonify({"error": "Invalid report id"}), 400
            data = get_report(rid_int)
            if not data:
                return jsonify({"error": "Report not found"}), 404
            return jsonify(data), 200
        except Exception as e:
            return jsonify({"error": "Failed to fetch report", "details": str(e)}), 500

    @app.get("/api/reports/<rid>/events")
    def api_get_report_events(rid: str):
        """
        Fetch distributed trace events for the selected report.
        Proxies the call to the proxy/dispatcher service so the web UI
        can stay same-origin with the agent API.
        """
        try:
            try:
                rid_int = int(rid)
            except ValueError:
                return jsonify({"error": "Invalid report id"}), 400

            data = get_report(rid_int)
            if not data:
                return jsonify({"error": "Report not found"}), 404

            trace_id = data.get("trace_id")
            if not trace_id:
                return jsonify({"trace_id": None, "trace": None, "entries": []}), 200

            if not proxy_client.is_configured:
                return jsonify({"error": "Proxy not configured", "trace_id": trace_id}), 503

            import requests

            resp = requests.get(f"{service_config.PROXY_URL}/traces/{trace_id}", timeout=5)
            if resp.status_code != 200:
                return jsonify({"error": "Failed to fetch trace from proxy", "trace_id": trace_id}), 502
            payload = resp.json()
            payload["trace_id"] = trace_id
            return jsonify(payload), 200
        except Exception as e:
            return jsonify({"error": "Failed to fetch trace", "details": str(e)}), 500

    @app.get("/api/traces/agent-calls/<int:agent_call_id>")
    def api_get_agent_call(agent_call_id: int):
        if not proxy_client.is_configured:
            return jsonify({"error": "Proxy not configured"}), 503
        import requests
        resp = requests.get(f"{service_config.PROXY_URL}/traces/agent-calls/{agent_call_id}", timeout=5)
        return (resp.text, resp.status_code, {"Content-Type": "application/json"})

    @app.get("/api/traces/tool-calls/<int:tool_call_id>")
    def api_get_tool_call(tool_call_id: int):
        if not proxy_client.is_configured:
            return jsonify({"error": "Proxy not configured"}), 503
        import requests
        resp = requests.get(f"{service_config.PROXY_URL}/traces/tool-calls/{tool_call_id}", timeout=5)
        return (resp.text, resp.status_code, {"Content-Type": "application/json"})

    @app.get("/api/traces/http-calls/<int:http_call_id>")
    def api_get_http_call(http_call_id: int):
        if not proxy_client.is_configured:
            return jsonify({"error": "Proxy not configured"}), 503
        import requests
        resp = requests.get(f"{service_config.PROXY_URL}/traces/http-calls/{http_call_id}", timeout=5)
        return (resp.text, resp.status_code, {"Content-Type": "application/json"})

    return app
