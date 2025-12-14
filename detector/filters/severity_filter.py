from typing import Optional, Dict


def run(log: Dict) -> Optional[bool]:
    """
    Drop low-signal logs (info/debug). Return True to drop, None to keep analyzing.
    """
    level_val = log.get("level")
    if not isinstance(level_val, str):
        return None

    level = level_val.strip().lower()
    if level in ("info", "debug"):
        return True  # Drop low-signal logs

    return None
