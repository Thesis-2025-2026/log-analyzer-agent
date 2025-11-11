"""
Connect to the detector module and process flagged logs using the Workforce orchestration system.
"""
import redis
import json
from agent_system.agents.orchestrator import create_log_analysis_workforce, analyze_log_with_workforce
from agent_system.core.storage import insert_report
from agent_system.tools.log_parser import summarize_log


def main():
    """Main entry point for the agent system that listens for anomalies from the detector."""
    # Connect to Redis
    r = redis.Redis(host="localhost", port=6379, db=0)
    pubsub = r.pubsub()
    pubsub.subscribe("anomalies")
    
    # Create the workforce for log analysis
    print("Initializing Workforce for log analysis...")
    workforce = create_log_analysis_workforce()
    print("Workforce initialized and ready.")
    
    print("AI Agent listening for anomalies...")
    
    for message in pubsub.listen():
        if message["type"] == "message":
            try:
                anomaly = json.loads(message["data"])
                print("\n🚨 AI Agent received anomaly:", anomaly)
                
                # Convert anomaly to log data string for analysis
                log_data = json.dumps(anomaly) if isinstance(anomaly, dict) else str(anomaly)
                
                # Analyze the log using the workforce
                print("📊 Analyzing log with Workforce...")
                analysis_result = analyze_log_with_workforce(workforce, log_data)
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
