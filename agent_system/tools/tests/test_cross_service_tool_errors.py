import json
from agent_system.tools import cross_service_tool


class DummyResp:
    def __init__(self, status_code, json_body):
        self.status_code = status_code
        self._json = json_body

    def json(self):
        return self._json


def test_get_service_report_missing_service(monkeypatch):
    def fake_get(url, timeout=10):
        return DummyResp(404, {})

    monkeypatch.setattr(cross_service_tool.requests, "get", fake_get)
    msg = cross_service_tool.get_service_report("missing-service", "ctx")
    assert "not found" in msg.lower()


def test_get_service_report_unhealthy(monkeypatch):
    def fake_get(url, timeout=10):
        return DummyResp(200, {"url": "http://svc", "status": "unhealthy"})

    monkeypatch.setattr(cross_service_tool.requests, "get", fake_get)
    msg = cross_service_tool.get_service_report("svc", "ctx")
    assert "unhealthy" in msg.lower()


def test_get_service_report_post_error(monkeypatch):
    def fake_get(url, timeout=10):
        return DummyResp(200, {"url": "http://svc", "status": "healthy", "capabilities": []})

    class PostResp:
        status_code = 500
        def json(self): return {}

    monkeypatch.setattr(cross_service_tool.requests, "get", fake_get)
    monkeypatch.setattr(cross_service_tool.requests, "post", lambda *a, **kw: PostResp())
    msg = cross_service_tool.get_service_report("svc", "ctx")
    assert "failed" in msg.lower()
