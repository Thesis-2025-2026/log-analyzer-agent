#!/usr/bin/env bash
set -euo pipefail

# Usage: bash run_100_parallel.sh <output_dir> <auth_pg_port> <redis_container> [num_runs]
# Like run_100.sh but with configurable ports/containers for parallel stacks.

OUTPUT_DIR="${1:?Usage: run_100_parallel.sh <output_dir> <auth_pg_port> <redis_container> [num_runs]}"
AUTH_PG_PORT="${2:?Provide auth postgres port (e.g. 5535)}"
REDIS_CONTAINER="${3:?Provide redis container name (e.g. redis-exp2)}"
NUM_RUNS="${4:-100}"
TIMEOUT_PER_RUN=300
INTER_RUN_DELAY=3
MAX_ATTEMPTS=200

mkdir -p "$OUTPUT_DIR"

echo "========================================="
echo " Experiment: $NUM_RUNS runs (all outcomes)"
echo " Output: $OUTPUT_DIR"
echo " Auth PG port: $AUTH_PG_PORT"
echo " Redis container: $REDIS_CONTAINER"
echo " Started: $(date)"
echo "========================================="

COMPLETED=0
ATTEMPT=0

while [ "$COMPLETED" -lt "$NUM_RUNS" ] && [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
    ATTEMPT=$((ATTEMPT + 1))

    MAX_ID=$(PGPASSWORD=logs_pass psql -h localhost -p "$AUTH_PG_PORT" -U logs_user -d auth_logs \
        -t -A -c "SELECT COALESCE(MAX(id), 0) FROM reports;" 2>/dev/null || echo "0")
    MAX_ID=$(echo "$MAX_ID" | tr -d ' \t\n\r')

    # Flush similarity filter cache
    docker exec "$REDIS_CONTAINER" redis-cli KEYS "det:sim:*" 2>/dev/null | while read -r key; do
        docker exec "$REDIS_CONTAINER" redis-cli DEL "$key" 2>/dev/null || true
    done

    if AUTH_PG_PORT="$AUTH_PG_PORT" \
       DEPLOY_PG_PORT="${DEPLOY_PG_PORT:-5536}" \
       IDP_PG_PORT="${IDP_PG_PORT:-5537}" \
       TRACE_PG_PORT="${TRACE_PG_PORT:-5540}" \
       python3 collect_run_data.py \
        --run-number "$ATTEMPT" \
        --start-report-id "$MAX_ID" \
        --timeout "$TIMEOUT_PER_RUN" \
        --output-dir "$OUTPUT_DIR" 2>/dev/null; then

        COMPLETED=$((COMPLETED + 1))
        echo "[$(date +%H:%M:%S)] Run $ATTEMPT: SAVED #$COMPLETED/$NUM_RUNS"
    else
        echo "[$(date +%H:%M:%S)] Run $ATTEMPT: TIMEOUT/ERROR"
    fi

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
