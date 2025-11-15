# Import settings first to configure logging before other imports
from agent_system.config import settings  # noqa: F401

from flask import Flask, request, jsonify
from flask_cors import CORS
import time

from agent_system.core.registry import get_agent
from agent_system.__main__ import analyze_log
from agent_system.core.storage import list_reports, get_report


def create_app() -> Flask:
    # Serve the static frontend from ../web (index.html, assets, etc.)
    app = Flask(__name__, static_folder="../web", static_url_path="")
    # Enable permissive CORS for simple local development
    CORS(app)

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
        return jsonify({"status": "ok"}), 200

    @app.post("/api/query")
    def api_query():
        data = request.get_json(silent=True) or {}
        query = data.get("query") or data.get("text") or data.get("log")
        agent_name = data.get("agent") or "workforce"

        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Missing 'query' in JSON body"}), 400

        if not isinstance(agent_name, str) or not agent_name.strip():
            agent_name = "log_analysis" #FIXME: this agent does not exist anymore

        start = time.time()
        try:
            agent = get_agent(agent_name)
        except Exception as e:
            return jsonify({
                "error": f"Unknown agent '{agent_name}'",
                "details": str(e),
            }), 400

        try:
            reply = analyze_log(agent, query)
            duration_ms = int((time.time() - start) * 1000)
            return jsonify({
                "reply": reply,
                "agent": agent_name,
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
            # Simple pagination params
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
