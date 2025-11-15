import os
import hashlib
from typing import Optional, Dict, Any

import redis


REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB = int(os.getenv("REDIS_DB", "0"))

SIM_TTL_SEC = int(os.getenv("SIM_TTL_SEC", "60"))
SIM_NAMESPACE = os.getenv("SIM_NAMESPACE", "det:sim")

_r = None


def _redis():
    global _r
    if _r is None:
        _r = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB, decode_responses=True
        )
    return _r


def _canon(obj: Any, parent: str = "") -> str:
    if isinstance(obj, dict):
        parts = []
        for k in sorted(obj.keys()):
            parts.append(f"{k}:{_canon(obj[k], k)}")
        return "{" + ",".join(parts) + "}"
    if isinstance(obj, list):
        return f"[{parent}:{len(obj)}]"
    return f"<{parent}>"


def _fingerprint(log: Dict) -> str:
    tmpl = _canon(log)
    return hashlib.md5(tmpl.encode("utf-8")).hexdigest()[:16]


def run(log: Dict) -> Optional[bool]:
    try:
        fp = _fingerprint(log)
    except Exception:
        return None

    key = f"{SIM_NAMESPACE}:{fp}"
    created = _redis().set(key, "1", nx=True, ex=SIM_TTL_SEC)
    if created:
        return True
    return False

