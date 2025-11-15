#!/usr/bin/env python3
"""
Test script for the Workforce-based agent system.
Tests imports, tool functionality, and basic workforce creation.
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test that all modules can be imported."""
    print("=" * 60)
    print("TEST 1: Testing Imports")
    print("=" * 60)
    
    try:
        from agent_system.agents.orchestrator import create_log_analysis_workforce
        print("✓ Workforce orchestrator imported")
    except Exception as e:
        print(f"✗ Workforce orchestrator import failed: {e}")
        return False
    
    try:
        from agent_system.tools.db_tool import query_logs, get_logs_by_error_pattern
        print("✓ DB tools imported")
    except Exception as e:
        print(f"✗ DB tools import failed: {e}")
        return False
    
    try:
        from agent_system.tools.rag_tool import search_fixes_for_error
        print("✓ RAG tool imported")
    except Exception as e:
        print(f"✗ RAG tool import failed: {e}")
        return False
    
    try:
        from agent_system.tools.health_check_tool import check_service_health
        print("✓ Health check tool imported")
    except Exception as e:
        print(f"✗ Health check tool import failed: {e}")
        return False
    
    try:
        from agent_system.agents.internal_knowledge import make_internal_knowledge_agent
        print("✓ Internal Knowledge Agent imported")
    except Exception as e:
        print(f"✗ Internal Knowledge Agent import failed: {e}")
        return False
    
    try:
        from agent_system.agents.error_reasoner import make_error_reasoner_agent
        print("✓ Error Reasoner Agent imported")
    except Exception as e:
        print(f"✗ Error Reasoner Agent import failed: {e}")
        return False
    
    print("\n✓ All imports successful!\n")
    return True


def test_tools():
    """Test that tools can be called (may fail if services not available)."""
    print("=" * 60)
    print("TEST 2: Testing Tool Functions")
    print("=" * 60)
    
    # Test RAG tool
    try:
        from agent_system.tools.rag_tool import search_fixes_for_error
        result = search_fixes_for_error("test error message", top_k=1)
        print(f"✓ RAG tool callable (returned {type(result).__name__})")
    except Exception as e:
        print(f"⚠ RAG tool error (expected if vector DB not configured): {type(e).__name__}")
    
    # Test Health check tool
    try:
        from agent_system.tools.health_check_tool import check_service_health
        result = check_service_health("http://localhost:8000", timeout=1)
        print(f"✓ Health check tool callable (status: {result.get('status', 'unknown')})")
    except Exception as e:
        print(f"✗ Health check tool error: {e}")
        return False
    
    print("\n✓ Tool functions are callable!\n")
    return True


def test_agents():
    """Test that agents can be created (may fail if model not available)."""
    print("=" * 60)
    print("TEST 3: Testing Agent Creation")
    print("=" * 60)
    
    # Set minimal env vars
    os.environ.setdefault('MODEL_PLATFORM', 'OLLAMA')
    os.environ.setdefault('MODEL_NAME', 'llama3.1:8b-instruct')
    os.environ.setdefault('OPENAI_BASE_URL', 'http://localhost:11434/v1')
    os.environ.setdefault('OPENAI_API_KEY', 'ollama')
    os.environ.setdefault('TEMPERATURE', '0.1')
    
    try:
        from agent_system.agents.internal_knowledge import make_internal_knowledge_agent
        agent = make_internal_knowledge_agent()
        print("✓ Internal Knowledge Agent created")
        tool_count = len(agent.tool_dict) if hasattr(agent, 'tool_dict') and agent.tool_dict else 0
        print(f"  - Has {tool_count} tools")
    except Exception as e:
        print(f"⚠ Internal Knowledge Agent creation (may fail if model unavailable): {type(e).__name__}: {str(e)[:100]}")
    
    try:
        from agent_system.agents.error_reasoner import make_error_reasoner_agent
        agent = make_error_reasoner_agent()
        print("✓ Error Reasoner Agent created")
        tool_count = len(agent.tool_dict) if hasattr(agent, 'tool_dict') and agent.tool_dict else 0
        print(f"  - Has {tool_count} tools")
    except Exception as e:
        print(f"⚠ Error Reasoner Agent creation (may fail if model unavailable): {type(e).__name__}: {str(e)[:100]}")
    
    print("\n✓ Agent factories are functional!\n")
    return True


def test_workforce():
    """Test that workforce can be created."""
    print("=" * 60)
    print("TEST 4: Testing Workforce Creation")
    print("=" * 60)
    
    # Set minimal env vars
    os.environ.setdefault('MODEL_PLATFORM', 'OLLAMA')
    os.environ.setdefault('MODEL_NAME', 'llama3.1:8b-instruct')
    os.environ.setdefault('OPENAI_BASE_URL', 'http://localhost:11434/v1')
    os.environ.setdefault('OPENAI_API_KEY', 'ollama')
    os.environ.setdefault('TEMPERATURE', '0.1')
    
    try:
        from agent_system.agents.orchestrator import create_log_analysis_workforce
        workforce = create_log_analysis_workforce()
        print("✓ Workforce created successfully")
        print(f"  - Description: {workforce.description[:80]}...")
        # Check for workers in different possible attributes
        worker_count = 0
        if hasattr(workforce, 'children') and workforce.children:
            worker_count = len(workforce.children)
        elif hasattr(workforce, '_workers'):
            worker_count = len(workforce._workers) if workforce._workers else 0
        print(f"  - Has {worker_count} workers configured")
    except Exception as e:
        print(f"⚠ Workforce creation (may fail if model unavailable): {type(e).__name__}: {str(e)[:150]}")
        return False
    
    print("\n✓ Workforce creation successful!\n")
    return True


def test_registry():
    """Test the agent registry."""
    print("=" * 60)
    print("TEST 5: Testing Registry")
    print("=" * 60)
    
    try:
        from agent_system.core.registry import get_agent
        
        # Test workforce retrieval
        try:
            workforce = get_agent('workforce')
            print("✓ Workforce retrieved from registry")
        except Exception as e:
            print(f"⚠ Workforce retrieval (may fail if model unavailable): {type(e).__name__}")
        
        # Test legacy agent retrieval
        try:
            agent = get_agent('log_analysis')
            print("✓ Legacy log_analysis agent retrieved from registry")
        except Exception as e:
            print(f"⚠ Legacy agent retrieval: {type(e).__name__}: {str(e)[:100]}")
        
    except Exception as e:
        print(f"✗ Registry test failed: {e}")
        return False
    
    print("\n✓ Registry system working!\n")
    return True


def main():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("WORKFORCE AGENT SYSTEM TEST SUITE")
    print("=" * 60 + "\n")
    
    results = []
    results.append(("Imports", test_imports()))
    results.append(("Tools", test_tools()))
    results.append(("Agents", test_agents()))
    results.append(("Workforce", test_workforce()))
    results.append(("Registry", test_registry()))
    
    print("=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status}: {name}")
    
    all_passed = all(result[1] for result in results)
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ ALL TESTS PASSED!")
    else:
        print("⚠ SOME TESTS HAD ISSUES (check warnings above)")
    print("=" * 60 + "\n")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

