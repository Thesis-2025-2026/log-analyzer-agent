"""
Registry for agent creation functions.
Supports both legacy single agents and the new Workforce-based orchestration.
"""
from typing import Callable, Dict, Any
from agent_system.agents.orchestrator import create_log_analysis_workforce
from agent_system.agents.log_analysis.agent import make_agent as make_log_agent

# Cache for workforce instances (singleton pattern)
_workforce_cache: Dict[str, Any] = {}


_REGISTRY: Dict[str, Callable[[], object]] = {
    "log_analysis": make_log_agent,  # Legacy single agent
    "workforce": lambda: _get_or_create_workforce("default"),  # New workforce-based system
}


def _get_or_create_workforce(name: str = "default"):
    """Get or create a cached workforce instance."""
    if name not in _workforce_cache:
        _workforce_cache[name] = create_log_analysis_workforce()
    return _workforce_cache[name]


def get_agent(name: str):
    """
    Get an agent or workforce by name.
    
    Args:
        name: Agent name ("log_analysis" for legacy, "workforce" for new system)
    
    Returns:
        Agent or Workforce instance
    """
    try:
        return _REGISTRY[name]()
    except KeyError:
        raise ValueError(f"Unknown agent '{name}'. Available: {list(_REGISTRY)}")


def register_agent(name: str, factory: Callable[[], object]):
    """Register a new agent factory."""
    _REGISTRY[name] = factory
