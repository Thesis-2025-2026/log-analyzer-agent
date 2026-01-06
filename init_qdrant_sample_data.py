#!/usr/bin/env python3
"""
Script to initialize Qdrant vector database with sample error-fix pairs.
This script uses the same embedding model (text-embedding-3-small) as the application.
"""
import os
import sys
from agent_system.tools.rag_tool import add_fix_to_knowledge_base
from dotenv import load_dotenv

load_dotenv()

# Sample error-fix pairs to add to Qdrant
ERROR_FIX_PAIRS = [
    {
        "error": "Bank gateway timeout after 5000ms",
        "fix": "Fix in file: /app/common/bank_api.py, line 87\n\n1. Increase timeout in bank_api.py line 45:\n   Change: TIMEOUT = 5000\n   To: TIMEOUT = 10000\n\n2. Add retry logic in /app/payment/processor.py, line 214:\n   Replace:\n   result = bank_api.charge(card, amount)\n   \n   With:\n   from tenacity import retry, stop_after_attempt, wait_exponential\n   \n   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=4))\n   def charge_with_retry(card, amount):\n       return bank_api.charge(card, amount)\n   \n   result = charge_with_retry(card, amount)\n\n3. Add circuit breaker in /app/common/circuit_breaker.py (new file):\n   Implement circuit breaker pattern to prevent cascading failures.",
        "metadata": {
            "service": "payment-service",
            "severity": "high",
            "resolved_date": "2025-01-10",
            "category": "timeout",
            "files": ["/app/common/bank_api.py", "/app/payment/processor.py"]
        }
    },
    {
        "error": "Database connection pool exhausted",
        "fix": "Fix in file: /app/config/database.py, line 23\n\n1. Increase pool size in database.py line 23:\n   Change: pool_size=100\n   To: pool_size=150\n\n2. Fix connection leak in /app/services/user_service.py, line 156:\n   Replace:\n   conn = db.get_connection()\n   cursor = conn.cursor()\n   # ... query code ...\n   \n   With:\n   conn = db.get_connection()\n   try:\n       cursor = conn.cursor()\n       # ... query code ...\n   finally:\n       cursor.close()\n       conn.close()\n\n3. Add monitoring in /app/monitoring/pool_monitor.py:\n   Alert when pool usage exceeds 80%.",
        "metadata": {
            "service": "user-service",
            "severity": "critical",
            "resolved_date": "2025-01-08",
            "category": "database",
            "files": ["/app/config/database.py", "/app/services/user_service.py"]
        }
    },
    {
        "error": "Failed to authenticate user: Invalid API key",
        "fix": "Fix in file: /app/auth/validator.py, line 89\n\n1. Add key expiration check in validator.py line 89:\n   Add before validation:\n   if api_key.expires_at and api_key.expires_at < datetime.now():\n       raise AuthenticationError('API key expired')\n\n2. Fix key format validation in /app/auth/validator.py, line 95:\n   Change: if not api_key.startswith('sk_'):\n   To: if not re.match(r'^sk_[a-zA-Z0-9]{32}$', api_key):\n\n3. Add rotation mechanism in /app/auth/key_rotation.py:\n   Implement automatic key rotation every 90 days.\n\n4. Add logging in /app/auth/validator.py, line 102:\n   logger.warning(f'Authentication failed for key: {api_key[:8]}...', extra={'user_id': user_id})",
        "metadata": {
            "service": "auth-service",
            "severity": "medium",
            "resolved_date": "2025-01-12",
            "category": "authentication",
            "files": ["/app/auth/validator.py"]
        }
    },
    {
        "error": "Connection refused: Unable to connect to Redis server",
        "fix": "Fix in file: /app/cache/redis_client.py, line 34\n\n1. Fix connection string in .env file:\n   Change: REDIS_URL=redis://localhost:6379\n   To: REDIS_URL=redis://redis.internal:6379\n   (or verify correct host in docker-compose.yml)\n\n2. Add retry logic in redis_client.py line 34:\n   Replace:\n   self.client = redis.Redis.from_url(redis_url)\n   \n   With:\n   from tenacity import retry, stop_after_attempt, wait_exponential\n   \n   @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=3))\n   def connect_redis(self, redis_url):\n       return redis.Redis.from_url(redis_url, socket_connect_timeout=5)\n   \n   self.client = connect_redis(redis_url)\n\n3. Add fallback in /app/cache/cache_manager.py, line 67:\n   if not redis_available:\n       return local_cache.get(key)",
        "metadata": {
            "service": "cache-service",
            "severity": "high",
            "resolved_date": "2025-01-09",
            "category": "connection",
            "files": ["/app/cache/redis_client.py", ".env", "docker-compose.yml"]
        }
    },
    {
        "error": "Out of memory: Java heap space",
        "fix": "Fix in file: /app/analytics/config/jvm.conf\n\n1. Increase heap size in jvm.conf:\n   Change: JAVA_OPTS=-Xmx2g\n   To: JAVA_OPTS=-Xmx4g -XX:+UseG1GC\n\n2. Fix memory leak in /app/analytics/DataProcessor.java, line 234:\n   Replace:\n   List<Data> results = new ArrayList<>();\n   // ... processing ...\n   return results;\n   \n   With:\n   try (Stream<Data> stream = dataSource.stream()) {\n       return stream\n           .limit(10000)  // Add pagination\n           .collect(Collectors.toList());\n   }\n\n3. Add pagination in /app/analytics/DataProcessor.java, line 189:\n   Process data in batches of 1000 records instead of loading all at once.",
        "metadata": {
            "service": "analytics-service",
            "severity": "critical",
            "resolved_date": "2025-01-11",
            "category": "memory",
            "files": ["/app/analytics/config/jvm.conf", "/app/analytics/DataProcessor.java"]
        }
    },
    {
        "error": "Slow query detected: Query execution time exceeded threshold",
        "fix": "Fix in file: /app/services/user_service.py, line 278\n\n1. Add index in migration file: /app/migrations/20250113_add_user_indexes.sql:\n   CREATE INDEX idx_users_email ON users(email);\n   CREATE INDEX idx_users_created_at ON users(created_at);\n\n2. Fix N+1 query in user_service.py line 278:\n   Replace:\n   users = User.query.all()\n   for user in users:\n       user.profile = Profile.query.filter_by(user_id=user.id).first()\n   \n   With:\n   users = User.query.options(joinedload(User.profile)).all()\n\n3. Add pagination in /app/services/user_service.py, line 245:\n   Change: users = User.query.all()\n   To: users = User.query.paginate(page=page, per_page=50).items\n\n4. Optimize join in /app/services/user_service.py, line 312:\n   Use select_related() for foreign key relationships.",
        "metadata": {
            "service": "user-service",
            "severity": "medium",
            "resolved_date": "2025-01-13",
            "category": "performance",
            "files": ["/app/services/user_service.py", "/app/migrations/20250113_add_user_indexes.sql"]
        }
    },
    {
        "error": "SSL certificate verification failed",
        "fix": "Fix in file: /app/common/http_client.py, line 52\n\n1. Update certificate in /app/certs/bank_gateway.crt:\n   Download new certificate from bank gateway provider\n   Replace expired certificate file\n\n2. Fix SSL verification in http_client.py line 52:\n   Replace:\n   verify=False  # TEMPORARY - REMOVE IN PRODUCTION\n   \n   With:\n   verify='/app/certs/bank_gateway.crt'\n\n3. Update CA bundle in Dockerfile:\n   RUN apt-get update && apt-get install -y ca-certificates\n   COPY certs/*.crt /usr/local/share/ca-certificates/\n   RUN update-ca-certificates\n\n4. For development only, add to .env:\n   SSL_VERIFY=false  # Only for local development",
        "metadata": {
            "service": "payment-service",
            "severity": "high",
            "resolved_date": "2025-01-07",
            "category": "security",
            "files": ["/app/common/http_client.py", "/app/certs/bank_gateway.crt", "Dockerfile"]
        }
    },
    {
        "error": "FileNotFoundError: /app/config/settings.yaml",
        "fix": "Fix in file: /app/config/loader.py, line 18\n\n1. Create missing config file: /app/config/settings.yaml\n   Copy from: /app/config/settings.yaml.example\n   Or create with default values\n\n2. Add fallback in loader.py line 18:\n   Replace:\n   with open('/app/config/settings.yaml', 'r') as f:\n   \n   With:\n   config_path = os.getenv('CONFIG_PATH', '/app/config/settings.yaml')\n   if not os.path.exists(config_path):\n       config_path = '/app/config/settings.yaml.default'\n   with open(config_path, 'r') as f:\n\n3. Update docker-compose.yml to mount config:\n   volumes:\n     - ./config:/app/config:ro",
        "metadata": {
            "service": "api-service",
            "severity": "medium",
            "resolved_date": "2025-01-14",
            "category": "configuration",
            "files": ["/app/config/loader.py", "/app/config/settings.yaml", "docker-compose.yml"]
        }
    }
]


