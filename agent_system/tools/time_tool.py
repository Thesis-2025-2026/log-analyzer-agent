from datetime import datetime, timezone
from typing import Dict


def get_current_time() -> Dict[str, object]:
    """
    Return the current UTC time for time-range log queries.

    Returns:
        {
            "utc": "2025-01-14T09:42:17.883Z",
            "epoch_seconds": 1736857337
        }
    """
    now = datetime.now(timezone.utc)
    return {
        "utc": now.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
        "epoch_seconds": int(now.timestamp()),
    }
