from camel.agents import ChatAgent
from agent_system.core.model_factory import create_model


def build_agent(system_prompt: str, tools: list | None = None) -> ChatAgent:
    model = create_model()
    return ChatAgent(
        system_message=system_prompt,
        model=model,
        tools=tools or [],
    )
