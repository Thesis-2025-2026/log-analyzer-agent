"""
Internal Knowledge Tool for querying the Internal Knowledge Agent.

This tool allows the Main Agent to query the Internal Knowledge Agent
for historical logs, similar past errors, and known fixes.
"""
from typing import Optional
import logging
import os
import time

from agent_system.core.tracing import instrument_agent_step
from agent_system.core.rate_limit import looks_rate_limited, compute_sleep_seconds

logger = logging.getLogger(__name__)

MAX_RETRIES = int(os.getenv("INTERNAL_KNOWLEDGE_MAX_RETRIES", "3"))
RATE_LIMIT_BASE_SLEEP_SECONDS = float(os.getenv("INTERNAL_KNOWLEDGE_RATE_LIMIT_BASE_SLEEP_SECONDS", "1.0"))
RATE_LIMIT_MAX_SLEEP_SECONDS = float(os.getenv("INTERNAL_KNOWLEDGE_RATE_LIMIT_MAX_SLEEP_SECONDS", "30"))


def query_internal_knowledge(log_data: str, query_type: str = "full") -> str:
    """
    Query the Internal Knowledge Agent for historical context and similar past errors.
    
    This tool delegates to the Internal Knowledge Agent to retrieve:
    - Historical logs from the SQL database that match error patterns
    - Similar past errors and their fixes from the vector database (RAG)
    - Patterns and trends in log data
    
    Args:
        log_data: The log data to analyze (error message, stack trace, etc.)
        query_type: Type of query to perform:
            - "full": Get both historical logs and RAG-based fixes (default)
            - "logs_only": Only query historical logs from SQL database
            - "fixes_only": Only query RAG for similar errors and fixes
    
    Returns:
        A string containing the Internal Knowledge Agent's response with:
        - Summary of relevant historical logs found
        - Similar past errors and their resolutions (if available)
        - Patterns or trends identified
        - Recommendations based on historical data
    """
    # Import here to avoid circular dependencies
    from agent_system.agents.internal_knowledge import make_internal_knowledge_agent

    logger.info(f"Querying Internal Knowledge Agent (query_type: {query_type})")

    # Construct the prompt based on query type
    if query_type == "logs_only":
        prompt = (
            f"Retrieve historical logs from the SQL database that match this error pattern. "
            f"Focus only on past occurrences and trends.\n\n"
            f"Log data:\n{log_data}"
        )
    elif query_type == "fixes_only":
        prompt = (
            f"Search the vector database (RAG) for similar past errors and their fixes. "
            f"Focus on known solutions and resolutions.\n\n"
            f"Log data:\n{log_data}"
        )
    else:  # full
        prompt = (
            f"Retrieve historical logs and similar past errors related to this log entry. "
            f"Search the knowledge base for similar past errors and fixes using RAG. "
            f"Provide a comprehensive summary of relevant historical context and any known fixes.\n\n"
            f"Log data:\n{log_data}"
        )

    last_error: Optional[str] = None
    for attempt in range(1, max(1, MAX_RETRIES) + 1):
        try:
            internal_agent = make_internal_knowledge_agent()
            response = instrument_agent_step(
                "Internal Knowledge Agent",
                prompt,
                lambda: internal_agent.step(prompt),
            )

            # Extract content from response
            content = None
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                content = getattr(response.msg, 'content', '') or ''
            elif hasattr(response, 'content'):
                content = response.content or ''
            elif isinstance(response, str):
                content = response
            else:
                content = str(response)

            if content and content.strip():
                logger.info("Successfully retrieved internal knowledge")
                return content.strip()

            raise ValueError("Internal Knowledge Agent returned empty response")
        except Exception as e:
            last_error = str(e)
            logger.warning(
                "Internal Knowledge Agent attempt %d/%d failed: %s",
                attempt,
                MAX_RETRIES,
                last_error,
            )
            if attempt >= MAX_RETRIES:
                break
            if looks_rate_limited(last_error):
                sleep_s = compute_sleep_seconds(
                    last_error,
                    attempt=attempt,
                    base_seconds=RATE_LIMIT_BASE_SLEEP_SECONDS,
                    max_seconds=RATE_LIMIT_MAX_SLEEP_SECONDS,
                )
                logger.warning(
                    "Internal Knowledge Agent rate-limited; sleeping %.2fs before retry (%d/%d).",
                    sleep_s,
                    attempt,
                    MAX_RETRIES,
                )
                time.sleep(sleep_s)

    logger.error("Failed to query Internal Knowledge Agent after %d attempts: %s", MAX_RETRIES, last_error)
    return f"Error querying internal knowledge: {last_error}"
