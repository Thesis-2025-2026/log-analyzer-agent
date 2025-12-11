"""
Main Agent for orchestration, reasoning, and comprehensive log analysis.
"""
from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from agent_system.core.model_factory import create_model
from agent_system.prompts.main_agent import get_main_agent_prompt
from agent_system.tools.health_check_tool import check_service_health
from agent_system.tools.internal_knowledge_tool import query_internal_knowledge


def make_main_agent() -> ChatAgent:
    """
    Create a Main Agent with orchestration, reasoning, and health check capabilities.
    
    The Main Agent is responsible for:
    - Receiving and parsing log analysis requests
    - Orchestrating the analysis workflow
    - Analyzing error severity and impact
    - Checking service health
    - Querying internal knowledge when needed
    - Synthesizing information from multiple sources
    - Generating final analysis reports with recommendations
    
    Returns:
        A configured ChatAgent instance with all necessary tools
    """
    model = create_model(tool_choice=None)
    system_prompt = get_main_agent_prompt()
    
    tools = [
        FunctionTool(check_service_health),
        FunctionTool(query_internal_knowledge),
    ]
    
    return ChatAgent(
        system_message=system_prompt,
        model=model,
        tools=tools,
    )

