"""
Workforce orchestrator for multi-agent log analysis.
"""
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, Tuple
from camel.agents import ChatAgent
from agent_system.agents.internal_knowledge import make_internal_knowledge_agent
from agent_system.agents.error_reasoner import make_error_reasoner_agent

logger = logging.getLogger(__name__)


def _execute_agent_with_retry(agent: ChatAgent, prompt: str, agent_name: str, max_retries: int = 3) -> Tuple[Optional[str], Optional[str]]:
    """
    Execute an agent with retry logic.
    
    Args:
        agent: The ChatAgent instance to execute
        prompt: The prompt to send to the agent
        agent_name: Name of the agent for logging
        max_retries: Maximum number of retry attempts
    
    Returns:
        Tuple of (result_content, error_message). If successful, result_content is set and error_message is None.
        If failed after all retries, result_content is None and error_message contains the error.
    """
    last_error = None
    
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[{agent_name}] Attempt {attempt}/{max_retries}")
            response = agent.step(prompt)
            
            # Extract content from response
            content = None
            if hasattr(response, 'msg') and hasattr(response.msg, 'content'):
                content = getattr(response.msg, 'content', '') or ''
            elif hasattr(response, 'content'):
                content = response.content or ''
            elif isinstance(response, str):
                content = response
            else:
                # Try to get content from response object
                content = str(response)
            
            if content and content.strip():
                logger.info(f"[{agent_name}] Successfully completed on attempt {attempt}")
                return content.strip(), None
            else:
                raise ValueError(f"Empty response from {agent_name}")
                
        except Exception as e:
            last_error = str(e)
            logger.warning(f"[{agent_name}] Attempt {attempt}/{max_retries} failed: {last_error}")
            
            if attempt < max_retries:
                logger.info(f"[{agent_name}] Retrying...")
            else:
                logger.error(f"[{agent_name}] All {max_retries} attempts failed. Last error: {last_error}")
    
    return None, f"Failed after {max_retries} attempts: {last_error}"


def analyze_log_direct(log_data: str, max_retries: int = 3) -> str:
    """
    Analyze a log using direct agent orchestration (simpler than Workforce).
    
    Runs both Internal Knowledge and Error Reasoner agents in parallel with retry logic,
    then generates a summary from their results.
    
    Args:
        log_data: The log data to analyze (can be JSON string or raw log text)
        max_retries: Maximum number of retry attempts for each agent (default: 3)
    
    Returns:
        The analysis result as a formatted summary string
    """
    logger.info("Starting direct log analysis (parallel execution)")
    logger.debug(f"Log data: {log_data[:200]}...")
    
    # Construct task prompts for each agent
    internal_knowledge_prompt = (
        f"Retrieve historical logs and similar past errors related to this log entry. "
        f"Search the knowledge base for similar past errors and fixes using RAG. "
        f"Provide a summary of relevant historical context and any known fixes.\n\n"
        f"Log data:\n{log_data}"
    )
    
    error_reasoner_prompt = (
        f"Assess the severity of this error and check the health status of associated services. "
        f"Determine the error impact, severity level, and verify service availability. "
        f"Provide a clear assessment with severity level and explanation.\n\n"
        f"Log data:\n{log_data}"
    )
    
    # Create agents
    logger.info("Creating agents...")
    internal_knowledge_agent = make_internal_knowledge_agent()
    error_reasoner_agent = make_error_reasoner_agent()
    
    # Execute agents in parallel
    logger.info("Executing agents in parallel...")
    internal_knowledge_result = None
    error_reasoner_result = None
    internal_knowledge_error = None
    error_reasoner_error = None
    
    with ThreadPoolExecutor(max_workers=2) as executor:
        # Submit both tasks
        future_ik = executor.submit(
            _execute_agent_with_retry,
            internal_knowledge_agent,
            internal_knowledge_prompt,
            "Internal Knowledge Agent",
            max_retries
        )
        future_er = executor.submit(
            _execute_agent_with_retry,
            error_reasoner_agent,
            error_reasoner_prompt,
            "Error Reasoner Agent",
            max_retries
        )
        
        # Wait for both to complete and collect results
        for future in as_completed([future_ik, future_er]):
            try:
                result, error = future.result()
                # Determine which agent this result belongs to
                if future == future_ik:
                    internal_knowledge_result = result
                    internal_knowledge_error = error
                else:
                    error_reasoner_result = result
                    error_reasoner_error = error
            except Exception as e:
                logger.error(f"Unexpected error in parallel execution: {e}", exc_info=True)
                # Try to determine which future failed
                if future == future_ik:
                    internal_knowledge_error = f"Unexpected error: {str(e)}"
                else:
                    error_reasoner_error = f"Unexpected error: {str(e)}"
    
    # Generate summary
    logger.info("Generating summary from agent results...")
    summary = _generate_direct_summary(
        internal_knowledge_result,
        error_reasoner_result,
        log_data,
        {
            'internal_knowledge': internal_knowledge_error,
            'error_reasoner': error_reasoner_error
        }
    )
    
    return summary


def _generate_direct_summary(
    internal_knowledge_result: Optional[str],
    error_reasoner_result: Optional[str],
    log_data: str,
    errors: dict
) -> str:
    """
    Generate a summary from direct agent execution results.
    
    Args:
        internal_knowledge_result: Result from Internal Knowledge Agent (None if failed)
        error_reasoner_result: Result from Error Reasoner Agent (None if failed)
        log_data: Original log data
        errors: Dictionary with error messages for each agent (key: agent name, value: error message)
    
    Returns:
        Formatted summary string
    """
    summary_parts = []
    summary_parts.append("=" * 80)
    summary_parts.append("LOG ANALYSIS SUMMARY")
    summary_parts.append("=" * 80)
    summary_parts.append(f"\nOriginal Log:\n{log_data}\n")
    summary_parts.append("-" * 80)
    summary_parts.append("\nAnalysis Results:\n")
    
    # Internal Knowledge Agent results
    summary_parts.append("\n[Internal Knowledge Agent]")
    if internal_knowledge_result:
        summary_parts.append("Status: ✓ Completed")
        summary_parts.append(f"Result:\n{internal_knowledge_result}\n")
    else:
        summary_parts.append("Status: ✗ Failed")
        if errors.get('internal_knowledge'):
            summary_parts.append(f"Error: {errors['internal_knowledge']}\n")
        else:
            summary_parts.append("Error: Unknown error occurred\n")
    summary_parts.append("-" * 80)
    
    # Error Reasoner Agent results
    summary_parts.append("\n[Error Reasoner Agent]")
    if error_reasoner_result:
        summary_parts.append("Status: ✓ Completed")
        summary_parts.append(f"Result:\n{error_reasoner_result}\n")
    else:
        summary_parts.append("Status: ✗ Failed")
        if errors.get('error_reasoner'):
            summary_parts.append(f"Error: {errors['error_reasoner']}\n")
        else:
            summary_parts.append("Error: Unknown error occurred\n")
    summary_parts.append("-" * 80)
    
    # Final status
    both_completed = internal_knowledge_result and error_reasoner_result
    one_completed = (internal_knowledge_result or error_reasoner_result) and not both_completed
    
    summary_parts.append("\n[Summary Status]")
    if both_completed:
        summary_parts.append("✓ Both specialized agents (Internal Knowledge and Error Reasoner) have completed their analysis.")
    elif one_completed:
        summary_parts.append("⚠ Partial completion: One agent completed successfully, one failed.")
    else:
        summary_parts.append("✗ Both agents failed to complete their analysis.")
    summary_parts.append("=" * 80)
    
    return "\n".join(summary_parts)

