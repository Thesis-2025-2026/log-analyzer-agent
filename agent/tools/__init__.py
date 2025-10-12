from typing import Callable, Dict
from agent.tools.log_parser import summarize_log


def build_tools() -> Dict[str, Callable[[str], str]]:
    return {
        "summarize_log": summarize_log,
    }
