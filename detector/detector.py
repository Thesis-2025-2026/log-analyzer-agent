import os
import json
import redis
from filters import run_filters

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

LOGS_CHANNEL = os.getenv("LOGS_CHANNEL", "logs")
ANOM_CHANNEL = os.getenv("ANOM_CHANNEL", "anomalies")


def main() -> None:
    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True)
    pubsub = r.pubsub(ignore_subscribe_messages=True)
    pubsub.subscribe(LOGS_CHANNEL)

    print(f"Detector is running. Subscribed to '{LOGS_CHANNEL}' → publishing to '{ANOM_CHANNEL}'")

    for message in pubsub.listen():
        data_str = message.get("data")
        try:
            log = json.loads(data_str)
        except json.JSONDecodeError:
            continue

        if run_filters(log):
            try:
                r.publish(ANOM_CHANNEL, json.dumps(log))
            except Exception:
                pass


if __name__ == "__main__":
    main()
