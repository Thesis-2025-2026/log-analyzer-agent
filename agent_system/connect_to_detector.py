"""
Connect to the detector module and process flagged logs using the Workforce orchestration system.
"""
# Import settings first to configure logging before other imports
from agent_system.config import settings  # noqa: F401

import logging
import os
import redis
import json
import requests

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
ANOM_CHANNEL = os.getenv("ANOM_CHANNEL", "anomalies")

SERVICE_URL = (os.getenv("AGENT_API_URL") or os.getenv("SERVICE_URL") or "http://localhost:8000").rstrip("/")
AGENT_API_TIMEOUT_SECONDS = int(os.getenv("AGENT_API_TIMEOUT_SECONDS", "600"))


def main():
    """Main entry point for the agent system that listens for anomalies from the detector."""
    # Connect to Redis
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB)
    pubsub = r.pubsub()
    pubsub.subscribe(ANOM_CHANNEL)
    
    print("Initializing Main Agent for log analysis...")
    print("Main Agent initialized and ready.")
    
    print("AI Agent listening for anomalies...")
    
    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                anomaly = json.loads(message["data"])
                print("\n🚨 AI Agent received anomaly:", anomaly)
                logger.info(
                    "Investigating anomaly from detector",
                    extra={
                        "service": anomaly.get("service", "unknown"),
                        "level": anomaly.get("level", "unknown"),
                        "trace_id": anomaly.get("trace_id"),
                        "flow": anomaly.get("flow"),
                    },
                )
                
                # Convert anomaly to log data string for analysis
                log_data = json.dumps(anomaly) if isinstance(anomaly, dict) else str(anomaly)

                # Delegate analysis to the local Agent API so it uses the exact same tracing path (/api/query).
                print(f"📊 Analyzing via Agent API: {SERVICE_URL}/api/query")
                payload = {"query": log_data, "persist_report": True}
                if isinstance(anomaly, dict):
                    trace_id = anomaly.get("trace_id")
                    if isinstance(trace_id, str) and trace_id.strip():
                        payload["trace_id"] = trace_id.strip()

                resp = requests.post(
                    f"{SERVICE_URL}/api/query",
                    json=payload,
                    timeout=AGENT_API_TIMEOUT_SECONDS,
                )
                data = {}
                try:
                    data = resp.json()
                except Exception:
                    data = {"error": resp.text}

                if resp.status_code != 200:
                    raise RuntimeError(f"Agent API error {resp.status_code}: {data.get('error') or data}")

                print("✅ Analysis complete.")
                if data.get("report_id") is not None:
                    print(f"💾 Report stored with ID: {data.get('report_id')}")
                if data.get("trace_id"):
                    print(f"🧵 trace_id: {data.get('trace_id')}")
                if data.get("reply"):
                    print(f"\n📋 Analysis Result:\n{data.get('reply')}\n")
                    
            except json.JSONDecodeError as e:
                print(f"[error] Failed to parse anomaly message: {e}")
            except Exception as e:
                print(f"[error] Error processing anomaly: {e}")


if __name__ == "__main__":
    main()
