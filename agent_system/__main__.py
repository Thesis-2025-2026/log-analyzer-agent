from agent_system.core.registry import get_agent
from agent_system.core.storage import insert_report
from agent_system.tools.log_parser import summarize_log
from camel.logger import set_log_level


def analyze_log(agent, log_text: str) -> str:
    """Run the agent with a guard that re-prompts if tools were not used.

    Strategy
    - First attempt: send the analysis request including a RAW_LOG hint.
    - If the model does not trigger a tool call, send a strict follow-up that
      instructs it to call summarize_log with the exact payload.
    - Return the final content regardless, so the CLI remains responsive.
    """

    # Initial prompt with a RAW_LOG hint to nudge tool usage
    user_msg = (
        "Analyze this log. It should have some sort of log in form of a json string. "
        "You HAVE TO use the tools you are given.\n"
        f"RAW_LOG:\n{log_text}\n"
    )

    max_attempts = 4
    attempt = 0
    final_resp = None

    while attempt < max_attempts:
        resp = agent.step(user_msg)
        final_resp = resp
        tool_calls = (resp.info or {}).get("tool_calls") or []
        if tool_calls:
            # Tool(s) were used; stop retrying
            break

        # Prepare a strict follow-up to force a tool call on the next attempt
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
    service = "unknown"
    try:
        parsed = summarize_log(log_text)
        level = str(parsed.get("level", level))
        service = str(parsed.get("service", service))
    except Exception:
        pass

    # Persist report
    try:
        insert_report(level=level, service=service, content=content, raw_log=log_text)
    except Exception as e:
        # Non-fatal: keep CLI/API responsive even if DB is down
        print(f"[warn] failed to store report: {e}")

    return content


def main():
    # Ensure CAMEL logs are visible in console
    #set_log_level("INFO")
    agent = get_agent("log_analysis")  # switch agent by name here
    print("Manual Log Analysis. Type 'quit' to exit.")
    while True:
        user_log = input("\nLog> ").strip()
        if user_log.lower() in {"quit", "exit"}:
            break
        print("\nAnalyzing...")
        print("\nAnalysis:\n" + analyze_log(agent, user_log))


if __name__ == "__main__":
    main()
