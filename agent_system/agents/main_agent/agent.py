"""
Main Agent for orchestration, reasoning, and comprehensive log analysis.
"""
import os

from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from agent_system.core.model_factory import create_model
from agent_system.core.tracing import get_parent_event_id, get_trace_id, trace_tool_bound
from agent_system.prompts.main_agent import get_main_agent_prompt
from agent_system.tools.health_check_tool import check_service_health
from agent_system.tools.internal_knowledge_tool import query_internal_knowledge
from agent_system.tools.cross_service_tool import (
    discover_services,
    get_service_report,
    gather_cross_service_reports,
)


def make_main_agent() -> ChatAgent:
    """
    Create a Main Agent with orchestration, reasoning, and health check capabilities.
    
    The Main Agent is responsible for:
    - Receiving and parsing log analysis requests
    - Orchestrating the analysis workflow
    - Analyzing error severity and impact
    - Checking service health
    - Querying internal knowledge when needed
    - Discovering other services via the proxy
    - Gathering reports from other services for cross-service context
    - Synthesizing information from multiple sources
    - Generating final analysis reports with recommendations
    
    Returns:
        A configured ChatAgent instance with all necessary tools
    """
    model = create_model(tool_choice="auto")
    system_prompt = get_main_agent_prompt()

    trace_id = get_trace_id()
    parent_event_id = get_parent_event_id()
    service_name = os.getenv("SERVICE_NAME", "").strip() or None
    
    tools = [
        # Local analysis tools
        FunctionTool(
            trace_tool_bound(
                check_service_health,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Main Agent",
            )
        ),
        FunctionTool(
            trace_tool_bound(
                query_internal_knowledge,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Main Agent",
            )
        ),
        # Cross-service tools for distributed analysis
        FunctionTool(
            trace_tool_bound(
                discover_services,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Main Agent",
            )
        ),
        FunctionTool(
            trace_tool_bound(
                get_service_report,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Main Agent",
            )
        ),
        FunctionTool(
            trace_tool_bound(
                gather_cross_service_reports,
                trace_id=trace_id,
                parent_event_id=parent_event_id,
                service_name=service_name,
                agent_name="Main Agent",
            )
        ),
    ]
    
    return ChatAgent(
        system_message=system_prompt,
        model=model,
        tools=tools,
    )
