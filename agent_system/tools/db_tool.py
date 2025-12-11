"""
DB Tool for querying the SQL database to retrieve additional logs and context.
"""
import os
from typing import Any, Dict, List, Optional
import psycopg2
import psycopg2.extras


def _get_db_params() -> Dict[str, Any]:
    """Get database connection parameters from environment variables."""
    return {
        "host": os.getenv("POSTGRES_HOST", "localhost"),
        "port": int(os.getenv("POSTGRES_PORT", "5433")),
        "dbname": os.getenv("POSTGRES_DB", "logs_db"),
        "user": os.getenv("POSTGRES_USER", "logs_user"),
        "password": os.getenv("POSTGRES_PASSWORD", "logs_pass"),
    }


def query_logs(
    level: Optional[str] = None,
    service: Optional[str] = None,
    limit: int = 10,
    hours_back: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Query logs from the database with optional filters.
    
    Use this tool to retrieve historical logs that match specific criteria.
    This helps provide context for error analysis by finding similar past occurrences.
    
    Args:
        level: Filter by log level (e.g., 'error', 'warning', 'info')
        service: Filter by service name
        limit: Maximum number of logs to return (default: 10, max: 100)
        hours_back: Only return logs from the last N hours (optional)
    
    Returns:
        A list of dictionaries containing log entries with fields:
        - id: log entry ID
        - timestamp: when the log was created
        - level: log level
        - raw: the raw log data (JSON)
    """
    params = _get_db_params()
    limit = min(max(1, limit), 100)  # Clamp between 1 and 100
    
    conditions = []
    values = []
    
    if level:
        conditions.append("level = %s")
        values.append(level)
    
    if service:
        # Service might be in the raw JSONB field
        conditions.append("(raw->>'service' = %s OR raw->>'service_name' = %s)")
        values.extend([service, service])
    
    if hours_back:
        # Use make_interval() function for proper parameterization
        # This avoids SQL injection and handles the interval correctly
        conditions.append("timestamp >= NOW() - make_interval(hours => %s)")
        values.append(hours_back)
    
    where_clause = " AND ".join(conditions) if conditions else "1=1"
    
    query = f"""
        SELECT id, timestamp, level, raw
        FROM logs
        WHERE {where_clause}
        ORDER BY timestamp DESC
        LIMIT %s
    """
    values.append(limit)
    
    try:
        with psycopg2.connect(**params) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, values)
                rows = cur.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        return [{"error": f"Database query failed: {str(e)}"}]


def get_logs_by_error_pattern(error_message: str, limit: int = 10) -> List[Dict[str, Any]]:
    """
    Search for logs containing similar error messages or patterns.
    
    This tool performs a text search in log messages to find related errors.
    Useful for finding historical occurrences of similar issues.
    
    Args:
        error_message: The error message or pattern to search for
        limit: Maximum number of logs to return (default: 10, max: 50)
    
    Returns:
        A list of dictionaries containing matching log entries
    """
    params = _get_db_params()
    limit = min(max(1, limit), 50)
    
    query = """
        SELECT id, timestamp, level, raw
        FROM logs
        WHERE raw::text ILIKE %s
           OR (raw->>'message')::text ILIKE %s
        ORDER BY timestamp DESC
        LIMIT %s
    """
    pattern = f"%{error_message}%"
    
    try:
        with psycopg2.connect(**params) as conn:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(query, [pattern, pattern, limit])
                rows = cur.fetchall()
                return [dict(row) for row in rows]
    except Exception as e:
        return [{"error": f"Database search failed: {str(e)}"}]

