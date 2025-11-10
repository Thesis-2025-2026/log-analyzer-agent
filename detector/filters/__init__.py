from typing import Optional, Dict
from . import severity_filter
from . import regex_filter
from . import similarity_filter


# Order:
# 1) Regex: must mention error-ish terms -> else drop
# 2) Severity: drop if info/debug -> else continue
# 3) Similarity: drop if similar within TTL -> else publish
def run_filters(log: Dict) -> bool:
    if regex_filter.run(log) is not True:
        return False

    if severity_filter.run(log) is False:
        return False

    sim: Optional[bool] = similarity_filter.run(log)
    if sim is False:
        return False
    return True
