"""
Connect to the detector module and process flagged logs using the Workforce orchestration system.
"""
# Import settings first to configure logging before other imports
from agent_system.config import settings  # noqa: F401

import logging
import os
import redis
import json
from agent_system.agents.main_agent.workflow import analyze_log_with_main_agent
from agent_system.core.storage import insert_report
from agent_system.tools.log_parser import summarize_log

logger = logging.getLogger(__name__)

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))
ANOM_CHANNEL = os.getenv("ANOM_CHANNEL", "anomalies")


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
                
                # Analyze the log using the workforce
                print("📊 Analyzing log with Main Agent...")
                analysis_result = analyze_log_with_main_agent(log_data)
                print("✅ Analysis complete.")
                print(f"\n📋 Analysis Result:\n{analysis_result}\n")
                
                # Extract metadata for storage
                level = "unknown"
                service = "unknown"
                try:
                    parsed = summarize_log(log_data)
                    level = str(parsed.get("level", level))
                    service = str(parsed.get("service", service))
                except Exception as e:
                    print(f"[warn] Failed to parse log metadata: {e}")
                
                # Store the analysis report
                try:
                    report = insert_report(
                        level=level,
                        service=service,
                        content=analysis_result,
                        raw_log=log_data
                    )
                    print(f"💾 Report stored with ID: {report.get('id')}")
                except Exception as e:
                    print(f"[warn] Failed to store report: {e}")
                    
            except json.JSONDecodeError as e:
                print(f"[error] Failed to parse anomaly message: {e}")
            except Exception as e:
                print(f"[error] Error processing anomaly: {e}")


if __name__ == "__main__":
    main()
