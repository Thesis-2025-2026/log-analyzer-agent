# Search for fixes related to a database error
from agent_system.tools.rag_tool import search_fixes_for_error, _get_vector_retriever
from dotenv import load_dotenv

load_dotenv()

print("Retrieving vector")
vector_retriever = _get_vector_retriever()
print("vector retrieved:")
print(vector_retriever)

query_error2 = "Database connection failed"
results2 = search_fixes_for_error(query_error2, top_k=3)

print(f"Searching for fixes related to: '{query_error2}'\n")
print(f"Found {len(results2)} similar fixes:\n")

for i, result in enumerate(results2, 1):
    if "error" in result:
        print(f"❌ {result['error']}")
        if "suggestion" in result:
            print(f"   Suggestion: {result['suggestion']}")
    elif "message" in result:
        print(f"ℹ️  {result['message']}")
        if "suggestion" in result:
            print(f"   Suggestion: {result['suggestion']}")
    else:
        print(f"Result {i}:")
        print(f"  Score: {result.get('score', 'N/A'):.4f}")
        print(f"  Content: {result.get('content', 'N/A')[:200]}...")
        if result.get('metadata'):
            print(f"  Metadata: {result['metadata']}")
    print()
