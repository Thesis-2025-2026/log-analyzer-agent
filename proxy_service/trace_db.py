from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Protocol


@dataclass(frozen=True)
class TraceEvent:
    trace_id: str
    event_type: str  # "agent" | "tool" | "http" | ...
    service_name: Optional[str] = None
    agent_name: Optional[str] = None
    tool_name: Optional[str] = None
    parent_event_id: Optional[int] = None
    started_at: Optional[str] = None  # ISO-8601 UTC
    ended_at: Optional[str] = None  # ISO-8601 UTC
    duration_ms: Optional[int] = None
    status: str = "ok"  # "ok" | "error"
    error: Optional[str] = None
    agent_call_id: Optional[int] = None
    tool_call_id: Optional[int] = None
    http_call_id: Optional[int] = None
    seq: Optional[int] = None


class TraceStore(Protocol):
    def ensure_trace(self, trace_id: str, root_service: Optional[str] = None, root_report_id: Optional[str] = None) -> None: ...
    def insert_event(
        self,
        event: TraceEvent,
        agent_call_payload: Optional[Dict[str, Any]] = None,
        tool_call_payload: Optional[Dict[str, Any]] = None,
        http_call_payload: Optional[Dict[str, Any]] = None,
    ) -> int: ...
    def list_entries(self, trace_id: str) -> List[Dict[str, Any]]: ...
    def get_agent_call(self, agent_call_id: int) -> Optional[Dict[str, Any]]: ...
    def get_tool_call(self, tool_call_id: int) -> Optional[Dict[str, Any]]: ...
    def get_http_call(self, http_call_id: int) -> Optional[Dict[str, Any]]: ...
    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]: ...
    def update_event(
        self,
        entry_id: int,
        *,
        ended_at: Optional[str] = None,
        duration_ms: Optional[int] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
        tool_call_payload: Optional[Dict[str, Any]] = None,
    ) -> bool: ...


