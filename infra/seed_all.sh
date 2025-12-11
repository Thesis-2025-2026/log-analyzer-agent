#!/bin/bash
# Seed all databases for distributed demo
# 
# Usage: ./infra/seed_all.sh
#
# Prerequisites:
# - Docker containers running (docker-compose -f docker-compose.distributed.yml up -d)
# - OPENAI_API_KEY set in environment or .env file

set -e

echo "=============================================="
echo "Seeding Distributed Demo Databases"
echo "=============================================="

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Check for OPENAI_API_KEY
if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY not set"
    echo "Please set it in .env file or export it"
    exit 1
fi

echo ""
echo "[1/3] PostgreSQL databases are seeded automatically on container start"
echo "      - Service A: payment-service historical logs"
echo "      - Service B: order-service historical logs"

echo ""
echo "[2/3] Checking Qdrant services..."

# Wait for Qdrant services to be ready
echo "Waiting for Qdrant services to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:6333/readyz > /dev/null 2>&1 && \
       curl -s http://localhost:6334/readyz > /dev/null 2>&1; then
        echo "Qdrant services are ready!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

echo ""
echo "[3/3] Seeding Qdrant vector databases..."
python infra/seed_qdrant.py \
    --service-a-url http://localhost:6333 \
    --service-b-url http://localhost:6334 \
    --collection log_fixes

echo ""
echo "=============================================="
echo "Seeding Complete!"
echo "=============================================="
echo ""
echo "PostgreSQL seeds:"
echo "  - Service A: 10 payment logs, 2 reports"
echo "  - Service B: 11 order logs, 2 reports"
echo ""
echo "Qdrant seeds:"
echo "  - Service A: 5 payment error-fix pairs"
echo "  - Service B: 5 order error-fix pairs"
echo ""
echo "You can now run the test notebook:"
echo "  jupyter notebook test_distributed_system.ipynb"

