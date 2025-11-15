"""
Internal Knowledge Agent for retrieving historical logs and RAG-based knowledge.
"""
from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from agent_system.core.model_factory import create_model
from agent_system.prompts.internal_knowledge import get_internal_knowledge_prompt
from agent_system.tools.db_tool import query_logs, get_logs_by_error_pattern
from agent_system.tools.rag_tool import search_fixes_for_error, add_fix_to_knowledge_base


def make_internal_knowledge_agent() -> ChatAgent:
    """Create an Internal Knowledge Agent with DB and RAG tools."""
    model = create_model(tool_choice=None)
    system_prompt = get_internal_knowledge_prompt()
    
    tools = [
        FunctionTool(query_logs),
        FunctionTool(get_logs_by_error_pattern),
        FunctionTool(search_fixes_for_error), # goes to the internal Vector DB to look up the fixes
        # FunctionTool(add_fix_to_knowledge_base),
    ]
    
    return ChatAgent(
        system_message=system_prompt,
        model=model,
        # tools=tools, # FIXME: fix the tooling, now it goes and create an infinite loop
    )

