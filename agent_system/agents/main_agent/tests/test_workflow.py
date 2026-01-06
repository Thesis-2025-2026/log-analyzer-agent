import pytest

from agent_system.agents.main_agent import workflow


class DummyAgent:
    def __init__(self, responses):
        self.responses = responses
        self.calls = 0

    def step(self, prompt):
        self.calls += 1
        resp = self.responses[self.calls - 1]
        if isinstance(resp, Exception):
            raise resp
        return resp


class DummyResp:
    def __init__(self, content):
        self.msg = type("Msg", (), {"content": content})


def test_workflow_success(monkeypatch):
    dummy = DummyAgent([DummyResp("ok")])
    import agent_system.agents.main_agent.workflow as wf
    monkeypatch.setattr(wf, "make_main_agent", lambda: dummy)
    out = workflow.analyze_log_with_main_agent("log text", max_retries=2, visited_services=["svc1"])
    assert "LOG ANALYSIS REPORT" in out
    assert dummy.calls == 1


def test_workflow_retries_and_formats_error(monkeypatch):
    dummy = DummyAgent([Exception("boom"), Exception("boom2")])
    import agent_system.agents.main_agent.workflow as wf
    monkeypatch.setattr(wf, "make_main_agent", lambda: dummy)
    out = workflow.analyze_log_with_main_agent("log text", max_retries=2)
    assert "LOG ANALYSIS REPORT - ERROR" in out
