"""
Workforce orchestrator for multi-agent log analysis.
"""
from camel.societies.workforce import Workforce
from camel.tasks import Task
from camel.agents import ChatAgent
from agent_system.core.model_factory import create_model
from agent_system.prompts.orchestrator import get_orchestrator_prompt
from agent_system.agents.internal_knowledge import make_internal_knowledge_agent
from agent_system.agents.error_reasoner import make_error_reasoner_agent


def create_log_analysis_workforce() -> Workforce:
    """
    Create and configure a Workforce for log analysis tasks.
    
    The workforce consists of:
    - Coordinator Agent: Delegates tasks to specialized agents
    - Task Agent: Decomposes complex tasks into subtasks
    - Internal Knowledge Worker: Handles database queries and RAG searches
    - Error Reasoner Worker: Handles severity analysis and health checks
    """
    model = create_model()
    
    # Create coordinator agent with orchestrator prompt
    coordinator_prompt = get_orchestrator_prompt()
    coordinator_agent = ChatAgent(
        system_message=coordinator_prompt,
        model=model,
    )
    
    # Create task agent (can use same model and a task decomposition prompt)
    task_agent = ChatAgent(
        system_message=(
            "You are a task decomposition agent. Your role is to break down complex "
            "log analysis tasks into smaller, manageable subtasks that can be assigned "
            "to specialized agents. Each subtask should be clear, specific, and actionable."
        ),
        model=model,
    )
    
    # Create the workforce
    workforce = Workforce(
        description=(
            "A multi-agent system for intelligent log analysis. "
            "Processes flagged logs by coordinating specialized agents to gather context, "
            "analyze severity, check service health, and provide comprehensive analysis reports."
        ),
        coordinator_agent=coordinator_agent,
        task_agent=task_agent,
        share_memory=True,  # Workers can share context
        use_structured_output_handler=True,
    )
    
    # Add specialized workers
    workforce.add_single_agent_worker(
        description=(
            "An agent specialized in retrieving historical logs from the database "
            "and searching the knowledge base for similar past errors and fixes using RAG. "
            "Use this agent when you need historical context, pattern matching, or "
            "knowledge base lookups."
        ),
        worker=make_internal_knowledge_agent(),
    )
    
    workforce.add_single_agent_worker(
        description=(
            "An agent specialized in analyzing error severity and checking the health "
            "status of associated services. Use this agent when you need to assess "
            "error impact, determine severity levels, or verify service availability."
        ),
        worker=make_error_reasoner_agent(),
    )
    
    return workforce


def analyze_log_with_workforce(workforce: Workforce, log_data: str) -> str:
    """
    Analyze a log using the workforce orchestration system.
    
    Args:
        workforce: The configured Workforce instance
        log_data: The log data to analyze (can be JSON string or raw log text)
    
    Returns:
        The analysis result as a string
    """
    task = Task(
        content=(
            f"Analyze the following log entry and provide a comprehensive analysis. "
            f"Include historical context, severity assessment, service health checks, "
            f"and actionable recommendations.\n\n"
            f"Log data:\n{log_data}"
        ),
        id="log_analysis_task",
    )
    
    # Process the task through the workforce
    result_task = workforce.process_task(task=task)
    
    return result_task.result if result_task.result else "Analysis completed but no result returned."

