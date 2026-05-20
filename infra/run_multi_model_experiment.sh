#!/usr/bin/env bash
set -euo pipefail

# Multi-Model Experiment Runner
# Runs 100 iterations per model, keeping ALL outcomes (success + failure).
# Usage: bash run_multi_model_experiment.sh [model_key]
#   model_key: 4omini | gpt54mini | gpt5nano | haiku  (optional, runs all if omitted)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
RESOURCES_DIR="$(cd "$PROJECT_DIR/../thesis/Resources" && pwd)"
CONFIG_DIR="$PROJECT_DIR/config"

RUNS_PER_MODEL=100
TIMEOUT_PER_RUN=300
INTER_RUN_DELAY=3
MAX_ATTEMPTS=200

declare -A MODEL_NAMES=(
    [4omini]="gpt-4o-mini"
    [gpt54mini]="gpt-5.4-mini"
    [gpt5nano]="gpt-5-nano"
    [haiku]="claude-haiku-4-5-20250414"
)

declare -A MODEL_PLATFORMS=(
    [4omini]="OPENAI"
    [gpt54mini]="OPENAI"
    [gpt5nano]="OPENAI"
    [haiku]="ANTHROPIC"
)

declare -A OUTPUT_DIRS=(
    [4omini]="$RESOURCES_DIR/runs_4omini"
    [gpt54mini]="$RESOURCES_DIR/runs_gpt54mini"
    [gpt5nano]="$RESOURCES_DIR/runs_gpt5nano"
    [haiku]="$RESOURCES_DIR/runs_haiku"
)

SERVICE_ENVS=(
    "$CONFIG_DIR/service-auth.env"
    "$CONFIG_DIR/service-deployments.env"
    "$CONFIG_DIR/service-idp.env"
    "$CONFIG_DIR/service-order.env"
    "$CONFIG_DIR/service-payment.env"
)

AGENT_CONTAINERS=(
    "service-auth-consumer"
    "service-deployments-consumer"
    "service-idp-consumer"
    "service-order-consumer"
    "service-payment-consumer"
)

update_env_files() {
    local model_name="$1"
    local model_platform="$2"

    for env_file in "${SERVICE_ENVS[@]}"; do
        if grep -q "^MODEL_NAME=" "$env_file"; then
            sed -i '' "s/^MODEL_NAME=.*/MODEL_NAME=$model_name/" "$env_file"
        else
            echo "MODEL_NAME=$model_name" >> "$env_file"
        fi

        if grep -q "^MODEL_PLATFORM=" "$env_file"; then
            sed -i '' "s/^MODEL_PLATFORM=.*/MODEL_PLATFORM=$model_platform/" "$env_file"
        else
            echo "MODEL_PLATFORM=$model_platform" >> "$env_file"
        fi
    done
    echo "  Updated env files: MODEL_NAME=$model_name, MODEL_PLATFORM=$model_platform"
}

restart_agents() {
    echo "  Rebuilding and restarting agent containers..."
    cd "$PROJECT_DIR"
    docker compose -f docker-compose.case-study.yml build \
        service-auth-consumer service-deployments-consumer \
        service-idp-consumer service-order-consumer service-payment-consumer \
        --quiet 2>/dev/null || true

    for container in "${AGENT_CONTAINERS[@]}"; do
        docker compose -f docker-compose.case-study.yml restart "$container" 2>/dev/null || true
    done

    echo "  Waiting 15s for containers to stabilize..."
    sleep 15
}

flush_redis_cache() {
    docker exec redis redis-cli KEYS "det:sim:*" 2>/dev/null | while read -r key; do
        docker exec redis redis-cli DEL "$key" 2>/dev/null || true
    done
}

