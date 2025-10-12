from agent_system.core.registry import get_agent


def analyze_log(agent, log_text: str) -> str:
    user_msg = (
        "Analyze this log. You MUST first call the tool `summarize_log(log_text=...)` "
        "to parse it before answering.\n"
        "After using the tool, return a compact JSON object with keys: "
        "`severity`, `root_cause`, `next_steps`.\n\n"
        f"RAW_LOG:\n{log_text}\n"
    )
    resp = agent.step(user_msg)
    return (getattr(resp.msg, "content", "") or "").strip()


def main():
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
