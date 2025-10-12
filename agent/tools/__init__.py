from typing import Callable, Dict
from agent.tools.logParser import summarizeLog


def buildTools() -> Dict[str, Callable[[str], str]]:
    return {
        "summarizeLog": summarizeLog,
    }
