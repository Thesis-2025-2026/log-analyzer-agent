"""
Internal Knowledge Tool for querying the Internal Knowledge Agent.

This tool allows the Main Agent to query the Internal Knowledge Agent
for historical logs, similar past errors, and known fixes.
"""
from typing import Optional
import logging

logger = logging.getLogger(__name__)


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
    try:
        # Import here to avoid circular dependencies
        from agent_system.agents.internal_knowledge import make_internal_knowledge_agent
        
        logger.info(f"Querying Internal Knowledge Agent (query_type: {query_type})")
        
        # Create the Internal Knowledge Agent
        internal_agent = make_internal_knowledge_agent()
        
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
        
        # Execute the Internal Knowledge Agent
        response = internal_agent.step(prompt)
        
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
        else:
            logger.warning("Internal Knowledge Agent returned empty response")
            return "No relevant historical data found in the knowledge base."
            
    except Exception as e:
        logger.error(f"Failed to query Internal Knowledge Agent: {e}", exc_info=True)
        return f"Error querying internal knowledge: {str(e)}"

