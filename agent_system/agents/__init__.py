"""
Agent System - Main and Internal Knowledge Agents
"""
from agent_system.agents.main_agent import make_main_agent, analyze_log_with_main_agent
from agent_system.agents.internal_knowledge import make_internal_knowledge_agent

__all__ = [
    'make_main_agent',
    'analyze_log_with_main_agent',
    'make_internal_knowledge_agent',
]

