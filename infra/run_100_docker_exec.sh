#!/usr/bin/env bash
set -euo pipefail

# Usage: bash run_100_docker_exec.sh <output_dir> <pg_container> <redis_container> <trace_pg_container> [num_runs]
# Collects experiment data using docker exec (no host port mapping needed).

OUTPUT_DIR="${1:?Usage: run_100_docker_exec.sh <output_dir> <pg_container> <redis_container> <trace_pg_container> [num_runs]}"
PG_CONTAINER="${2:?Provide auth postgres container (e.g. service-auth-postgres-exp2)}"
REDIS_CONTAINER="${3:?Provide redis container (e.g. redis-exp2)}"
TRACE_PG_CONTAINER="${4:?Provide trace postgres container (e.g. proxy-trace-postgres-exp2)}"
NUM_RUNS="${5:-100}"
TIMEOUT_PER_RUN=300
INTER_RUN_DELAY=3
MAX_ATTEMPTS=200

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
mkdir -p "$OUTPUT_DIR"

echo "========================================="
echo " Experiment: $NUM_RUNS runs (all outcomes, docker exec)"
echo " Output: $OUTPUT_DIR"
echo " Auth PG: $PG_CONTAINER"
echo " Redis: $REDIS_CONTAINER"
echo " Trace PG: $TRACE_PG_CONTAINER"
echo " Started: $(date)"
echo "========================================="

get_max_report_id() {
    docker exec "$PG_CONTAINER" psql -U logs_user -d auth_logs -t -A \
        -c "SELECT COALESCE(MAX(id), 0) FROM reports;" 2>/dev/null | tr -d ' \t\n\r'
}

poll_for_report() {
    local start_id="$1"
    local timeout="$2"
    local deadline=$(($(date +%s) + timeout))

    while [ "$(date +%s)" -lt "$deadline" ]; do
        local result
        result=$(docker exec "$PG_CONTAINER" psql -U logs_user -d auth_logs -t -A \
            -c "SELECT row_to_json(r) FROM (SELECT id, created_at, level, service, title, trace_id, content, raw_log FROM reports WHERE id > $start_id ORDER BY id LIMIT 1) r;" 2>/dev/null || echo "")
        if [ -n "$result" ] && [ "$result" != "" ]; then
            echo "$result"
            return 0
        fi
        sleep 3
    done
    return 1
}

get_trace_data() {
    local trace_id="$1"
    docker exec "$TRACE_PG_CONTAINER" psql -U trace_user -d proxy_traces -t -A -c "
        SELECT json_build_object(
            'entries', (SELECT COALESCE(json_agg(row_to_json(e)), '[]'::json) FROM (SELECT id, trace_id, service_name, agent_name, tool_name, event_type, started_at, ended_at, duration_ms, status, seq FROM trace_entries WHERE trace_id = '$trace_id' ORDER BY seq) e),
            'agent_calls', (SELECT COALESCE(json_agg(row_to_json(a)), '[]'::json) FROM (SELECT id, trace_id, service_name, agent_name, started_at, ended_at, duration_ms, status, prompt_tokens, completion_tokens, total_tokens FROM agent_calls WHERE trace_id = '$trace_id' ORDER BY id) a),
            'tool_calls', (SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json) FROM (SELECT id, trace_id, service_name, agent_name, tool_name, started_at, ended_at, duration_ms, status FROM tool_calls WHERE trace_id = '$trace_id' ORDER BY id) t),
            'http_calls', (SELECT COALESCE(json_agg(row_to_json(h)), '[]'::json) FROM (SELECT id, trace_id, service_name, target_service, method, url, status_code, started_at, ended_at, duration_ms, status FROM http_calls WHERE trace_id = '$trace_id' ORDER BY id) h)
        );" 2>/dev/null || echo "{}"
}

COMPLETED=0
ATTEMPT=0