class PostgresTraceStore:
    def __init__(self, database_url: str):
        import psycopg2
        import psycopg2.extras
        from psycopg2.pool import ThreadedConnectionPool

        self._psycopg2 = psycopg2
        self._extras = psycopg2.extras
        self._pool = ThreadedConnectionPool(minconn=1, maxconn=10, dsn=database_url)

    def _get_conn(self):
        conn = self._pool.getconn()
        conn.autocommit = False
        return conn

    def _put_conn(self, conn):
        self._pool.putconn(conn)

    def ensure_trace(self, trace_id: str, root_service: Optional[str] = None, root_report_id: Optional[str] = None) -> None:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO traces (trace_id, root_service, root_report_id)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (trace_id) DO NOTHING
                    """,
                    (trace_id, root_service, root_report_id),
                )
            conn.commit()
        finally:
            self._put_conn(conn)

    def insert_event(
        self,
        event: TraceEvent,
        agent_call_payload: Optional[Dict[str, Any]] = None,
        tool_call_payload: Optional[Dict[str, Any]] = None,
        http_call_payload: Optional[Dict[str, Any]] = None,
    ) -> int:
        agent_call_id = event.agent_call_id
        tool_call_id = event.tool_call_id
        http_call_id = event.http_call_id

        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
                if event.trace_id:
                    cur.execute(
                        """
                        INSERT INTO traces (trace_id)
                        VALUES (%s)
                        ON CONFLICT (trace_id) DO NOTHING
                        """,
                        (event.trace_id,),
                    )

                if event.event_type == "agent" and agent_call_id is None:
                    payload = agent_call_payload or {}
                    cur.execute(
                        """
                        INSERT INTO agent_calls (
                            trace_id, service_name, agent_name, prompt, response,
                            started_at, ended_at, duration_ms, status, error
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s::timestamptz, %s::timestamptz, %s, %s, %s
                        )
                        RETURNING id
                        """,
                        (
                            event.trace_id,
                            event.service_name,
                            event.agent_name,
                            payload.get("prompt"),
                            payload.get("response"),
                            event.started_at,
                            event.ended_at,
                            event.duration_ms,
                            event.status,
                            event.error,
                        ),
                    )
                    agent_call_id = int(cur.fetchone()["id"])

                if event.event_type == "tool" and tool_call_id is None:
                    payload = tool_call_payload or {}
                    cur.execute(
                        """
                        INSERT INTO tool_calls (
                            trace_id, service_name, agent_name, tool_name, input, output,
                            started_at, ended_at, duration_ms, status, error
                        )
                        VALUES (
                            %s, %s, %s, %s, %s, %s,
                            %s::timestamptz, %s::timestamptz, %s, %s, %s
                        )
                        RETURNING id
                        """,
                        (
                            event.trace_id,
                            event.service_name,
                            event.agent_name,
                            event.tool_name,
                            payload.get("input"),
                            payload.get("output"),
                            event.started_at,
                            event.ended_at,
                            event.duration_ms,
                            event.status,
                            event.error,
                        ),
                    )
                    tool_call_id = int(cur.fetchone()["id"])

                if event.event_type == "http" and http_call_id is None:
                    payload = http_call_payload or {}
                    cur.execute(
                        """
                        INSERT INTO http_calls (
                            trace_id, service_name, target_service, method, url,
                            request_body, response_body, status_code,
                            started_at, ended_at, duration_ms, status, error
                        )
                        VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s,
                            %s::timestamptz, %s::timestamptz, %s, %s, %s
                        )
                        RETURNING id
                        """,
                        (
                            event.trace_id,
                            event.service_name,
                            payload.get("target_service"),
                            payload.get("method"),
                            payload.get("url"),
                            payload.get("request_body"),
                            payload.get("response_body"),
                            payload.get("status_code"),
                            event.started_at,
                            event.ended_at,
                            event.duration_ms,
                            event.status,
                            event.error,
                        ),
                    )
                    http_call_id = int(cur.fetchone()["id"])

                cur.execute(
                    """
                    INSERT INTO trace_entries (
                        trace_id, parent_event_id, event_type, service_name, agent_name, tool_name,
                        agent_call_id, tool_call_id, http_call_id,
                        started_at, ended_at, duration_ms, status, error, seq
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s,
                        %s, %s, %s,
                        %s::timestamptz, %s::timestamptz, %s, %s, %s, %s
                    )
                    RETURNING id
                    """,
                    (
                        event.trace_id,
                        event.parent_event_id,
                        event.event_type,
                        event.service_name,
                        event.agent_name,
                        event.tool_name,
                        agent_call_id,
                        tool_call_id,
                        http_call_id,
                        event.started_at,
                        event.ended_at,
                        event.duration_ms,
                        event.status,
                        event.error,
                        event.seq,
                    ),
                )
                entry_id = int(cur.fetchone()["id"])
            conn.commit()
            return entry_id
        finally:
            self._put_conn(conn)

    def list_entries(self, trace_id: str) -> List[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM trace_entries
                    WHERE trace_id = %s
                    ORDER BY
                        COALESCE(seq, id) ASC,
                        COALESCE(started_at, '-infinity'::timestamptz) ASC,
                        id ASC
                    """,
                    (trace_id,),
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        finally:
            self._put_conn(conn)

    def update_event(
        self,
        entry_id: int,
        *,
        ended_at: Optional[str] = None,
        duration_ms: Optional[int] = None,
        status: Optional[str] = None,
        error: Optional[str] = None,
        tool_call_payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, event_type, tool_call_id
                    FROM trace_entries
                    WHERE id = %s
                    """,
                    (entry_id,),
                )
                row = cur.fetchone()
                if not row:
                    conn.rollback()
                    return False

                # Update trace entry fields
                updates = []
                values: List[Any] = []
                if ended_at is not None:
                    updates.append("ended_at = %s::timestamptz")
                    values.append(ended_at)
                if duration_ms is not None:
                    updates.append("duration_ms = %s")
                    values.append(duration_ms)
                if status is not None:
                    updates.append("status = %s")
                    values.append(status)
                if error is not None:
                    updates.append("error = %s")
                    values.append(error)
                if updates:
                    values.append(entry_id)
                    cur.execute(
                        f"UPDATE trace_entries SET {', '.join(updates)} WHERE id = %s",
                        tuple(values),
                    )

                # Update tool payload when applicable
                if row.get("event_type") == "tool" and row.get("tool_call_id") and tool_call_payload is not None:
                    tool_updates = []
                    tool_values: List[Any] = []
                    if "output" in tool_call_payload:
                        tool_updates.append("output = %s")
                        tool_values.append(tool_call_payload.get("output"))
                    if ended_at is not None:
                        tool_updates.append("ended_at = %s::timestamptz")
                        tool_values.append(ended_at)
                    if duration_ms is not None:
                        tool_updates.append("duration_ms = %s")
                        tool_values.append(duration_ms)
                    if status is not None:
                        tool_updates.append("status = %s")
                        tool_values.append(status)
                    if error is not None:
                        tool_updates.append("error = %s")
                        tool_values.append(error)

                    if tool_updates:
                        tool_values.append(int(row["tool_call_id"]))
                        cur.execute(
                            f"UPDATE tool_calls SET {', '.join(tool_updates)} WHERE id = %s",
                            tuple(tool_values),
                        )

            conn.commit()
            return True
        finally:
            self._put_conn(conn)

    def get_agent_call(self, agent_call_id: int) -> Optional[Dict[str, Any]]:
        return self._get_one("agent_calls", agent_call_id)

    def get_tool_call(self, tool_call_id: int) -> Optional[Dict[str, Any]]:
        return self._get_one("tool_calls", tool_call_id)

    def get_http_call(self, http_call_id: int) -> Optional[Dict[str, Any]]:
        return self._get_one("http_calls", http_call_id)

    def _get_one(self, table: str, row_id: int) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
                cur.execute(f"SELECT * FROM {table} WHERE id = %s", (row_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            self._put_conn(conn)

    def get_trace(self, trace_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        try:
            with conn.cursor(cursor_factory=self._extras.RealDictCursor) as cur:
                cur.execute("SELECT * FROM traces WHERE trace_id = %s", (trace_id,))
                row = cur.fetchone()
                return dict(row) if row else None
        finally:
            self._put_conn(conn)


def create_trace_store() -> TraceStore:
    database_url = os.getenv("PROXY_TRACE_DATABASE_URL")
    if database_url:
        return PostgresTraceStore(database_url)
    raise RuntimeError("PROXY_TRACE_DATABASE_URL must be set for tracing")
