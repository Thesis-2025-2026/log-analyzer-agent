"""
Internal Knowledge Agent for retrieving historical logs and RAG-based knowledge.
"""
import os

from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from agent_system.core.model_factory import create_model
from agent_system.core.tracing import get_parent_event_id, get_trace_id, trace_tool_bound
from agent_system.prompts.internal_knowledge import get_internal_knowledge_prompt
from agent_system.tools.db_tool import query_logs_sql, query_logs_by_time_range
from agent_system.tools.rag_tool import search_fixes_for_error
from agent_system.tools.report_rag_tool import search_reports_for_context
from agent_system.tools.time_tool import get_current_time


def make_internal_knowledge_agent() -> ChatAgent:
    """Create an Internal Knowledge Agent with DB and RAG tools."""
    model = create_model(tool_choice="auto")
    system_prompt = get_internal_knowledge_prompt()

    trace_id = get_trace_id()
    parent_event_id = get_parent_event_id()
    service_name = os.getenv("SERVICE_NAME", "").strip() or None
    
    tools = [
        FunctionTool(
            trace_tool_bound(
                query_logs_sql,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Internal Knowledge Agent",
            )
        ),
        FunctionTool(
            trace_tool_bound(
                query_logs_by_time_range,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Internal Knowledge Agent",
            )
        ),
        FunctionTool(
            trace_tool_bound(
                search_fixes_for_error,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Internal Knowledge Agent",
            )
        ),
        FunctionTool(
            trace_tool_bound(
                search_reports_for_context,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Internal Knowledge Agent",
            )
        ),
        FunctionTool(
            trace_tool_bound(
                get_current_time,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Internal Knowledge Agent",
            )
        ),
    ]
    
    return ChatAgent(
        system_message=system_prompt,
        model=model,
        tools=tools
    )
