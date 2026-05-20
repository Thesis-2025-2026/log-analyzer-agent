#!/usr/bin/env bash
set -euo pipefail

# Multi-run experiment orchestrator
# Runs the OAuth cascade scenario N times, collecting data for each run.

NUM_RUNS=${1:-10}
COMPOSE_FILE="docker-compose.case-study.yml"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
OUTPUT_DIR="$PROJECT_DIR/../thesis/Resources/runs"
TIMEOUT_PER_RUN=300
INTER_RUN_DELAY=5

cd "$PROJECT_DIR"

echo "========================================="
echo " Multi-Run Experiment (N=$NUM_RUNS)"
echo "========================================="
echo "Compose file: $COMPOSE_FILE"
echo "Output dir:   $OUTPUT_DIR"
echo ""

# Clean previous run data
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

# Bring down any existing stack and remove volumes for clean state
echo "[Setup] Stopping existing containers..."
docker compose -f "$COMPOSE_FILE" down -v 2>/dev/null || true

echo "[Setup] Starting full stack..."
docker compose -f "$COMPOSE_FILE" up -d --build 2>&1 | tail -5

echo "[Setup] Waiting for services to become healthy (60s)..."
sleep 60

# Wait for KB seed to complete
echo "[Setup] Checking KB seed status..."
for i in $(seq 1 30); do
    if docker logs seed-knowledge-base 2>&1 | grep -q "Seeding complete\|already exist"; then
        echo "[Setup] KB seed completed."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "[Setup] Warning: KB seed status unclear, continuing anyway."
    fi
    sleep 2
done

# Verify auth-service API is responding
echo "[Setup] Verifying auth-service API health..."
for i in $(seq 1 20); do
    if curl -sf http://localhost:8001/health > /dev/null 2>&1; then
        echo "[Setup] auth-service API is healthy."
        break
    fi
    if [ "$i" -eq 20 ]; then
        echo "[Setup] Warning: auth-service API not responding, continuing..."
    fi
    sleep 3
done

echo ""
echo "========================================="
echo " Starting experiment runs"
echo "========================================="

for RUN in $(seq 1 "$NUM_RUNS"); do
    echo ""
    echo "--- Run $RUN/$NUM_RUNS ---"

    # Get current max report ID
    MAX_ID=$(PGPASSWORD=logs_pass psql -h localhost -p 5435 -U logs_user -d auth_logs \
        -t -A -c "SELECT COALESCE(MAX(id), 0) FROM reports;" 2>/dev/null || echo "0")
    MAX_ID=$(echo "$MAX_ID" | tr -d '[:space:]')
    echo "  Current max report ID: $MAX_ID"

    # Flush similarity filter keys in Redis
    echo "  Flushing similarity filter cache..."
    KEYS=$(docker exec redis redis-cli KEYS "det:sim:*" 2>/dev/null || echo "")
    if [ -n "$KEYS" ] && [ "$KEYS" != "" ]; then
        docker exec redis redis-cli KEYS "det:sim:*" | xargs -I {} docker exec redis redis-cli DEL {} 2>/dev/null || true
    fi
    echo "  Similarity cache flushed."

    # Run data collection
    echo "  Waiting for new report..."
    python3 "$SCRIPT_DIR/collect_run_data.py" \
        --run-number "$RUN" \
        --start-report-id "$MAX_ID" \
        --timeout "$TIMEOUT_PER_RUN" \
        --output-dir "$OUTPUT_DIR"

    if [ $? -ne 0 ]; then
        echo "  WARNING: Run $RUN failed or timed out!"
    fi

    # Inter-run delay
    if [ "$RUN" -lt "$NUM_RUNS" ]; then
        echo "  Waiting ${INTER_RUN_DELAY}s before next run..."
        sleep "$INTER_RUN_DELAY"
    fi
done

echo ""
echo "========================================="
echo " Experiment complete!"
echo "========================================="
echo "Results saved to: $OUTPUT_DIR"
ls -la "$OUTPUT_DIR"

echo ""
echo "Stopping stack..."
docker compose -f "$COMPOSE_FILE" down
echo "Done."
