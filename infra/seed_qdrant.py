#!/usr/bin/env python3
"""
Seed Qdrant vector databases with error-fix pairs for distributed demo.

This script populates both service-a-qdrant and service-b-qdrant with
service-specific knowledge for demonstrating cross-service analysis.

Usage:
    python infra/seed_qdrant.py [--service-a-url URL] [--service-b-url URL]
"""

import os
import sys
import argparse
import uuid
from typing import List, Dict
from dotenv import load_dotenv

load_dotenv()

# Try to import required libraries
try:
    from qdrant_client import QdrantClient, models
    from openai import OpenAI
except ImportError:
    print("Required packages not installed. Run: pip install qdrant-client openai")
    sys.exit(1)


# Service A (Payment Service) Error-Fix Knowledge Base
PAYMENT_SERVICE_FIXES = [
    {
        "error": "Bank gateway timeout after 5000ms",
        "fix": """Fix in file: /app/common/bank_api.py, line 87

1. Increase timeout in bank_api.py line 45:
   Change: timeout=5000 -> timeout=8000

2. Add circuit breaker pattern:
   ```python
   from circuitbreaker import circuit
   
   @circuit(failure_threshold=5, recovery_timeout=30)
   def charge(card, amount):
       # existing code
   ```

3. Add retry with exponential backoff:
   ```python
   @retry(tries=3, delay=1, backoff=2)
   def charge(card, amount):
       # existing code
   ```

Root cause: Bank gateway occasionally experiences high latency during peak hours.
Prevention: Monitor bank gateway response times, set up alerts for >3000ms responses.""",
        "severity": "HIGH",
        "service": "payment-service"
    },
    {
        "error": "Database connection pool exhausted - HikariPool-1 Connection not available",
        "fix": """Fix in file: /app/config/database.py, line 23

1. Increase pool size in database.py line 23:
   Change: maximumPoolSize=100 -> maximumPoolSize=150

2. Check for connection leaks in PaymentProcessor.java:
   ```java
   // WRONG - connection leak
   Connection conn = dataSource.getConnection();
   // do work
   // missing conn.close()
   
   // CORRECT - use try-with-resources
   try (Connection conn = dataSource.getConnection()) {
       // do work
   } // auto-closed
   ```

3. Add connection timeout:
   connectionTimeout=30000
   idleTimeout=600000
   maxLifetime=1800000

Root cause: Connection leak in processRefund() method.
Prevention: Use try-with-resources, add connection pool monitoring.""",
        "severity": "CRITICAL",
        "service": "payment-service"
    },
    {
        "error": "Payment declined by bank - decline code 51 insufficient funds",
        "fix": """This is a customer-side issue, not a system error.

Recommended handling:
1. Return clear error message to customer
2. Suggest alternative payment methods
3. Log for analytics but don't alert ops team

Example response:
```python
return PaymentResult(
    success=False,
    error_code="INSUFFICIENT_FUNDS",
    customer_message="Payment declined. Please try another card or payment method.",
    retry_allowed=True
)
```

Prevention: Implement pre-authorization checks for high-value orders.""",
        "severity": "LOW",
        "service": "payment-service"
    },
    {
        "error": "Transaction rollback due to deadlock",
        "fix": """Fix in file: /app/payment/processor.py

1. Add retry logic for deadlock:
   ```python
   @retry(on_exception=DeadlockException, tries=3, delay=0.1)
   def process_payment(order_id, amount):
       with transaction.atomic():
           # payment logic
   ```

2. Ensure consistent lock ordering:
   - Always lock order before payment
   - Always lock customer before order

3. Reduce transaction scope:
   - Split large transactions into smaller ones
   - Use optimistic locking where possible

Root cause: Concurrent payment and refund operations on same order.
Prevention: Implement order-level locking, monitor deadlock frequency.""",
        "severity": "MEDIUM",
        "service": "payment-service"
    },
    {
        "error": "Payment processor connection refused",
        "fix": """Immediate actions:
1. Check payment processor status page
2. Verify network connectivity from payment-service
3. Check firewall rules

If payment processor is down:
1. Enable fallback payment processor (if configured)
2. Queue payments for retry
3. Notify customers of temporary delay

Configuration:
```yaml
payment:
  primary_processor: stripe
  fallback_processor: paypal
  queue_on_failure: true
  max_queue_time: 3600
```

Root cause: Usually payment processor maintenance or network issues.
Prevention: Multi-processor setup, payment queue for resilience.""",
        "severity": "CRITICAL",
        "service": "payment-service"
    }
]

