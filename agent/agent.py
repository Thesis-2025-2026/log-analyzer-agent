import os
from dotenv import load_dotenv
from openai import OpenAI
from agent.tools import build_tools

load_dotenv()


def make_client() -> OpenAI:
    base_url = os.getenv("OPENAI_BASE_URL", "http://localhost:11434/v1")
    api_key = os.getenv("OPENAI_API_KEY", "ollama")
    return OpenAI(base_url=base_url, api_key=api_key)


def handle_manual_log(client: OpenAI, log_text: str) -> str:
    tools = build_tools()
    summary = tools["summarize_log"](log_text)

    system_prompt = (
        "You are a log-analysis assistant. Identify severity, probable root cause, "
        "and recommended next steps. Be concise and actionable."
    )
    user_content = (
        f"Raw log:\n{log_text}\n\n"
        f"Tool summary:\n{summary}\n\n"
        f"Provide a concise analysis."
    )

    resp = client.chat.completions.create(
        model=os.getenv("MODEL_NAME", "phi3:mini"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ],
        temperature=0.1,
    )
    return resp.choices[0].message.content


def main():
    client = make_client()
    print("Manual Log Analysis (local Ollama via OpenAI API). Type 'quit' to exit.")
    while True:
        user_log = input("\nLog> ").strip()
        if user_log.lower() in {"quit", "exit"}:
            break
        analysis = handle_manual_log(client, user_log)
        print(f"\nAnalysis:\n{analysis}")


if __name__ == "__main__":
    main()
