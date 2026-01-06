from agent_system.tools import cross_service_tool


def test_skip_self_call():
    cross_service_tool.CURRENT_SERVICE_NAME = "auth-service"
    cross_service_tool.set_visited_services([])
    msg = cross_service_tool.get_service_report("auth-service", "ctx")
    assert "avoid self-call" in msg.lower()


def test_skip_already_visited():
    cross_service_tool.CURRENT_SERVICE_NAME = "payment-service"
    cross_service_tool.set_visited_services(["order-service"])
    msg = cross_service_tool.get_service_report("order-service", "ctx")
    assert "already visited" in msg.lower()


def test_gather_skips_visited_and_calls_remaining(monkeypatch):
    called = []

    def fake_get_service_report(name, ctx):
        called.append(name)
        return f"report from {name}"

    cross_service_tool.set_visited_services(["svc1"])
    monkeypatch.setattr(cross_service_tool, "get_service_report", fake_get_service_report)

    output = cross_service_tool.gather_cross_service_reports("ctx", service_names="svc1,svc2,svc3")

    # svc1 was already visited, so only svc2 and svc3 should be called
    assert called == ["svc2", "svc3"]
    assert "svc2" in output and "svc3" in output
