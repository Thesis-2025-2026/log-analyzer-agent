"""
Main entry point for the agent system.
Supports both legacy single-agent mode and new Workforce-based orchestration.
"""
# Import settings first to configure logging before other imports
from agent_system.config import settings  # noqa: F401

from agent_system.core.registry import get_agent
from agent_system.core.storage import insert_report
from agent_system.tools.log_parser import summarize_log
from agent_system.agents.orchestrator import analyze_log_with_workforce
from camel.societies.workforce import Workforce


def analyze_log(agent_or_workforce, log_text: str) -> str:
    """
    Analyze a log using either a single agent or a Workforce.
    
    Args:
        agent_or_workforce: Either a ChatAgent or Workforce instance
        log_text: The log text to analyze
    
    Returns:
        Analysis result as a string
    """
    # Check if it's a Workforce instance
    if isinstance(agent_or_workforce, Workforce):
        return analyze_log_with_workforce(agent_or_workforce, log_text)
    
    # Legacy single-agent mode
    user_msg = (
        "Analyze this log. It should have some sort of log in form of a json string. "
        "You HAVE TO use the tools you are given.\n"
        f"RAW_LOG:\n{log_text}\n"
    )

    max_attempts = 4
    attempt = 0
    final_resp = None

    while attempt < max_attempts:
        resp = agent_or_workforce.step(user_msg)
        final_resp = resp
        tool_calls = (resp.info or {}).get("tool_calls") or []
        if tool_calls:
            break

        print("[guard] No tool call detected; retrying with strict tool-use instruction…")
        user_msg = (
            "Tool usage required: You did not call summarize_log on the RAW_LOG.\n"
            "Call summarize_log now on the json object that is somewhere between <LOG> and </LOG>.\n"
            "Dont forget that this text is human written it can have some regular language in it so be dire to look for json objects within it and use those json objects as the input for the tool not the entire text\n"
            f"<LOG>{log_text}</LOG>\n"
        )
        attempt += 1

    content = (getattr(final_resp.msg, "content", "") or "").strip()

    # Best-effort metadata extraction for storage using our local parser tool
    level = "unknown"
    service = os.getenv("SERVICE_NAME", "unknown")
    try:
        parsed = summarize_log(log_text)
        level = str(parsed.get("level", level))
        # Prefer configured service name (stable) if present.
        service = os.getenv("SERVICE_NAME", str(parsed.get("service", service)))
    except Exception:
        pass

    # Persist report
    try:
        insert_report(level=level, service=service, content=content, raw_log=log_text)
    except Exception as e:
        print(f"[warn] failed to store report: {e}")

    return content


def main():
    """Main CLI entry point."""
    import sys
    
    # Default to workforce, but allow legacy agent mode
    agent_name = sys.argv[1] if len(sys.argv) > 1 else "workforce"
    
    print(f"Using agent system: {agent_name}")
    agent_or_workforce = get_agent(agent_name)
    
    print("Manual Log Analysis. Type 'quit' to exit.")
    while True:
        user_log = input("\nLog> ").strip()
        if user_log.lower() in {"quit", "exit"}:
            break
        print("\nAnalyzing...")
        result = analyze_log(agent_or_workforce, user_log)
        print("\nAnalysis:\n" + result)


if __name__ == "__main__":
    main()
