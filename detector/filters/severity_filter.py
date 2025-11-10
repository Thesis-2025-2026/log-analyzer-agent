from typing import Optional, Dict


def run(log: Dict) -> Optional[bool]:
    level_val = log.get("level")
    level = level_val.lower()
    if level not in ("info", "debug"):
        return None
    return False
