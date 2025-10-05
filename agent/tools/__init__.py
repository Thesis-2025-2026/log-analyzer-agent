from typing import List
from langchain.tools import Tool
from agent.tools.logParser import summarizeLog


def buildTools() -> List[Tool]:
    return [
        Tool(
            name="summarizeLog",
            func=summarizeLog,
            description="Extracts key fields from a raw log line or JSON and returns a short summary.",
        ),
    ]
