import os
from typing import Any, Dict, List, Optional
import psycopg2
import psycopg2.extras


def _db_params() -> Dict[str, Any]:
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "dbname": os.getenv("POSTGRES_DB", "logs_db"),
        "user": os.getenv("POSTGRES_USER", "logs_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "logs_pass"),
    }


def insert_report(level: Optional[str], service: Optional[str], content: str, raw_log: Optional[str]) -> Dict[str, Any]:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO reports (level, service, content, raw_log)
                VALUES (%s, %s, %s, %s)
                RETURNING id, created_at, level, service
                """,
                (level, service, content, raw_log),
            )
            row = cur.fetchone()
            return dict(row)


def list_reports(limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
    params = _db_params()
    with psycopg2.connect(**params) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, created_at, level, service, LEFT(content, 400) AS preview
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
                SELECT id, created_at, level, service, content, raw_log
                FROM reports
                WHERE id = %s
                """,
                (report_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

