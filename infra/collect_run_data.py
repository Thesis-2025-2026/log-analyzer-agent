#!/usr/bin/env python3
"""
Polls PostgreSQL databases for a new auth-service report and its associated
trace data, then saves a structured JSON file for one experiment run.
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone

import psycopg2
import psycopg2.extras

POLL_INTERVAL = 3  # seconds between DB checks

DB_AUTH = {
    "host": os.getenv("AUTH_PG_HOST", "localhost"),
    "port": int(os.getenv("AUTH_PG_PORT", "5435")),
    "dbname": "auth_logs",
    "user": "logs_user",
    "password": "logs_pass",
}

DB_DEPLOYMENTS = {
    "host": os.getenv("DEPLOY_PG_HOST", "localhost"),
    "port": int(os.getenv("DEPLOY_PG_PORT", "5436")),
    "dbname": "deployments_logs",
    "user": "logs_user",
    "password": "logs_pass",
}

DB_IDP = {
    "host": os.getenv("IDP_PG_HOST", "localhost"),
    "port": int(os.getenv("IDP_PG_PORT", "5437")),
    "dbname": "idp_logs",
    "user": "logs_user",
    "password": "logs_pass",
}

DB_TRACE = {
    "host": os.getenv("TRACE_PG_HOST", "localhost"),
    "port": int(os.getenv("TRACE_PG_PORT", "5440")),
    "dbname": "proxy_traces",
    "user": "trace_user",
    "password": "trace_pass",
}


def connect(db_params):
    return psycopg2.connect(**db_params, cursor_factory=psycopg2.extras.RealDictCursor)


def poll_for_new_report(start_id, timeout):
    """Block until a new report appears in auth_logs with id > start_id."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with connect(DB_AUTH) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT id, created_at, level, service, title, trace_id, "
                        "content, raw_log FROM reports WHERE id > %s ORDER BY id LIMIT 1",
                        (start_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        return dict(row)
        except psycopg2.OperationalError:
            pass
        time.sleep(POLL_INTERVAL)
    return None


def get_trace_data(trace_id):
    """Fetch full trace breakdown from proxy_traces DB."""
    if not trace_id:
        return None
    try:
        with connect(DB_TRACE) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT trace_id, created_at, root_service, root_report_id "
                    "FROM traces WHERE trace_id = %s",
                    (trace_id,),
                )
                trace_row = cur.fetchone()

                cur.execute(
                    "SELECT id, trace_id, service_name, agent_name, tool_name, "
                    "event_type, started_at, ended_at, duration_ms, status, seq "
                    "FROM trace_entries WHERE trace_id = %s ORDER BY seq",
                    (trace_id,),
                )
                entries = [dict(r) for r in cur.fetchall()]

                cur.execute(
                    "SELECT id, trace_id, service_name, agent_name, "
                    "started_at, ended_at, duration_ms, status "
                    "FROM agent_calls WHERE trace_id = %s ORDER BY id",
                    (trace_id,),
                )
                agent_calls = [dict(r) for r in cur.fetchall()]

                cur.execute(
                    "SELECT id, trace_id, service_name, agent_name, tool_name, "
                    "started_at, ended_at, duration_ms, status "
                    "FROM tool_calls WHERE trace_id = %s ORDER BY id",
                    (trace_id,),
                )
                tool_calls = [dict(r) for r in cur.fetchall()]

                cur.execute(
                    "SELECT id, trace_id, service_name, target_service, method, "
                    "url, status_code, started_at, ended_at, duration_ms, status "
                    "FROM http_calls WHERE trace_id = %s ORDER BY id",
                    (trace_id,),
                )
                http_calls = [dict(r) for r in cur.fetchall()]

        return {
            "trace": dict(trace_row) if trace_row else None,
            "entries": entries,
            "agent_calls": agent_calls,
            "tool_calls": tool_calls,
            "http_calls": http_calls,
        }
    except psycopg2.OperationalError as e:
        print(f"  Warning: could not fetch trace data: {e}", file=sys.stderr)
        return None


def get_log_counts(start_time):
    """Count logs ingested after start_time across all services."""
    counts = {}
    for name, db in [("auth", DB_AUTH), ("deployments", DB_DEPLOYMENTS), ("idp", DB_IDP)]:
        try:
            with connect(db) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT count(*) as cnt FROM logs WHERE timestamp >= %s",
                        (start_time,),
                    )
                    counts[name] = cur.fetchone()["cnt"]
        except psycopg2.OperationalError:
            counts[name] = -1
    return counts


