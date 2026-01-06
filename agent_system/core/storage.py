import os
import logging
from typing import Any, Dict, List, Optional
import psycopg2
import psycopg2.extras
from psycopg2.extras import Json as PgJson

logger = logging.getLogger(__name__)
def _db_params() -> Dict[str, Any]:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "dbname": os.getenv("POSTGRES_DB", "logs_db"),
        "user": os.getenv("POSTGRES_USER", "logs_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "logs_pass"),
    }


def insert_report(
    level: Optional[str],
    service: Optional[str],
    content: str,
    raw_log: Optional[str],
    trace_id: Optional[str] = None,
    title: Optional[str] = None,
) -> Dict[str, Any]:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO reports (level, service, title, trace_id, content, raw_log)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, created_at, level, service, title, trace_id
                """,
                (level, service, title, trace_id, content, raw_log),
            )
            row = cur.fetchone()
            return dict(row)


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, created_at, level, service, title, trace_id, LEFT(content, 400) AS preview
                FROM reports
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, offset),
            )
            rows = cur.fetchall()
            return [dict(r) for r in rows]


def get_report(report_id: int) -> Optional[Dict[str, Any]]:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, created_at, level, service, title, trace_id, content, raw_log
                FROM reports
                WHERE id = %s
                """,
                (report_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def delete_report(report_id: int) -> bool:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reports WHERE id = %s", (report_id,))
            return cur.rowcount > 0


def count_reports() -> int:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM reports")
            row = cur.fetchone()
            return int(row[0]) if row else 0


def insert_log(level: Optional[str], raw: Dict[str, Any]) -> Dict[str, Any]:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO logs (level, raw)
                VALUES (%s, %s)
                RETURNING id, timestamp, level
                """,
                (level, PgJson(raw)),
            )
            row = cur.fetchone()
            return dict(row)
