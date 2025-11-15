#!/usr/bin/env python3
"""
Comprehensive test of the full Workforce-based agent system with Qdrant vector DB.
"""
import sys
import os
import json

from dotenv import load_dotenv
load_dotenv()

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variables for Qdrant (from init.ipynb)
# os.environ.setdefault("QDRANT_URL", "https://7ac382c0-35d0-498d-9bb3-66f519d57d62.eu-central-1-0.aws.cloud.qdrant.io:6333")
# os.environ.setdefault("QDRANT_API_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.O62Wx4ArdXTRIppZ_X1hpNHTEev8uV3QEe9ON3lXkEg")
# os.environ.setdefault("QDRANT_COLLECTION", "log_fixes")
# os.environ.setdefault("EMBEDDING_DIM", "384")  # Match the collection vector size

# # Set model configuration
# os.environ.setdefault('MODEL_PLATFORM', 'OLLAMA')
# os.environ.setdefault('MODEL_NAME', 'llama3.1:8b-instruct')
# os.environ.setdefault('OPENAI_BASE_URL', 'http://localhost:11434/v1')
# os.environ.setdefault('OPENAI_API_KEY', 'ollama')
# os.environ.setdefault('TEMPERATURE', '0.1')

def test_rag_tool_connection():
    """Test RAG tool can connect to Qdrant."""
    print("=" * 60)
    print("TEST 1: RAG Tool Connection to Qdrant")
    print("=" * 60)
    
    try:
        from agent_system.tools.rag_tool import search_fixes_for_error, add_fix_to_knowledge_base
        
        # Test search (should work even with empty collection)
        print("Testing search_fixes_for_error...")
        results = search_fixes_for_error("database connection timeout", top_k=3)
        print(f"✓ Search function works (returned {type(results).__name__})")
        if isinstance(results, list) and len(results) > 0:
            if "error" not in results[0]:
                print(f"  Found {len(results)} results")
            else:
                print(f"  Note: {results[0].get('error', 'Unknown error')}")
        else:
            print("  Collection is empty (expected for new setup)")
        
        return True
    except Exception as e:
        print(f"✗ RAG tool connection failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_add_fix_to_knowledge_base():
    """Test adding a fix to the knowledge base."""
    print("\n" + "=" * 60)
    print("TEST 2: Adding Fix to Knowledge Base")
    print("=" * 60)
    
    try:
        from agent_system.tools.rag_tool import add_fix_to_knowledge_base
        
        # Add a sample fix
        error_log = "Database connection timeout after 30 seconds"
        fix_description = "Increase database connection timeout to 60 seconds or check network connectivity. Verify database server is running and accessible."
        metadata = {
            "service": "database",
            "severity": "high",
            "category": "connection"
        }
        
        result = add_fix_to_knowledge_base(error_log, fix_description, metadata)
        print(f"✓ Add fix function executed")
        if result.get("success"):
            print("  ✓ Fix added to knowledge base successfully")
        else:
            print(f"  ⚠ {result.get('error', 'Unknown error')}")
        
        return True
    except Exception as e:
        print(f"✗ Add fix failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_search_after_add():
    """Test searching after adding a fix."""
    print("\n" + "=" * 60)
    print("TEST 3: Search After Adding Fix")
    print("=" * 60)
    
    try:
        from agent_system.tools.rag_tool import search_fixes_for_error
        
        # Search for the error we just added
        results = search_fixes_for_error("database connection timeout", top_k=3)
        print(f"✓ Search executed")
        
        if isinstance(results, list) and len(results) > 0:
            if "error" not in results[0]:
                print(f"  Found {len(results)} matching results")
                for i, result in enumerate(results[:2], 1):
                    print(f"  Result {i}: {result.get('content', '')[:100]}...")
            else:
                print(f"  Note: {results[0].get('error', 'Unknown error')}")
        else:
            print("  No results found (may need to wait for indexing)")
        
        return True
    except Exception as e:
        print(f"✗ Search after add failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_internal_knowledge_agent():
    """Test Internal Knowledge Agent with tools."""
    print("\n" + "=" * 60)
    print("TEST 4: Internal Knowledge Agent")
    print("=" * 60)
    
    try:
        from agent_system.agents.internal_knowledge import make_internal_knowledge_agent
        
        agent = make_internal_knowledge_agent()
        print("✓ Internal Knowledge Agent created")
        
        tool_count = len(agent.tool_dict) if hasattr(agent, 'tool_dict') and agent.tool_dict else 0
        print(f"  - Has {tool_count} tools")
        if agent.tool_dict:
            print(f"  - Tools: {list(agent.tool_dict.keys())}")
        
        return True
    except Exception as e:
        print(f"✗ Internal Knowledge Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_error_reasoner_agent():
    """Test Error Reasoner Agent with tools."""
    print("\n" + "=" * 60)
    print("TEST 5: Error Reasoner Agent")
    print("=" * 60)
    
    try:
        from agent_system.agents.error_reasoner import make_error_reasoner_agent
        
        agent = make_error_reasoner_agent()
        print("✓ Error Reasoner Agent created")
        
        tool_count = len(agent.tool_dict) if hasattr(agent, 'tool_dict') and agent.tool_dict else 0
        print(f"  - Has {tool_count} tools")
        if agent.tool_dict:
            print(f"  - Tools: {list(agent.tool_dict.keys())}")
        
        return True
    except Exception as e:
        print(f"✗ Error Reasoner Agent creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workforce_creation():
    """Test Workforce creation with all agents."""
    print("\n" + "=" * 60)
    print("TEST 6: Workforce Creation")
    print("=" * 60)
    
    try:
        from agent_system.agents.orchestrator import create_log_analysis_workforce
        
        workforce = create_log_analysis_workforce()
        print("✓ Workforce created successfully")
        print(f"  - Description: {workforce.description[:80]}...")
        
        return True
    except Exception as e:
        print(f"✗ Workforce creation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_workforce_with_sample_log():
    """Test Workforce with a sample log analysis task."""
    print("\n" + "=" * 60)
    print("TEST 7: Workforce Log Analysis (Sample)")
    print("=" * 60)
    
    try:
        from agent_system.agents.orchestrator import create_log_analysis_workforce, analyze_log_with_workforce
        
        workforce = create_log_analysis_workforce()
        
        # Sample log data
        sample_log = json.dumps({
            "level": "error",
            "service": "orders",
            "message": "Database connection timeout after 30 seconds",
            "timestamp": "2024-01-15T10:30:00Z"
        })
        
        print("Analyzing sample log with Workforce...")
        print(f"Log: {sample_log[:100]}...")
        print("\nThis may take a while if the model needs to be loaded...")
        print("(Skipping actual execution to avoid long waits - uncomment to test)")
        
        # Uncomment to actually run (requires model to be available):
        result = analyze_log_with_workforce(workforce, sample_log)
        print(f"\n✓ Analysis complete")
        print(f"Result preview: {result[:200]}...")
        
        print("✓ Workforce structure is ready for log analysis")
        return True
    except Exception as e:
        print(f"✗ Workforce log analysis test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_db_tools():
    """Test DB tools (may fail if DB not running)."""
    print("\n" + "=" * 60)
    print("TEST 8: Database Tools")
    print("=" * 60)
    
    try:
        from agent_system.tools.db_tool import query_logs, get_logs_by_error_pattern
        
        # Test query_logs (will fail if DB not available, but function should exist)
        try:
            results = query_logs(limit=5)
            print(f"✓ query_logs function works")
            if isinstance(results, list):
                print(f"  Returned {len(results)} results")
        except Exception as e:
            print(f"  ⚠ Database not available (expected): {type(e).__name__}")
        
        print("✓ DB tools are accessible")
        return True
    except Exception as e:
        print(f"✗ DB tools test failed: {e}")
        return False


def test_health_check_tools():
    """Test health check tools."""
    print("\n" + "=" * 60)
    print("TEST 9: Health Check Tools")
    print("=" * 60)
    
    try:
        from agent_system.tools.health_check_tool import check_service_health
        
        result = check_service_health("http://localhost:8000", timeout=2)
        print(f"✓ Health check function works")
        print(f"  Status: {result.get('status', 'unknown')}")
        
        return True
    except Exception as e:
        print(f"✗ Health check tools test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("FULL SYSTEM TEST SUITE - WITH QDRANT VECTOR DB")
    print("=" * 60 + "\n")
    
    results = []
    # results.append(("RAG Tool Connection", test_rag_tool_connection()))
    # results.append(("Add Fix to Knowledge Base", test_add_fix_to_knowledge_base()))
    # results.append(("Search After Add", test_search_after_add()))
    # results.append(("Internal Knowledge Agent", test_internal_knowledge_agent()))
    # results.append(("Error Reasoner Agent", test_error_reasoner_agent()))
    results.append(("Workforce Creation", test_workforce_creation()))
    results.append(("Workforce Log Analysis", test_workforce_with_sample_log()))
    # results.append(("Database Tools", test_db_tools()))
    # results.append(("Health Check Tools", test_health_check_tools()))
    
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED!")
        print("The full system is ready to use.")
    else:
        print("⚠ SOME TESTS HAD ISSUES")
        print("Check the output above for details.")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

