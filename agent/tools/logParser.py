import json
from typing import Dict, Any


def summarizeLog(logText: str) -> str:
    try:
        payload: Dict[str, Any] = json.loads(logText)
        level = payload.get("level", "unknown")
        message = payload.get("message", "")
        service = payload.get("service", "unknown")
        return f"level={level} service={service} message={message}"
    except json.JSONDecodeError:
        inferredLevel = "info"
        textUpper = logText.upper()
        if "ERROR" in textUpper:
            inferredLevel = "error"
        elif "WARN" in textUpper:
            inferredLevel = "warning"
        return f"level={inferredLevel} raw={logText[:200]}"