while [ "$COMPLETED" -lt "$NUM_RUNS" ] && [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
    ATTEMPT=$((ATTEMPT + 1))

    MAX_ID=$(get_max_report_id)
    [ -z "$MAX_ID" ] && MAX_ID=0

    # Flush similarity filter cache
    docker exec "$REDIS_CONTAINER" redis-cli KEYS "det:sim:*" 2>/dev/null | while read -r key; do
        docker exec "$REDIS_CONTAINER" redis-cli DEL "$key" 2>/dev/null || true
    done

    REPORT_JSON=$(poll_for_report "$MAX_ID" "$TIMEOUT_PER_RUN" || echo "")

    if [ -z "$REPORT_JSON" ]; then
        echo "[$(date +%H:%M:%S)] Run $ATTEMPT: TIMEOUT/ERROR"
        if [ "$COMPLETED" -lt "$NUM_RUNS" ] && [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; then
            sleep "$INTER_RUN_DELAY"
        fi
        continue
    fi

    # Wait for trace to complete
    sleep 8

    REPORT_ID=$(echo "$REPORT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
    TRACE_ID=$(echo "$REPORT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('trace_id',''))")
    CONTENT=$(echo "$REPORT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('content',''))")

    TRACE_DATA=""
    if [ -n "$TRACE_ID" ]; then
        TRACE_DATA=$(get_trace_data "$TRACE_ID")
    fi

    # Build the run JSON using Python
    python3 -c "
import json, sys

report = json.loads('''$REPORT_JSON''')
trace_raw = '''$TRACE_DATA'''
trace_data = json.loads(trace_raw) if trace_raw.strip() else {}

entries = trace_data.get('entries', [])
agent_calls = trace_data.get('agent_calls', [])
tool_calls = trace_data.get('tool_calls', [])
http_calls = trace_data.get('http_calls', [])

services = set()
for e in entries:
    if e.get('service_name'):
        services.add(e['service_name'])

total_prompt = sum(a.get('prompt_tokens') or 0 for a in agent_calls)
total_completion = sum(a.get('completion_tokens') or 0 for a in agent_calls)
total_tokens = sum(a.get('total_tokens') or 0 for a in agent_calls)

durations = [a['duration_ms'] for a in agent_calls if a.get('duration_ms')]
total_duration = max(durations) if durations else None

content = report.get('content', '')
keywords = ['release', 'deploy', 'schema', 'rollback', 'callback', 'oauth']
root_cause_correct = sum(1 for k in keywords if k in content.lower()) >= 2

run_data = {
    'run_number': $ATTEMPT,
    'report': {
        'id': report['id'],
        'trace_id': report.get('trace_id'),
        'title': report.get('title'),
        'level': report.get('level'),
        'service': report.get('service'),
        'created_at': str(report.get('created_at','')),
        'content': content,
        'content_length': len(content),
        'root_cause_correct': root_cause_correct,
    },
    'trace_summary': {
        'trace_id': report.get('trace_id'),
        'total_entries': len(entries),
        'total_duration_ms': total_duration,
        'services_involved': sorted(services),
        'tool_call_count': len(tool_calls),
        'agent_call_count': len(agent_calls),
        'http_call_count': len(http_calls),
        'prompt_tokens': total_prompt,
        'completion_tokens': total_completion,
        'total_tokens': total_tokens,
    },
    'trace_breakdown': entries,
}

out_path = '$OUTPUT_DIR/run_$(printf "%02d" $ATTEMPT).json'
with open(out_path, 'w') as f:
    json.dump(run_data, f, indent=2, default=str)

print(f'  Duration: {total_duration}ms, Entries: {len(entries)}, Tools: {len(tool_calls)}, Services: {sorted(services)}')
if total_tokens:
    print(f'  Tokens: {total_prompt} prompt + {total_completion} completion = {total_tokens} total')
" 2>&1

    COMPLETED=$((COMPLETED + 1))
    echo "[$(date +%H:%M:%S)] Run $ATTEMPT: SAVED #$COMPLETED/$NUM_RUNS"

    if [ "$COMPLETED" -lt "$NUM_RUNS" ] && [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; then
        sleep "$INTER_RUN_DELAY"
    fi
done

echo ""
echo "========================================="
echo " Complete: $COMPLETED runs saved from $ATTEMPT attempts"
echo " Finished: $(date)"
echo "========================================="
ls "$OUTPUT_DIR" | wc -l | xargs -I{} echo " Files: {}"
