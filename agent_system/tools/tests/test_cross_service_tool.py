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