# Service B (Order Service) Error-Fix Knowledge Base
ORDER_SERVICE_FIXES = [
    {
        "error": "Order stuck in PENDING_PAYMENT state",
        "fix": """Fix in file: /app/order/state_machine.py

1. Add payment timeout handler:
   ```python
   PAYMENT_TIMEOUT_MINUTES = 30
   
   @scheduled(every=5, unit='minutes')
   def check_pending_payments():
       stuck_orders = Order.objects.filter(
           status='PENDING_PAYMENT',
           created_at__lt=now() - timedelta(minutes=PAYMENT_TIMEOUT_MINUTES)
       )
       for order in stuck_orders:
           order.handle_payment_timeout()
   ```

2. Implement payment status polling:
   ```python
   def poll_payment_status(order_id):
       payment = PaymentService.get_status(order_id)
       if payment.status == 'COMPLETED':
           order.mark_paid()
       elif payment.status == 'FAILED':
           order.mark_payment_failed()
   ```

Root cause: Payment service timeout not propagating to order service.
Cross-service: Check payment-service logs for corresponding timeout errors.
Prevention: Implement event-driven payment confirmation with message queue.""",
        "severity": "HIGH",
        "service": "order-service"
    },
    {
        "error": "Inventory reservation failed - insufficient stock",
        "fix": """Fix in file: /app/order/inventory.py

1. Implement soft reservation:
   ```python
   def reserve_inventory(product_id, qty, order_id):
       with transaction.atomic():
           product = Product.objects.select_for_update().get(id=product_id)
           if product.available_qty >= qty:
               product.available_qty -= qty
               product.reserved_qty += qty
               product.save()
               Reservation.objects.create(
                   product=product, qty=qty, order_id=order_id,
                   expires_at=now() + timedelta(minutes=30)
               )
               return True
       return False
   ```

2. Add inventory alerts:
   ```python
   if product.available_qty < product.low_stock_threshold:
       send_low_stock_alert(product)
   ```

Root cause: Race condition between order placement and inventory update.
Prevention: Use SELECT FOR UPDATE, implement inventory buffer for popular items.""",
        "severity": "MEDIUM",
        "service": "order-service"
    },
    {
        "error": "Unable to create shipment - payment not confirmed",
        "fix": """Fix in file: /app/order/fulfillment.py

1. Add payment verification before shipment:
   ```python
   def create_shipment(order_id):
       order = Order.objects.get(id=order_id)
       
       # Verify payment status with payment service
       payment_status = PaymentService.verify(order.payment_id)
       
       if payment_status != 'CONFIRMED':
           raise PaymentNotConfirmedException(
               f"Order {order_id} payment status: {payment_status}"
           )
       
       # Proceed with shipment
       return ShippingService.create_label(order)
   ```

2. Implement retry with backoff:
   ```python
   @retry(tries=5, delay=60, backoff=2)
   def wait_for_payment_confirmation(order_id):
       # poll payment service
   ```

Root cause: Payment service delay or failure blocking fulfillment pipeline.
Cross-service: Correlate with payment-service logs for root cause.
Prevention: Async payment confirmation via message queue.""",
        "severity": "HIGH",
        "service": "order-service"
    },
    {
        "error": "Batch shipment creation failed - external service unavailable",
        "fix": """Fix in file: /app/order/batch_processor.py

1. Implement batch retry logic:
   ```python
   def process_shipment_batch(order_ids):
       failed_orders = []
       for order_id in order_ids:
           try:
               create_shipment(order_id)
           except ServiceUnavailableException:
               failed_orders.append(order_id)
       
       if failed_orders:
           schedule_retry(failed_orders, delay_minutes=15)
       
       return len(order_ids) - len(failed_orders)
   ```

2. Add circuit breaker for shipping service:
   ```python
   @circuit(failure_threshold=3, recovery_timeout=60)
   def call_shipping_api(order):
       # API call
   ```

Root cause: Shipping provider API downtime or rate limiting.
Prevention: Multiple shipping providers, request queuing.""",
        "severity": "HIGH",
        "service": "order-service"
    },
    {
        "error": "Order state update failed - database timeout",
        "fix": """Fix in file: /app/order/models.py

1. Add query timeout:
   ```python
   from django.db import connection
   
   with connection.cursor() as cursor:
       cursor.execute("SET statement_timeout = '5000'")
       # execute query
   ```

2. Optimize slow queries:
   - Add index on order.status column
   - Add index on order.customer_id column
   - Partition orders table by created_at

3. Use async state updates:
   ```python
   @celery.task
   def update_order_state(order_id, new_state):
       Order.objects.filter(id=order_id).update(status=new_state)
   ```

Root cause: Database under high load, missing indexes.
Prevention: Query optimization, database monitoring, read replicas.""",
        "severity": "MEDIUM",
        "service": "order-service"
    }
]


