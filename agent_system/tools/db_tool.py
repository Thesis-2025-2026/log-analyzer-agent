"""
DB Tools for querying logs with read-only SQL access.
"""
from __future__ import annotations

import os
import re
from typing import Any, Dict, List

import psycopg2
import psycopg2.extras

_READONLY_PATTERN = re.compile(r"^\s*(with|select)\b", re.IGNORECASE)
_FORBIDDEN_PATTERN = re.compile(
    r"\b(insert|update|delete|drop|alter|create|truncate|grant|revoke)\b",
    re.IGNORECASE,
)


def _get_db_params() -> Dict[str, Any]:
    """Get database connection parameters from environment variables."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "dbname": os.getenv("POSTGRES_DB", "logs_db"),
        "user": os.getenv("POSTGRES_USER", "logs_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "logs_pass"),
    }


def query_logs_sql(sql: str, limit: int = 100) -> Dict[str, Any]:
    """
    Execute a read-only SELECT query against the logs database.

    This tool accepts a SELECT/WITH query and returns up to `limit` rows.
    It rejects any non-SELECT statements and disallows multiple statements.
    """
    if not isinstance(sql, str) or not sql.strip():
        return {"error": "SQL query must be a non-empty string."}

    cleaned = sql.strip().rstrip(";")
    if ";" in cleaned:
        return {"error": "Only a single SELECT statement is allowed."}
    if not _READONLY_PATTERN.match(cleaned):
        return {"error": "Only SELECT/WITH queries are allowed."}
    if _FORBIDDEN_PATTERN.search(cleaned):
        return {"error": "Write operations are not allowed in this tool."}

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 100
    limit = min(max(1, limit), 100)
    wrapped = f"SELECT * FROM ({cleaned}) AS q LIMIT {limit}"

    try:
        with psycopg2.connect(**_get_db_params()) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(wrapped)
                rows = cur.fetchall()
                return {
                    "items": [dict(row) for row in rows],
                    "limit": limit,
                    "returned": len(rows),
                }
    except Exception as e:
        return {"error": f"Database query failed: {str(e)}"}


def query_logs_by_time_range(start_ts: str, end_ts: str, limit: int = 100) -> Dict[str, Any]:
    """
    Fetch logs between start_ts and end_ts (inclusive), ordered from earliest to latest.

    Returns up to `limit` logs starting from start_ts. If more logs exist, a note
    is included indicating additional logs between the last returned log and end_ts.
    """
    if not isinstance(start_ts, str) or not start_ts.strip():
        return {"error": "start_ts must be a non-empty timestamp string."}
    if not isinstance(end_ts, str) or not end_ts.strip():
        return {"error": "end_ts must be a non-empty timestamp string."}

    try:
        limit = int(limit)
    except (TypeError, ValueError):
        limit = 100
    limit = min(max(1, limit), 100)
    params = _get_db_params()

    try:
        with psycopg2.connect(**params) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, timestamp, level, raw
                    FROM logs
                    WHERE timestamp >= %s AND timestamp <= %s
                    ORDER BY timestamp ASC
                    LIMIT %s
                    """,
                    (start_ts, end_ts, limit),
                )
                rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM logs
                    WHERE timestamp >= %s AND timestamp <= %s
                    """,
                    (start_ts, end_ts),
                )
                count_row = cur.fetchone() or {}
                total_val = count_row.get("total", 0)
                total = int(total_val) if total_val is not None else 0

        note = None
        if total > limit:
            last_ts = rows[-1]["timestamp"] if rows else None
            if last_ts:
                note = (
                    f"More than {limit} logs between {start_ts} and {end_ts}. "
                    f"Returned the first {limit} from the start; "
                    f"{total - limit} more logs exist between {last_ts} and {end_ts}."
                )
            else:
                note = (
                    f"More than {limit} logs between {start_ts} and {end_ts}. "
                    f"Returned the first {limit} from the start."
                )

        return {
            "items": [dict(row) for row in rows],
            "start_ts": start_ts,
            "end_ts": end_ts,
            "returned": len(rows),
            "total": total,
            "note": note,
        }
    except Exception as e:
        return {"error": f"Database query failed: {str(e)}"}
