from flask import Flask, request, jsonify
from flask_cors import CORS
import time
import logging
import atexit

from agent_system.agents.main_agent import analyze_log_with_main_agent
from agent_system.core.storage import list_reports, get_report, insert_report
from agent_system.tools.log_parser import summarize_log
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
        return app.send_static_file("reports.html")

    @app.get("/report/<rid>")
    def report_page(rid: str):
        # Serve a static detail page; the page fetches /api/reports/<rid> client-side
        return app.send_static_file("report.html")

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
        
        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Missing 'query' in JSON body"}), 400
        
        start = time.time()
        
        try:
            result = proxy_client.query_service(service_name, query)
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

        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Missing 'query' in JSON body"}), 400

        start = time.time()

        try:
            # Use the new Main Agent for log analysis
            reply = analyze_log_with_main_agent(query)
            duration_ms = int((time.time() - start) * 1000)
            logger.info(f"we got reply {reply}")
            # Persist report to the service-specific database
            try:
                meta = summarize_log(query)
                level = str(meta.get("level", "unknown"))
                service = str(meta.get("service", "unknown"))
                insert_report(level=level, service=service, content=reply, raw_log=query)
            except Exception as db_err:
                print("error", db_err)
                logger.warning("Failed to store report: %s", db_err)

            return jsonify({
                "reply": reply,
                "agent": "main_agent",
                "duration_ms": duration_ms,
            }), 200
        except Exception as e:
            return jsonify({
                "error": "Failed to process query",
                "details": str(e),
            }), 500

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

    return app