def get_embedding(client: OpenAI, text: str) -> List[float]:
    """Generate embedding using OpenAI text-embedding-3-small."""
    response = client.embeddings.create(
        model="text-embedding-3-small",
        input=text
    )
    return response.data[0].embedding


def create_collection_if_not_exists(qdrant_client: QdrantClient, collection_name: str):
    """Create Qdrant collection if it doesn't exist."""
    collections = qdrant_client.get_collections().collections
    exists = any(c.name == collection_name for c in collections)
    
    if not exists:
        qdrant_client.create_collection(
            collection_name=collection_name,
            vectors_config=models.VectorParams(
                size=1536,  # text-embedding-3-small dimension
                distance=models.Distance.COSINE
            )
        )
        print(f"Created collection: {collection_name}")
    else:
        print(f"Collection already exists: {collection_name}")


def seed_qdrant(
    qdrant_url: str,
    collection_name: str,
    fixes: List[Dict],
    openai_client: OpenAI
):
    """Seed a Qdrant instance with error-fix pairs."""
    print(f"\nSeeding Qdrant at {qdrant_url}...")
    
    try:
        qdrant_client = QdrantClient(url=qdrant_url, timeout=30.0)
        create_collection_if_not_exists(qdrant_client, collection_name)
        
        points = []
        for fix_data in fixes:
            # Create combined text for embedding
            text_for_embedding = f"Error: {fix_data['error']}\nFix: {fix_data['fix']}"
            
            # Generate embedding
            print(f"  Generating embedding for: {fix_data['error'][:50]}...")
            embedding = get_embedding(openai_client, text_for_embedding)
            
            # Create point
            point = models.PointStruct(
                id=str(uuid.uuid4()),
                vector=embedding,
                payload={
                    "error": fix_data["error"],
                    "fix": fix_data["fix"],
                    "severity": fix_data["severity"],
                    "service": fix_data["service"],
                    "text": text_for_embedding
                }
            )
            points.append(point)
        
        # Upsert all points
        qdrant_client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        print(f"  ✓ Inserted {len(points)} error-fix pairs into {collection_name}")
        
        # Verify
        info = qdrant_client.get_collection(collection_name)
        print(f"  Collection {collection_name} now has {info.points_count} points")
        
    except Exception as e:
        print(f"  ✗ Error seeding {qdrant_url}: {e}")
        raise


def main():
    parser = argparse.ArgumentParser(description="Seed Qdrant databases for distributed demo")
    parser.add_argument("--service-a-url", default="http://localhost:6333", 
                        help="Qdrant URL for Service A")
    parser.add_argument("--service-b-url", default="http://localhost:6334",
                        help="Qdrant URL for Service B")
    parser.add_argument("--collection", default="log_fixes",
                        help="Collection name")
    args = parser.parse_args()
    
    # Check for API key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Error: OPENAI_API_KEY environment variable not set")
        sys.exit(1)
    
    # Initialize OpenAI client
    openai_client = OpenAI(api_key=api_key)
    
    print("=" * 60)
    print("Qdrant Seed Script for Distributed Demo")
    print("=" * 60)
    
    # Seed Service A (Payment Service)
    print("\n[Service A - Payment Service]")
    try:
        seed_qdrant(
            qdrant_url=args.service_a_url,
            collection_name=args.collection,
            fixes=PAYMENT_SERVICE_FIXES,
            openai_client=openai_client
        )
    except Exception as e:
        print(f"Failed to seed Service A: {e}")
    
    # Seed Service B (Order Service)
    print("\n[Service B - Order Service]")
    try:
        seed_qdrant(
            qdrant_url=args.service_b_url,
            collection_name=args.collection,
            fixes=ORDER_SERVICE_FIXES,
            openai_client=openai_client
        )
    except Exception as e:
        print(f"Failed to seed Service B: {e}")
    
    print("\n" + "=" * 60)
    print("Seeding complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()

