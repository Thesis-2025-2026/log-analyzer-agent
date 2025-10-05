import os
from dotenv import load_dotenv
from langchain.agents import initialize_agent, AgentType
from langchain_ollama import ChatOllama
from agent.tools import buildTools

load_dotenv()

def makeLlm():
    baseUrl = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    modelName = os.getenv("MODEL_NAME", "phi3:mini")
    return ChatOllama(model=modelName, temperature=0, base_url=baseUrl)

llm = makeLlm()
tools = buildTools()
agent = initialize_agent(
    tools=tools,
    llm=llm,
    agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
    verbose=True,
)

def handleManualLog(logText: str) -> str:
    prompt = (
        "You are a log-analysis assistant. Given the log payload, identify severity, "
        "probable root cause, and recommended next steps. Use tools when helpful.\n"
        f"Log text:\n{logText}"
    )
    result = agent.invoke(prompt)
    return result["output"]

def main():
    print("Manual Log Analysis Agent Ready (type 'quit' to exit')")
    while True:
        userLog = input("\nLog> ").strip()
        if userLog.lower() in {"quit", "exit"}:
            break
        analysis = handleManualLog(userLog)
        print(f"\nAnalysis:\n{analysis}")

if __name__ == "__main__":
    main()
