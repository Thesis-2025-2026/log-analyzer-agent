from __future__ import annotations

import random
import re
from typing import Optional

_RETRY_AFTER_PATTERN = re.compile(r"Please try again in\\s+([0-9.]+)(ms|s)", re.IGNORECASE)


def looks_rate_limited(text: str) -> bool:
    lowered = (text or "").lower()
    return (
        "rate limit reached" in lowered
        or "rate_limit_exceeded" in lowered
        or "error code: 429" in lowered
        or "http/1.1 429" in lowered
        or "too many requests" in lowered
    )


def parse_retry_after_seconds(text: str) -> Optional[float]:
    m = _RETRY_AFTER_PATTERN.search(text or "")
    if not m:
        return None
    value = float(m.group(1))
    unit = m.group(2).lower()
    return (value / 1000.0) if unit == "ms" else value


def compute_sleep_seconds(
    message: str,
    *,
    attempt: int,
    base_seconds: float = 1.0,
    max_seconds: float = 30.0,
) -> float:
    """
    Compute sleep duration for a rate limit error.
    - Prefer server-provided 'Please try again in Xms/Xs' when present.
    - Fallback to exponential backoff with jitter.
    """
    retry_after = parse_retry_after_seconds(message)
    if retry_after is not None:
        seconds = retry_after + 0.2 + random.random() * 0.2
        return min(seconds, max_seconds)

    exp = base_seconds * (2 ** max(0, attempt - 1))
    seconds = exp + random.random() * 0.3
    return min(seconds, max_seconds)

