import pytest

from agent_api import app as app_module
from agent_api.app import create_app


@pytest.fixture
def client(monkeypatch):
    # Avoid real proxy/health monitor during tests
    class _DummyProxy:
        is_configured = False

        def register(self, *a, **kw): return False
        def unregister(self, *a, **kw): return None
        def discover_services(self, *a, **kw): return []
        def query_service(self, *a, **kw): return None

    dummy_proxy = _DummyProxy()
    monkeypatch.setattr(app_module, "proxy_client", dummy_proxy)
    monkeypatch.setattr(app_module, "register_with_proxy", lambda max_retries=3: False)
    monkeypatch.setattr(app_module.health_monitor, "start_threaded", lambda: None)
    monkeypatch.setattr(app_module.health_monitor, "stop", lambda: None)
    monkeypatch.setattr(app_module.atexit, "register", lambda *a, **kw: None)
    # Stub analyzer and storage
    monkeypatch.setattr(app_module, "analyze_log_with_main_agent", lambda *a, **kw: "mock reply")
    monkeypatch.setattr(app_module, "insert_report", lambda *a, **kw: None)

    app = create_app()
    app.config["TESTING"] = True
    return app.test_client()


def test_health_endpoint(client):
    """Health endpoint returns ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.get_json().get("status") == "ok"


def test_query_requires_body(client):
    """Query endpoint rejects empty payload."""
    resp = client.post("/api/query", json={})
    assert resp.status_code == 400


def test_query_happy_path(client):
    """Query endpoint responds with mock reply."""
    resp = client.post("/api/query", json={"query": "hello world"})
    assert resp.status_code == 200
    assert resp.get_json().get("reply") == "mock reply"


def test_list_reports_exists(client, monkeypatch):
    """List reports endpoint returns items list."""
    monkeypatch.setattr("agent_api.app.list_reports", lambda limit=50, offset=0: [{"id": 1}])
    resp = client.get("/api/reports")
    assert resp.status_code == 200
    assert isinstance(resp.get_json().get("items"), list)


def test_get_report_success(client, monkeypatch):
    """Report detail endpoint returns data."""
    monkeypatch.setattr("agent_api.app.get_report", lambda rid: {"id": rid, "content": "demo"})
    resp = client.get("/api/reports/1")
    assert resp.status_code == 200
    assert resp.get_json().get("id") == 1


def test_get_report_rejects_bad_id(client):
    """Report detail rejects non-numeric id."""
    resp = client.get("/api/reports/not-a-number")
    assert resp.status_code == 400
