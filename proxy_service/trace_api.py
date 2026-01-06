from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel, Field

from proxy_service.trace_db import TraceEvent, create_trace_store


_db = create_trace_store()
router = APIRouter(tags=["Tracing"])


class TraceInitRequest(BaseModel):
    trace_id: str
    root_service: Optional[str] = None
    root_report_id: Optional[str] = None


class TraceEventPayload(BaseModel):
    trace_id: str
    event_type: str = Field(..., description="agent | tool | http | ...")
    service_name: Optional[str] = None
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    parent_event_id: Optional[int] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    duration_ms: Optional[int] = None
    status: str = "ok"
    error: Optional[str] = None
    seq: Optional[int] = None
    agent_call: Optional[Dict[str, Any]] = None
    tool_call: Optional[Dict[str, Any]] = None
    http_call: Optional[Dict[str, Any]] = None


class TraceEventUpdatePayload(BaseModel):
    ended_at: Optional[str] = None
    duration_ms: Optional[int] = None
    status: Optional[str] = None
    error: Optional[str] = None
    tool_call: Optional[Dict[str, Any]] = None


@router.post("/traces/init")
async def init_trace(req: TraceInitRequest) -> Dict[str, Any]:
    _db.ensure_trace(req.trace_id, root_service=req.root_service, root_report_id=req.root_report_id)
    return {"success": True, "trace_id": req.trace_id}


@router.post("/traces/events")
async def ingest_events(payload: Any = Body(...)) -> Dict[str, Any]:
    """
    Ingest a single event or a list of events.
    """
    if isinstance(payload, list):
        events_raw = payload
    elif isinstance(payload, dict):
        events_raw = [payload]
    else:
        raise HTTPException(status_code=400, detail="Invalid payload (expected object or array)")

    inserted: List[int] = []
    for item in events_raw:
        event = TraceEventPayload.model_validate(item)
        entry_id = _db.insert_event(
            TraceEvent(
                trace_id=event.trace_id,
                event_type=event.event_type,
                service_name=event.service_name,
                agent_name=event.agent_name,
                tool_name=event.tool_name,
                parent_event_id=event.parent_event_id,
                started_at=event.started_at,
                ended_at=event.ended_at,
                duration_ms=event.duration_ms,
                status=event.status,
                error=event.error,
                seq=event.seq,
            ),
            agent_call_payload=event.agent_call,
            tool_call_payload=event.tool_call,
            http_call_payload=event.http_call,
        )
        inserted.append(entry_id)

    return {"success": True, "inserted": inserted, "count": len(inserted)}


@router.patch("/traces/events/{entry_id}")
async def update_event(entry_id: int, req: TraceEventUpdatePayload) -> Dict[str, Any]:
    ok = _db.update_event(
        entry_id,
        ended_at=req.ended_at,
        duration_ms=req.duration_ms,
        status=req.status,
        error=req.error,
        tool_call_payload=req.tool_call,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Trace event not found")
    return {"success": True, "updated": entry_id}


@router.get("/traces/{trace_id}")
async def get_trace(trace_id: str) -> Dict[str, Any]:
    trace = _db.get_trace(trace_id)
    if not trace:
        raise HTTPException(status_code=404, detail="Trace not found")
    entries = _db.list_entries(trace_id)
    return {"trace": trace, "entries": entries}


@router.get("/traces/agent-calls/{agent_call_id}")
async def get_agent_call(agent_call_id: int) -> Dict[str, Any]:
    row = _db.get_agent_call(agent_call_id)
    if not row:
        raise HTTPException(status_code=404, detail="Agent call not found")
    return row


@router.get("/traces/tool-calls/{tool_call_id}")
async def get_tool_call(tool_call_id: int) -> Dict[str, Any]:
    row = _db.get_tool_call(tool_call_id)
    if not row:
        raise HTTPException(status_code=404, detail="Tool call not found")
    return row


@router.get("/traces/http-calls/{http_call_id}")
async def get_http_call(http_call_id: int) -> Dict[str, Any]:
    row = _db.get_http_call(http_call_id)
    if not row:
        raise HTTPException(status_code=404, detail="HTTP call not found")
    return row