def parse_severity(content):
    """Extract severity rating from report content."""
    if not content:
        return None
    for line in content.split("\n"):
        if "SEVERITY" in line.upper() or "severity" in line.lower():
            return line.strip()
    # Try to find severity in markdown-style
    import re
    match = re.search(r"(?:severity|SEVERITY)[:\s]*(\w+)", content, re.IGNORECASE)
    if match:
        return match.group(0)
    return None


def check_root_cause_correct(content):
    """Heuristic: check if report mentions deployment/release/schema as root cause."""
    if not content:
        return False
    keywords = ["release", "deploy", "schema", "rollback", "callback", "oauth"]
    lower = content.lower()
    return sum(1 for k in keywords if k in lower) >= 2


def json_serial(obj):
    """JSON serializer for datetime objects."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")


def main():
    parser = argparse.ArgumentParser(description="Collect data for one experiment run")
    parser.add_argument("--run-number", type=int, required=True)
    parser.add_argument("--start-report-id", type=int, required=True)
    parser.add_argument("--timeout", type=int, default=300, help="Max seconds to wait for report")
    parser.add_argument("--output-dir", default="../../thesis/Resources/runs")
    args = parser.parse_args()

    start_time = datetime.now(timezone.utc)
    print(f"Run {args.run_number}: waiting for new report (id > {args.start_report_id})...")

    report = poll_for_new_report(args.start_report_id, args.timeout)
    if not report:
        print(f"Run {args.run_number}: TIMEOUT - no report appeared within {args.timeout}s")
        sys.exit(1)

    report_time = report["created_at"]
    print(f"Run {args.run_number}: report #{report['id']} found (trace={report.get('trace_id')})")

    # Wait for trace to complete (agent may still be writing)
    time.sleep(8)

    trace_data = get_trace_data(report.get("trace_id"))
    log_counts = get_log_counts(start_time)

    # Compute summary metrics
    total_duration_ms = None
    total_entries = 0
    services_involved = set()
    tool_call_count = 0
    agent_call_count = 0
    http_call_count = 0

    if trace_data:
        total_entries = len(trace_data["entries"])
        tool_call_count = len(trace_data["tool_calls"])
        agent_call_count = len(trace_data["agent_calls"])
        http_call_count = len(trace_data["http_calls"])

        for e in trace_data["entries"]:
            if e.get("service_name"):
                services_involved.add(e["service_name"])

        # Duration from agent_calls
        durations = [ac["duration_ms"] for ac in trace_data["agent_calls"] if ac.get("duration_ms")]
        if durations:
            total_duration_ms = max(durations)

        # Fallback: check trace_entries for root agent duration
        if not total_duration_ms:
            entry_durations = [e["duration_ms"] for e in trace_data["entries"] if e.get("duration_ms")]
            if entry_durations:
                total_duration_ms = max(entry_durations)

    run_data = {
        "run_number": args.run_number,
        "start_time": start_time.isoformat(),
        "report": {
            "id": report["id"],
            "trace_id": report.get("trace_id"),
            "title": report.get("title"),
            "level": report.get("level"),
            "service": report.get("service"),
            "created_at": report["created_at"],
            "content": report["content"],
            "content_length": len(report["content"]) if report["content"] else 0,
            "severity_line": parse_severity(report["content"]),
            "root_cause_correct": check_root_cause_correct(report["content"]),
        },
        "trace_summary": {
            "trace_id": report.get("trace_id"),
            "total_entries": total_entries,
            "total_duration_ms": total_duration_ms,
            "services_involved": sorted(services_involved),
            "tool_call_count": tool_call_count,
            "agent_call_count": agent_call_count,
            "http_call_count": http_call_count,
        },
        "trace_breakdown": trace_data["entries"] if trace_data else [],
        "log_counts_since_start": log_counts,
    }

    os.makedirs(args.output_dir, exist_ok=True)
    out_path = os.path.join(args.output_dir, f"run_{args.run_number:02d}.json")
    with open(out_path, "w") as f:
        json.dump(run_data, f, indent=2, default=json_serial)

    print(f"Run {args.run_number}: saved to {out_path}")
    print(f"  Duration: {total_duration_ms}ms, Entries: {total_entries}, "
          f"Tools: {tool_call_count}, Services: {sorted(services_involved)}")


if __name__ == "__main__":
    main()
