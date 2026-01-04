import json
from typing import Any, Dict, Optional


def _clean_one_line(text: str) -> str:
    return " ".join(str(text or "").replace("\r\n", "\n").replace("\r", "\n").split())


def _truncate(text: str, limit: int = 90) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)].rstrip() + "…"

TITLE_MAX_CHARS = 70


def generate_report_title(raw_log: str) -> str:
    """
    Generate a short incident title from the raw input log.

    This is intentionally lightweight and deterministic (no LLM call).
    It is used to populate the report list UI with a meaningful headline.

    Args:
        raw_log: Raw input string (may be JSON or plain text)

    Returns:
        A short title string.
    """
    service: Optional[str] = None
    message: Optional[str] = None
    error_code: Optional[str] = None

    try:
        payload: Dict[str, Any] = json.loads(raw_log)
        service = payload.get("service") or payload.get("service_name")
        message = payload.get("message") or payload.get("msg")
        error_code = payload.get("error_code") or payload.get("code")
    except Exception:
        pass

    if service is not None:
        service = _clean_one_line(str(service))
    if message is not None:
        message = _clean_one_line(str(message))
    if error_code is not None:
        error_code = _clean_one_line(str(error_code))

    if message:
        base = f"{service}: {message}" if service else message
        if error_code and error_code not in base:
            base = f"{base} ({error_code})"
        return _truncate(base, TITLE_MAX_CHARS)

    # Fallback: try to make something reasonable from raw text.
    cleaned = _clean_one_line(raw_log)
    if service:
        cleaned = f"{service}: {cleaned}"
    return _truncate(cleaned or "Incident", TITLE_MAX_CHARS)
