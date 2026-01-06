import json

from agent_system.tools import log_parser


def test_parses_json_log_fields():
    payload = {
        "level": "error",
        "service": "auth-service",
        "message": "failed to connect",
        "extra": {"a": 1},
    }
    result = log_parser.summarize_log(json.dumps(payload))
    assert result["level"] == "error"
    assert result["service"] == "auth-service"
    assert result["message"] == "failed to connect"
    assert result["raw"]["extra"] == {"a": 1}


def test_parses_message_fallbacks():
    payload = {"level": "warn", "service_name": "payment", "msg": "timeout"}
    result = log_parser.summarize_log(json.dumps(payload))
    assert result["service"] == "payment"
    assert result["message"] == "timeout"


def test_infers_level_for_plain_text():
    txt = "something WARN happened"
    result = log_parser.summarize_log(txt)
    assert result["level"] == "warning"
    assert "something" in result["message"]
