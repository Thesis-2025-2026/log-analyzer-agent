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
echo "      - Payment Service: payment-service historical logs"
echo "      - Order Service: order-service historical logs"
echo "      - Auth Service: auth-service historical logs"
echo "      - Deployments Service: deployments-service historical logs"
echo "      - IDP Service: idp-service historical logs"

echo ""
echo "[2/3] Checking Qdrant services..."

# Wait for Qdrant services to be ready
echo "Waiting for Qdrant services to be ready..."
for i in {1..30}; do
    if curl -s http://localhost:6333/readyz > /dev/null 2>&1 && \
       curl -s http://localhost:6334/readyz > /dev/null 2>&1 && \
       curl -s http://localhost:6335/readyz > /dev/null 2>&1 && \
       curl -s http://localhost:6336/readyz > /dev/null 2>&1 && \
       curl -s http://localhost:6337/readyz > /dev/null 2>&1; then
        echo "Qdrant services are ready!"
        break
    fi
    echo "Waiting... ($i/30)"
    sleep 2
done

echo ""
echo "[3/3] Seeding Qdrant vector databases..."
python3 infra/seed_qdrant.py \
    --payment-url http://localhost:6333 \
    --order-url http://localhost:6334 \
    --auth-url http://localhost:6335 \
    --deployments-url http://localhost:6336 \
    --idp-url http://localhost:6337 \
    --payment-collection payment_log_fixes \
    --order-collection order_log_fixes \
    --auth-collection auth_log_fixes \
    --deployments-collection deployments_log_fixes \
    --idp-collection idp_log_fixes

echo ""
echo "=============================================="
echo "Seeding Complete!"
echo "=============================================="
echo ""
echo "PostgreSQL seeds:"
echo "  - Payment Service: 10 logs, 2 reports"
echo "  - Order Service: 11 logs, 2 reports"
echo "  - Auth Service: 12 logs, 1 report"
echo "  - Deployments Service: 3 logs"
echo "  - IDP Service: 4 logs"
echo ""
echo "Qdrant seeds:"
echo "  - Payment Service: 5 error-fix pairs"
echo "  - Order Service: 5 error-fix pairs"
echo "  - Auth Service: 3 error-fix pairs"
echo "  - Deployments Service: 2 error-fix pairs"
echo "  - IDP Service: 2 error-fix pairs"
echo ""
echo "You can now run the test notebook:"
echo "  jupyter notebook test_distributed_system.ipynb"
