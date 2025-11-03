from flask import Flask, request, jsonify
from flask_cors import CORS
import time

from agent_system.core.registry import get_agent
from agent_system.__main__ import analyze_log


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

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.post("/api/query")
    def api_query():
        data = request.get_json(silent=True) or {}
        query = data.get("query") or data.get("text") or data.get("log")
        agent_name = data.get("agent") or "log_analysis"

        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Missing 'query' in JSON body"}), 400

        if not isinstance(agent_name, str) or not agent_name.strip():
            agent_name = "log_analysis"

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
    def list_reports():
        # TODO: implement reports listing (paginate, filter)
        return jsonify({"items": [], "total": 0}), 200

    @app.get("/api/reports/<rid>")
    def get_report(rid: str):
        # TODO: implement single report retrieval
        return jsonify({"id": rid, "status": "todo", "message": "Not implemented"}), 200

    return app