def main():
    """Initialize Qdrant with sample error-fix pairs."""
    print("🚀 Initializing Qdrant with sample error-fix pairs...")
    print(f"📊 Total pairs to insert: {len(ERROR_FIX_PAIRS)}\n")
    
    # Check if Qdrant is configured
    qdrant_url = os.getenv("QDRANT_URL")
    if not qdrant_url:
        print("❌ Error: QDRANT_URL environment variable is not set")
        print("   Please set QDRANT_URL and QDRANT_API_KEY in your .env file")
        sys.exit(1)
    
    added_count = 0
    failed_count = 0
    
    for i, pair in enumerate(ERROR_FIX_PAIRS, 1):
        try:
            result = add_fix_to_knowledge_base(
                error_log=pair["error"],
                fix_description=pair["fix"],
                metadata=pair["metadata"]
            )
            
            if result.get("success"):
                added_count += 1
                print(f"✅ [{i}/{len(ERROR_FIX_PAIRS)}] Added fix for: {pair['error'][:60]}...")
            else:
                failed_count += 1
                error_msg = result.get("error", "Unknown error")
                print(f"❌ [{i}/{len(ERROR_FIX_PAIRS)}] Failed: {error_msg}")
                print(f"   Error: {pair['error'][:60]}...")
        except Exception as e:
            failed_count += 1
            print(f"❌ [{i}/{len(ERROR_FIX_PAIRS)}] Exception: {str(e)}")
            print(f"   Error: {pair['error'][:60]}...")
    
    print("\n📊 Summary:")
    print(f"   ✅ Successfully added: {added_count}")
    print(f"   ❌ Failed: {failed_count}")
    
    if failed_count > 0:
        print("\n⚠️  Some entries failed to insert. Check your Qdrant configuration.")
        sys.exit(1)
    else:
        print("\n✅ All sample data inserted successfully!")


if __name__ == "__main__":
    main()
