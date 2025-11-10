import re
import json
from typing import Optional, Dict, List, Pattern


# Common error-ish terms seen in logs. Case-insensitive word-ish matches.
TERMS: List[str] = [
    r"error",
    r"warning",
    r"warn",
    r"exception",
    r"fail(?:ed)?",
    r"fatal",
    r"panic",
    r"traceback",
    r"stack(?:trace)?",
    r"timeout",
    r"refused",
    r"unreachable",
    r"crash",
]

PATTERNS: List[Pattern[str]] = [re.compile(rf"\b{p}\b", re.IGNORECASE) for p in TERMS]


def run(log: Dict) -> Optional[bool]:
    try:
        text = json.dumps(log, ensure_ascii=False)
    except Exception:
        text = str(log)

    for pat in PATTERNS:
        if pat.search(text):
            return None
    return False

