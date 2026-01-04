from __future__ import annotations

import json
import os
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple, TypeVar

import requests


T = TypeVar("T")


_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_parent_event_id: ContextVar[Optional[int]] = ContextVar("parent_event_id", default=None)
_current_agent_name: ContextVar[Optional[str]] = ContextVar("current_agent_name", default=None)
_current_service_name: ContextVar[Optional[str]] = ContextVar("current_service_name", default=None)
_seq: ContextVar[int] = ContextVar("trace_seq", default=0)


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truncate_text(value: Optional[str], limit: int = 20_000) -> Optional[str]:
    if value is None:
        return None
    if len(value) <= limit:
        return value
    return value[:limit] + f"\n...[truncated {len(value) - limit} chars]"


def _safe_json(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [_safe_json(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _safe_json(v) for k, v in value.items()}
    return str(value)


def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(_safe_json(value), ensure_ascii=False)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _proxy_url() -> Optional[str]:
    url = os.getenv("PROXY_URL")
    enabled = os.getenv("PROXY_ENABLED", "true").lower() == "true"
    if not enabled:
        return None
    return url.strip() if url else None


def _emit_event(payload: Dict[str, Any]) -> Optional[int]:
    url = _proxy_url()
    if not url:
        return None
    try:
        resp = requests.post(
            f"{url}/traces/events",
            json=payload,
            timeout=0.5,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        inserted = data.get("inserted")
        if isinstance(inserted, list) and inserted:
            return int(inserted[0])
        return None
    except Exception:
        return None


def new_trace_id() -> str:
    return uuid.uuid4().hex


def set_trace_context(
    trace_id: Optional[str],
    *,
    parent_event_id: Optional[int] = None,
    service_name: Optional[str] = None,
    agent_name: Optional[str] = None,
) -> Tuple[Any, Any, Any, Any]:
    if trace_id is not None and trace_id != _trace_id.get():
        _seq.set(0)
    t1 = _trace_id.set(trace_id)
    t2 = _parent_event_id.set(parent_event_id)
    t3 = _current_service_name.set(service_name)
    t4 = _current_agent_name.set(agent_name)
    return t1, t2, t3, t4


def reset_trace_context(tokens: Tuple[Any, Any, Any, Any]) -> None:
    t1, t2, t3, t4 = tokens
    _trace_id.reset(t1)
    _parent_event_id.reset(t2)
    _current_service_name.reset(t3)
    _current_agent_name.reset(t4)


def get_trace_id() -> Optional[str]:
    return _trace_id.get()


def get_parent_event_id() -> Optional[int]:
    return _parent_event_id.get()


def get_current_agent_name() -> Optional[str]:
    return _current_agent_name.get()


def get_current_service_name() -> Optional[str]:
    return _current_service_name.get()


def next_seq() -> int:
    current = _seq.get()
    current += 1
    _seq.set(current)
    return current


def init_trace(trace_id: str, root_service: Optional[str] = None, root_report_id: Optional[str] = None) -> None:
    url = _proxy_url()
    if not url:
        return
    try:
        requests.post(
            f"{url}/traces/init",
            json={"trace_id": trace_id, "root_service": root_service, "root_report_id": root_report_id},
            timeout=0.5,
        )
    except Exception:
        return


def emit_simple_event(
    *,
    event_type: str,
    agent_name: Optional[str] = None,
    tool_name: Optional[str] = None,
    status: str = "ok",
    error: Optional[str] = None,
    parent_event_id: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Optional[int]:
    trace_id = get_trace_id()
    if not trace_id:
        return None
    payload: Dict[str, Any] = {
        "trace_id": trace_id,
        "event_type": event_type,
        "service_name": get_current_service_name(),
        "agent_name": agent_name,
        "tool_name": tool_name,
        "parent_event_id": parent_event_id if parent_event_id is not None else get_parent_event_id(),
        "started_at": _utcnow_iso(),
        "ended_at": _utcnow_iso(),
        "duration_ms": None,
        "status": status,
        "error": error,
        "seq": next_seq(),
    }
    if extra:
        payload.update(extra)
    return _emit_event(payload)


def record_agent_call(agent_name: str, prompt: str, response: str, *, status: str = "ok", error: Optional[str] = None) -> Optional[int]:
    trace_id = get_trace_id()
    if not trace_id:
        return None
    started_at = _utcnow_iso()
    ended_at = _utcnow_iso()
    payload = {
        "trace_id": trace_id,
        "event_type": "agent",
        "service_name": get_current_service_name(),
        "agent_name": agent_name,
        "parent_event_id": get_parent_event_id(),
        "started_at": started_at,
        "ended_at": ended_at,
        "duration_ms": None,
        "status": status,
        "error": error,
        "seq": next_seq(),
        "agent_call": {
            "prompt": _truncate_text(prompt),
            "response": _truncate_text(response),
        },
    }
    return _emit_event(payload)


def instrument_agent_step(agent_name: str, prompt: str, step_fn: Callable[[], Any]) -> Any:
    trace_id = get_trace_id()
    if not trace_id:
        return step_fn()

    started_at = _utcnow_iso()
    start = time.perf_counter()
    prev_agent = _current_agent_name.set(agent_name)
    try:
        result = step_fn()
        duration_ms = int((time.perf_counter() - start) * 1000)
        ended_at = _utcnow_iso()
        response_text = _truncate_text(_extract_response_text(result))
        payload = {
            "trace_id": trace_id,
            "event_type": "agent",
            "service_name": get_current_service_name(),
            "agent_name": agent_name,
            "parent_event_id": get_parent_event_id(),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "status": "ok",
            "seq": next_seq(),
            "agent_call": {
                "prompt": _truncate_text(prompt),
                "response": response_text,
            },
        }
        _emit_event(payload)
        return result
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        ended_at = _utcnow_iso()
        payload = {
            "trace_id": trace_id,
            "event_type": "agent",
            "service_name": get_current_service_name(),
            "agent_name": agent_name,
            "parent_event_id": get_parent_event_id(),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "status": "error",
            "error": str(e),
            "seq": next_seq(),
            "agent_call": {
                "prompt": _truncate_text(prompt),
                "response": None,
            },
        }
        _emit_event(payload)
        raise
    finally:
        _current_agent_name.reset(prev_agent)


def _extract_response_text(response: Any) -> str:
    if hasattr(response, "msg") and hasattr(response.msg, "content"):
        return getattr(response.msg, "content", "") or ""
    if hasattr(response, "content"):
        return getattr(response, "content", "") or ""
    if isinstance(response, str):
        return response
    return str(response)


def trace_tool(fn: Callable[..., T], *, tool_name: Optional[str] = None) -> Callable[..., T]:
    name = tool_name or getattr(fn, "__name__", "tool")

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        trace_id = get_trace_id()
        if not trace_id:
            return fn(*args, **kwargs)

        started_at = _utcnow_iso()
        start = time.perf_counter()
        try:
            result = fn(*args, **kwargs)
            duration_ms = int((time.perf_counter() - start) * 1000)
            ended_at = _utcnow_iso()
            payload = {
                "trace_id": trace_id,
                "event_type": "tool",
                "service_name": get_current_service_name(),
                "agent_name": get_current_agent_name(),
                "tool_name": name,
                "parent_event_id": get_parent_event_id(),
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "status": "ok",
                "seq": next_seq(),
                "tool_call": {
                    "input": _truncate_text(_safe_json_dumps({"args": args, "kwargs": kwargs})),
                    "output": _truncate_text(_safe_json_dumps(result)),
                },
            }
            _emit_event(payload)
            return result
        except Exception as e:
            duration_ms = int((time.perf_counter() - start) * 1000)
            ended_at = _utcnow_iso()
            payload = {
                "trace_id": trace_id,
                "event_type": "tool",
                "service_name": get_current_service_name(),
                "agent_name": get_current_agent_name(),
                "tool_name": name,
                "parent_event_id": get_parent_event_id(),
                "started_at": started_at,
                "ended_at": ended_at,
                "duration_ms": duration_ms,
                "status": "error",
                "error": str(e),
                "seq": next_seq(),
                "tool_call": {
                    "input": _truncate_text(_safe_json_dumps({"args": args, "kwargs": kwargs})),
                    "output": None,
                },
            }
            _emit_event(payload)
            raise

    return wrapper


def trace_tool_bound(
    fn: Callable[..., T],
    *,
    trace_id: Optional[str],
    parent_event_id: Optional[int],
    service_name: Optional[str],
    agent_name: Optional[str],
    tool_name: Optional[str] = None,
) -> Callable[..., T]:
    """
    Bind trace context to a tool function so it can emit trace events even if
    the tool is executed on a different thread without ContextVar propagation.
    """
    traced = trace_tool(fn, tool_name=tool_name)

    @wraps(fn)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        tokens = set_trace_context(
            trace_id,
            parent_event_id=parent_event_id,
            service_name=service_name,
            agent_name=agent_name,
        )
        try:
            return traced(*args, **kwargs)
        finally:
            reset_trace_context(tokens)

    return wrapper


def instrument_http_call(
    *,
    target_service: Optional[str],
    method: str,
    url: str,
    request_body: Any,
    call_fn: Callable[[], Any],
) -> Any:
    trace_id = get_trace_id()
    if not trace_id:
        return call_fn()

    started_at = _utcnow_iso()
    start = time.perf_counter()
    try:
        result = call_fn()
        duration_ms = int((time.perf_counter() - start) * 1000)
        ended_at = _utcnow_iso()
        status_code = getattr(result, "status_code", None)
        response_body: Optional[str] = None
        try:
            if hasattr(result, "text"):
                response_body = result.text
        except Exception:
            response_body = None
        payload = {
            "trace_id": trace_id,
            "event_type": "http",
            "service_name": get_current_service_name(),
            "agent_name": get_current_agent_name(),
            "tool_name": f"{method} {target_service or ''}".strip(),
            "parent_event_id": get_parent_event_id(),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "status": "ok" if (status_code is None or int(status_code) < 500) else "error",
            "seq": next_seq(),
            "http_call": {
                "target_service": target_service,
                "method": method,
                "url": url,
                "request_body": _truncate_text(_safe_json_dumps(request_body)),
                "response_body": _truncate_text(response_body),
                "status_code": status_code,
            },
        }
        _emit_event(payload)
        return result
    except Exception as e:
        duration_ms = int((time.perf_counter() - start) * 1000)
        ended_at = _utcnow_iso()
        payload = {
            "trace_id": trace_id,
            "event_type": "http",
            "service_name": get_current_service_name(),
            "agent_name": get_current_agent_name(),
            "tool_name": f"{method} {target_service or ''}".strip(),
            "parent_event_id": get_parent_event_id(),
            "started_at": started_at,
            "ended_at": ended_at,
            "duration_ms": duration_ms,
            "status": "error",
            "error": str(e),
            "seq": next_seq(),
            "http_call": {
                "target_service": target_service,
                "method": method,
                "url": url,
                "request_body": _truncate_text(_safe_json_dumps(request_body)),
                "response_body": None,
                "status_code": None,
            },
        }
        _emit_event(payload)
        raise
