"""
Main Agent workflow for log analysis.
"""
import logging
import os
import time
from typing import Optional, List

from agent_system.tools.cross_service_tool import (
    set_visited_services,
    CURRENT_SERVICE_NAME,
)
from agent_system.core.tracing import instrument_agent_step
from agent_system.core.rate_limit import looks_rate_limited, compute_sleep_seconds
logger = logging.getLogger(__name__)

RATE_LIMIT_BASE_SLEEP_SECONDS = float(os.getenv("AGENT_RATE_LIMIT_BASE_SLEEP_SECONDS", "1.0"))
RATE_LIMIT_MAX_SLEEP_SECONDS = float(os.getenv("AGENT_RATE_LIMIT_MAX_SLEEP_SECONDS", "30"))


def make_main_agent():
    """Factory wrapper to allow monkeypatching in tests."""
    from agent_system.agents.main_agent import make_main_agent as factory
    return factory()


def analyze_log_with_main_agent(
    log_data: str,
    max_retries: int = 3,
    visited_services: Optional[List[str]] = None,
) -> str:
    """
    Analyze a log using the Main Agent.
    
    The Main Agent handles the entire workflow:
    - Parsing and understanding the log
    - Determining if internal knowledge is needed
    - Checking service health when necessary
    - Assessing error severity and impact
    - Generating final recommendations
    
    Args:
        log_data: The log data to analyze (can be JSON string or raw log text)
        max_retries: Maximum number of retry attempts (default: 3)
    
    Returns:
        The analysis result as a comprehensive report string
    """
    logger.info("Starting log analysis with Main Agent")
    logger.debug(f"Log data: {log_data[:200]}...")

    # Seed visited-services context to prevent cycles
    visited = list(visited_services or [])
    if CURRENT_SERVICE_NAME and CURRENT_SERVICE_NAME not in visited:
        visited.append(CURRENT_SERVICE_NAME)
    set_visited_services(visited)
    
    # Construct the analysis prompt
    prompt = (
        f"Analyze the following log entry and provide a comprehensive assessment. "
        f"Query internal knowledge if you need historical context or similar past errors. "
        f"Check service health if the error suggests a service failure. "
        f"Provide severity assessment, impact analysis, and actionable recommendations.\n\n"
        f"Log data:\n{log_data}"
    )
    
    # Create the Main Agent
    logger.info("Creating Main Agent...")
    main_agent = make_main_agent()
    
    # Execute with retry logic
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Main Agent] Attempt {attempt}/{max_retries}")
            response = instrument_agent_step(
                "Main Agent",
                prompt,
                lambda: main_agent.step(prompt),
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
                logger.info(f"[Main Agent] Successfully completed on attempt {attempt}")
                return _format_analysis_result(content.strip(), log_data)
            else:
                raise ValueError("Empty response from Main Agent")
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[Main Agent] Attempt {attempt}/{max_retries} failed: {last_error}")
            
            if attempt < max_retries:
                if looks_rate_limited(last_error):
                    sleep_s = compute_sleep_seconds(
                        last_error,
                        attempt=attempt,
                        base_seconds=RATE_LIMIT_BASE_SLEEP_SECONDS,
                        max_seconds=RATE_LIMIT_MAX_SLEEP_SECONDS,
                    )
                    logger.warning(
                        "[Main Agent] Rate-limited; sleeping %.2fs before retry (%d/%d).",
                        sleep_s,
                        attempt,
                        max_retries,
                    )
                    time.sleep(sleep_s)
                else:
                    logger.info(f"[Main Agent] Retrying...")
            else:
                logger.error(f"[Main Agent] All {max_retries} attempts failed. Last error: {last_error}")
    
    # If all attempts failed, return error message
    return _format_error_result(log_data, last_error, max_retries)


def _format_analysis_result(content: str, log_data: str) -> str:
    """Format the successful analysis result."""
    # The UI renders Markdown; avoid noisy ASCII banners and return the agent output directly.
    return content


def _format_error_result(log_data: str, error: Optional[str], max_retries: int) -> str:
    """Format the error result when analysis fails."""
    parts = [
        "## Analysis Failed",
        "",
        f"The Main Agent failed to complete the analysis after {max_retries} attempt(s).",
    ]
    if error:
        parts.extend(["", f"**Error:** `{error}`"])
    return "\n".join(parts)
