import redis
import json

r = redis.Redis(host="localhost", port=6379, db=0)

pubsub = r.pubsub()
pubsub.subscribe("logs")

print("Detector is running...")

for message in pubsub.listen():
    if message["type"] == "message":
        log = json.loads(message["data"])
        print("Detector received:", log)

        if log.get("level") == "ERROR":
            r.publish("anomalies", json.dumps(log))