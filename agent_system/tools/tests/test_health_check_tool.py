from agent_system.tools import health_check_tool
from requests.exceptions import RequestException


class DummyResp:
    def __init__(self, status_code):
        self.status_code = status_code


def test_health_check_http_alive(monkeypatch):
    calls = []

    def fake_get(url, timeout=5, allow_redirects=True):
        calls.append(url)
        return DummyResp(200)

    monkeypatch.setattr(health_check_tool.requests, "get", fake_get)
    result = health_check_tool.check_service_health("http://example.com", timeout=1)
    assert result["status"] == "alive"
    assert result["endpoint"].endswith("/health")
    assert calls  # ensure we called requests.get


def test_health_check_http_fallbacks(monkeypatch):
    # First two endpoints fail, third succeeds
    sequence = iter([
        RequestException("fail"),
        RequestException("fail"),
        DummyResp(404),  # still <500, treated as alive
    ])

    def fake_get(url, timeout=5, allow_redirects=True):
        val = next(sequence)
        if isinstance(val, Exception):
            raise val
        return val

    monkeypatch.setattr(health_check_tool.requests, "get", fake_get)
    res = health_check_tool.check_service_health("example.com", timeout=1)
    assert res["status"] == "alive"


def test_health_check_dead(monkeypatch):
    monkeypatch.setattr(
        health_check_tool.requests,
        "get",
        lambda *a, **kw: (_ for _ in ()).throw(RequestException("boom"))
    )
    # socket connect_ex failure -> dead; simulate by raising in socket as well
    class DummySock:
        def settimeout(self, t): pass
        def connect_ex(self, hostport): return 1
        def close(self): pass

    monkeypatch.setattr(health_check_tool.socket, "socket", lambda *a, **kw: DummySock())
    res = health_check_tool.check_service_health("http://bad-host.local", timeout=1)
    assert res["status"] == "dead"
