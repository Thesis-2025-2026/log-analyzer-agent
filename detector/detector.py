import os
import json
import redis
from detector.filters import run_filters
from agent_system.core.storage import insert_log

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

LOGS_CHANNEL = os.getenv("LOGS_CHANNEL", "logs")
ANOM_CHANNEL = os.getenv("ANOM_CHANNEL", "anomalies")
ANOM_QUEUE_KEY = os.getenv("ANOM_QUEUE_KEY") or f"{ANOM_CHANNEL}:queue"

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

        # Archive every received log before filters
        try:
            level_val = log.get("level")
            level = level_val if isinstance(level_val, str) else (str(level_val) if level_val is not None else None)
            insert_log(level=level, raw=log)
        except Exception:
            # Do not block pipeline on archive failure
            pass

        # if DETECTOR_DEBUG:
        # print(f"[detector] received log: {data_str}")

        if run_filters(log):
            payload = json.dumps(log)
            try:
                print(f"Publishing: ", log)
                r.rpush(ANOM_QUEUE_KEY, payload)
                r.publish(ANOM_CHANNEL, payload)
            except Exception:
                pass


if __name__ == "__main__":
    main()
