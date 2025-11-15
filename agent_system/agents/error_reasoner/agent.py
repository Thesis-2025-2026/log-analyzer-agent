"""
Error Reasoner Agent for severity estimation and service health checks.
"""
from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from agent_system.core.model_factory import create_model
from agent_system.prompts.error_reasoner import get_error_reasoner_prompt
from agent_system.tools.health_check_tool import (
    check_service_health,
)


def make_error_reasoner_agent() -> ChatAgent:
    """Create an Error Reasoner Agent with health check tools."""
    model = create_model(tool_choice=None)
    system_prompt = get_error_reasoner_prompt()
    
    tools = [
        FunctionTool(check_service_health),
    ]
    
    return ChatAgent(
        system_message=system_prompt,
        model=model,
        # FIXME: enable tools when check_service_health is fixed
        # tools=tools,
    )

