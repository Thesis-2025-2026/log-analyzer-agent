#!/usr/bin/env bash
set -euo pipefail

# Usage: bash run_100.sh <output_dir> [num_runs] [service]
# service: auth (default), deployments, idp

OUTPUT_DIR="${1:?Usage: run_100.sh <output_dir> [num_runs] [service]}"
NUM_RUNS="${2:-100}"
SERVICE="${3:-auth}"
TIMEOUT_PER_RUN=300
INTER_RUN_DELAY=3
MAX_ATTEMPTS=300
RATE_LIMIT_WAIT=120

# DB config per service
case "$SERVICE" in
    auth)        DB_PORT=5435; DB_NAME=auth_logs ;;
    deployments) DB_PORT=5436; DB_NAME=deployments_logs ;;
    idp)         DB_PORT=5437; DB_NAME=idp_logs ;;
    *)           echo "Unknown service: $SERVICE"; exit 1 ;;
esac

mkdir -p "$OUTPUT_DIR"

# Count existing valid runs and find the highest attempt number
EXISTING=$(find "$OUTPUT_DIR" -name "run_*.json" 2>/dev/null | wc -l | tr -d ' ')
LAST_NUM=$(find "$OUTPUT_DIR" -name "run_*.json" 2>/dev/null | sed 's/.*run_0*//;s/\.json//' | sort -n | tail -1)
LAST_NUM=${LAST_NUM:-0}

echo "========================================="
echo " Experiment: $NUM_RUNS runs (all outcomes)"
echo " Output: $OUTPUT_DIR"
echo " Service: $SERVICE (DB: $DB_NAME @ port $DB_PORT)"
echo " Timeout: ${TIMEOUT_PER_RUN}s per run"
echo " Existing valid runs: $EXISTING"
echo " Resuming from attempt: $((LAST_NUM + 1))"
echo " Started: $(date)"
echo "========================================="

COMPLETED=$EXISTING
ATTEMPT=$LAST_NUM

while [ "$COMPLETED" -lt "$NUM_RUNS" ] && [ "$ATTEMPT" -lt "$MAX_ATTEMPTS" ]; do
    ATTEMPT=$((ATTEMPT + 1))

    MAX_ID=$(PGPASSWORD=logs_pass psql -h localhost -p "$DB_PORT" -U logs_user -d "$DB_NAME" \
        -t -A -c "SELECT COALESCE(MAX(id), 0) FROM reports;" 2>/dev/null || echo "0")
    MAX_ID=$(echo "$MAX_ID" | tr -d ' \t\n\r')

    # Flush similarity filter cache
    docker exec redis redis-cli KEYS "det:sim:*" 2>/dev/null | while read -r key; do
        docker exec redis redis-cli DEL "$key" 2>/dev/null || true
    done

    if python3 collect_run_data.py \
        --run-number "$ATTEMPT" \
        --start-report-id "$MAX_ID" \
        --timeout "$TIMEOUT_PER_RUN" \
        --output-dir "$OUTPUT_DIR" \
        --service "$SERVICE" 2>/dev/null; then

        # Check if report contains rate-limit or Analysis Failed errors
        RUN_FILE="$OUTPUT_DIR/run_$(printf '%03d' $ATTEMPT).json"
        if [ -f "$RUN_FILE" ]; then
            if python3 -c "
import json, sys
with open('$RUN_FILE') as f:
    d = json.load(f)
content = d.get('report', {}).get('content', '') or ''
if 'Analysis Failed' in content or 'rate_limit' in content or '429' in content:
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
                rm -f "$RUN_FILE"
                echo "[$(date +%H:%M:%S)] Run $ATTEMPT: RATE LIMITED/FAILED - waiting ${RATE_LIMIT_WAIT}s..."
                sleep "$RATE_LIMIT_WAIT"
                continue
            fi
        fi

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
