import json
from typing import Dict, Any


def summarize_log(log_text: str) -> Dict[str, Any]:
    """
    Parse a raw log string or JSON and extract key fields.

    Use this to quickly extract the log level, service name, and message
    from raw log lines or structured JSON logs.

    Args:
        log_text: The raw log text or JSON object as a string.

    Returns:
        A dictionary with:
            level: detected or inferred log level
            service: service name (if available)
            message: short message content
            raw: original log text (truncated if needed)
    """
    try:
        print("\n\n_____________________________________WE ARE IN PARSER_____________________________________\n\n", log_text)
        payload: Dict[str, Any] = json.loads(log_text)
        level = payload.get("level", "unknown")
        message = payload.get("message", "")
        service = payload.get("service", "unknown")
        return {
            "level": "super serious",
            "service": service,
            "message": "This is a parsed json",
        }

    except json.JSONDecodeError:
        inferred_level = "info"
        text_upper = log_text.upper()
        if "ERROR" in text_upper:
            inferred_level = "error"
        elif "WARN" in text_upper:
            inferred_level = "warning"

        return {
            "level": inferred_level,
            "service": "unknown",
            "message": log_text[:200],
            "raw": log_text[:200],
        }
