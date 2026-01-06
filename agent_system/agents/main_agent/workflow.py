"""
Main Agent workflow for log analysis.
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def analyze_log_with_main_agent(log_data: str, max_retries: int = 3) -> str:
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
    
    # Import here to avoid circular dependencies
    from agent_system.agents.main_agent import make_main_agent
    
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
            response = main_agent.step(prompt)
            
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
                logger.info(f"[Main Agent] Retrying...")
            else:
                logger.error(f"[Main Agent] All {max_retries} attempts failed. Last error: {last_error}")
    
    # If all attempts failed, return error message
    return _format_error_result(log_data, last_error, max_retries)


def _format_analysis_result(content: str, log_data: str) -> str:
    """Format the successful analysis result."""
    result_parts = []
    result_parts.append("=" * 80)
    result_parts.append("LOG ANALYSIS REPORT")
    result_parts.append("=" * 80)
    result_parts.append(f"\nOriginal Log:\n{log_data}\n")
    result_parts.append("-" * 80)
    result_parts.append("\nAnalysis:\n")
    result_parts.append(content)
    result_parts.append("\n" + "=" * 80)
    
    return "\n".join(result_parts)


def _format_error_result(log_data: str, error: Optional[str], max_retries: int) -> str:
    """Format the error result when analysis fails."""
    result_parts = []
    result_parts.append("=" * 80)
    result_parts.append("LOG ANALYSIS REPORT - ERROR")
    result_parts.append("=" * 80)
    result_parts.append(f"\nOriginal Log:\n{log_data}\n")
    result_parts.append("-" * 80)
    result_parts.append("\nAnalysis Status: ✗ Failed")
    result_parts.append(f"\nThe Main Agent failed to complete the analysis after {max_retries} attempts.")
    if error:
        result_parts.append(f"Error: {error}")
    result_parts.append("\n" + "=" * 80)
    
    return "\n".join(result_parts)