run_single_model() {
    local model_key="$1"
    local model_name="${MODEL_NAMES[$model_key]}"
    local model_platform="${MODEL_PLATFORMS[$model_key]}"
    local output_dir="${OUTPUT_DIRS[$model_key]}"

    echo ""
    echo "========================================="
    echo " Model: $model_name ($model_platform)"
    echo " Output: $output_dir"
    echo " Target: $RUNS_PER_MODEL runs (all outcomes)"
    echo " Started: $(date)"
    echo "========================================="

    update_env_files "$model_name" "$model_platform"
    restart_agents

    mkdir -p "$output_dir"

    local completed=0
    local attempt=0

    while [ "$completed" -lt "$RUNS_PER_MODEL" ] && [ "$attempt" -lt "$MAX_ATTEMPTS" ]; do
        attempt=$((attempt + 1))

        MAX_ID=$(PGPASSWORD=logs_pass psql -h localhost -p 5435 -U logs_user -d auth_logs \
            -t -A -c "SELECT COALESCE(MAX(id), 0) FROM reports;" 2>/dev/null || echo "0")
        MAX_ID=$(echo "$MAX_ID" | tr -d '[:space:]')

        flush_redis_cache

        cd "$SCRIPT_DIR"
        if python3 collect_run_data.py \
            --run-number "$attempt" \
            --start-report-id "$MAX_ID" \
            --timeout "$TIMEOUT_PER_RUN" \
            --output-dir "$output_dir" 2>/dev/null; then

            completed=$((completed + 1))
            echo "[$(date +%H:%M:%S)] Attempt $attempt: SAVED #$completed/$RUNS_PER_MODEL"
        else
            echo "[$(date +%H:%M:%S)] Attempt $attempt: TIMEOUT/ERROR"
        fi

        if [ "$completed" -lt "$RUNS_PER_MODEL" ] && [ "$attempt" -lt "$MAX_ATTEMPTS" ]; then
            sleep "$INTER_RUN_DELAY"
        fi
    done

    echo ""
    echo "  Model $model_name complete: $completed runs saved from $attempt attempts"
    echo "  Finished: $(date)"
    ls "$output_dir" | wc -l | xargs -I{} echo "  Files in output: {}"
}

verify_model() {
    local model_key="$1"
    local model_name="${MODEL_NAMES[$model_key]}"
    local model_platform="${MODEL_PLATFORMS[$model_key]}"

    echo ""
    echo "--- Verifying $model_name ($model_platform) ---"

    update_env_files "$model_name" "$model_platform"
    restart_agents
    flush_redis_cache

    local tmp_dir=$(mktemp -d)
    local MAX_ID=$(PGPASSWORD=logs_pass psql -h localhost -p 5435 -U logs_user -d auth_logs \
        -t -A -c "SELECT COALESCE(MAX(id), 0) FROM reports;" 2>/dev/null || echo "0")
    MAX_ID=$(echo "$MAX_ID" | tr -d '[:space:]')

    cd "$SCRIPT_DIR"
    if python3 collect_run_data.py \
        --run-number 1 \
        --start-report-id "$MAX_ID" \
        --timeout 180 \
        --output-dir "$tmp_dir"; then

        local run_file="$tmp_dir/run_01.json"
        if [ -f "$run_file" ]; then
            local content_len=$(python3 -c "import json; d=json.load(open('$run_file')); print(d['report']['content_length'])" 2>/dev/null || echo "0")
            local tokens=$(python3 -c "import json; d=json.load(open('$run_file')); print(d['trace_summary']['total_tokens'])" 2>/dev/null || echo "0")

            if [ "$content_len" -gt 10 ] && [ "$tokens" -gt 0 ]; then
                echo "  PASS: report=$content_len chars, tokens=$tokens"
                rm -rf "$tmp_dir"
                return 0
            else
                echo "  FAIL: content_length=$content_len, tokens=$tokens"
                rm -rf "$tmp_dir"
                return 1
            fi
        fi
    fi

    echo "  FAIL: no report generated within timeout"
    rm -rf "$tmp_dir"
    return 1
}

# Main execution
if [ "${1:-}" = "verify" ]; then
    echo "========================================="
    echo " Model Verification Phase"
    echo "========================================="
    MODELS_TO_VERIFY=("${@:2}")
    if [ ${#MODELS_TO_VERIFY[@]} -eq 0 ]; then
        MODELS_TO_VERIFY=("4omini" "gpt54mini" "gpt5nano" "haiku")
    fi
    for key in "${MODELS_TO_VERIFY[@]}"; do
        if verify_model "$key"; then
            echo "  => $key: VERIFIED"
        else
            echo "  => $key: FAILED - will skip in full run"
        fi
    done
    exit 0
fi

MODELS_TO_RUN=("${@}")
if [ ${#MODELS_TO_RUN[@]} -eq 0 ]; then
    MODELS_TO_RUN=("4omini" "gpt54mini" "gpt5nano" "haiku")
fi

echo "========================================="
echo " Multi-Model Experiment"
echo " Models: ${MODELS_TO_RUN[*]}"
echo " Runs per model: $RUNS_PER_MODEL"
echo " Started: $(date)"
echo "========================================="

for key in "${MODELS_TO_RUN[@]}"; do
    run_single_model "$key"
done

echo ""
echo "========================================="
echo " ALL EXPERIMENTS COMPLETE"
echo " Finished: $(date)"
echo "========================================="
