from flask import Flask, request, jsonify
from flask_cors import CORS
import time

from agent_system.agents.main_agent import analyze_log_with_main_agent
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

        if not isinstance(query, str) or not query.strip():
            return jsonify({"error": "Missing 'query' in JSON body"}), 400

        start = time.time()

        try:
            # Use the new Main Agent for log analysis
            reply = analyze_log_with_main_agent(query)
            duration_ms = int((time.time() - start) * 1000)
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
