import json
from typing import Dict, Any


def summarize_log(log_text: str) -> str:
    try:
        payload: Dict[str, Any] = json.loads(log_text)
        level = payload.get("level", "unknown")
        message = payload.get("message", "")
        service = payload.get("service", "unknown")
        return f"level={level} service={service} message={message}"
    except json.JSONDecodeError:
        inferred_level = "info"
        text_upper = log_text.upper()
        if "ERROR" in text_upper:
            inferred_level = "error"
        elif "WARN" in text_upper:
            inferred_level = "warning"
        return f"level={inferred_level} raw={log_text[:200]}"
