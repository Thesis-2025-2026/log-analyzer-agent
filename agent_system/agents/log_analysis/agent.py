from camel.agents import ChatAgent
from camel.toolkits import FunctionTool
from agent_system.core.agent_factory import build_agent
from agent_system.prompts.log_analysis import get_prompt
from agent_system.tools.log_parser import summarize_log


def make_agent() -> ChatAgent:
    system_prompt = get_prompt()
    return build_agent(system_prompt, tools=[FunctionTool(summarize_log)])

