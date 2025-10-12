import redis
import psycopg2
import json

# Connect to Redis
r = redis.Redis(host="localhost", port=6379, db=0)
pubsub = r.pubsub()
pubsub.subscribe("anomalies")

# Connect to Postgres
conn = psycopg2.connect(
    dbname="logs_db",
    user="logs_user",
    password="logs_pass",
    host="localhost",
    port=5433
)
cur = conn.cursor()

print("AI Agent listening for anomalies...")

for message in pubsub.listen():
    if message["type"] == "message":
        anomaly = json.loads(message["data"])
        print("\n🚨 AI Agent received anomaly:", anomaly)

        # Example: get last 5 logs with the same level as the anomaly
        cur.execute("""
            SELECT timestamp, raw
            FROM logs
            WHERE level = %s
            ORDER BY timestamp DESC
            LIMIT 5;
        """, (anomaly["level"],))

        context = cur.fetchall()
        print("📜 Context logs (last 5 with same level):")
        for row in context:
            print(row)
