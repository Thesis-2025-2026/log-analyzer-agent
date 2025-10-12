from typing import Callable, Dict
from agent_system.agents.log_analysis.agent import make_agent as make_log_agent

_REGISTRY: Dict[str, Callable[[], object]] = {
    "log_analysis": make_log_agent,
}


def get_agent(name: str):
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(f"Unknown agent '{name}'. Available: {list(_REGISTRY)}")
