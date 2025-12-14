-- Seed data for Service B (Order Service)
-- Historical logs for demonstrating cross-service analysis

-- Insert sample order-related error logs
INSERT INTO logs (timestamp, level, raw) VALUES
-- Order processing issues related to payment
('2025-01-10 09:15:30', 'ERROR', '{"service": "order-service", "message": "Order stuck in PENDING_PAYMENT state", "order_id": "ORD-10001", "customer_id": "CUST-456", "wait_time_seconds": 300}'),
('2025-01-10 09:16:50', 'ERROR', '{"service": "order-service", "message": "Payment confirmation timeout for order", "order_id": "ORD-10002", "expected_payment_time": "2025-01-10T09:11:45Z"}'),
('2025-01-10 09:18:00', 'WARN', '{"service": "order-service", "message": "Multiple orders waiting for payment confirmation", "pending_orders": 15, "oldest_order_age_minutes": 10}'),

-- Inventory issues
('2025-01-11 10:00:00', 'ERROR', '{"service": "order-service", "message": "Inventory reservation failed", "order_id": "ORD-10030", "product_id": "PROD-555", "requested_qty": 5, "available_qty": 2}'),
('2025-01-11 10:05:00', 'WARN', '{"service": "order-service", "message": "Low inventory alert", "product_id": "PROD-555", "current_stock": 2, "threshold": 10}'),

-- Fulfillment delays
('2025-01-12 08:32:00', 'ERROR', '{"service": "order-service", "message": "Unable to create shipment - payment not confirmed", "order_id": "ORD-10055", "status": "PENDING_PAYMENT", "wait_time_minutes": 45}'),
('2025-01-12 08:33:00', 'ERROR', '{"service": "order-service", "message": "Batch shipment creation failed", "affected_orders": 12, "reason": "Payment service unavailable"}'),

-- Database issues
('2025-01-13 15:00:00', 'ERROR', '{"service": "order-service", "message": "Order state update failed - database timeout", "order_id": "ORD-10100", "from_state": "PROCESSING", "to_state": "SHIPPED"}'),
('2025-01-13 15:01:00', 'WARN', '{"service": "order-service", "message": "High database latency detected", "avg_query_time_ms": 850, "threshold_ms": 200}'),

-- Successful recoveries
('2025-01-10 09:25:00', 'INFO', '{"service": "order-service", "message": "Pending orders resumed after payment service recovery", "resumed_orders": 15}'),
('2025-01-12 09:00:00', 'INFO', '{"service": "order-service", "message": "Shipment batch completed after payment service restored", "shipped_orders": 12}');

-- Insert sample reports
INSERT INTO reports (created_at, level, service, content, raw_log) VALUES
('2025-01-10 09:30:00', 'ERROR', 'order-service',
 'SEVERITY: HIGH (6/10)\n\nROOT CAUSE: Orders stuck in PENDING_PAYMENT due to payment service timeout.\n\nCROSS-SERVICE IMPACT: Payment gateway timeout cascaded to order service, blocking fulfillment.\n\nAFFECTED ORDERS: 15 orders stuck for 10+ minutes.\n\nRESOLUTION: Orders auto-resumed when payment service recovered. Recommended: Add payment timeout handling with automatic retry.',
 '2025-01-10 09:15:30 [ERROR] Order stuck in PENDING_PAYMENT state'),

('2025-01-12 09:15:00', 'ERROR', 'order-service',
 'SEVERITY: HIGH (7/10)\n\nROOT CAUSE: Payment service database connection pool exhaustion blocked all payment confirmations.\n\nCASCADING EFFECT: Order service unable to process fulfillment for 45 minutes.\n\nAFFECTED: 12 orders could not be shipped.\n\nCROSS-SERVICE CORRELATION: payment-service reported DB pool exhaustion at 08:30:00, order-service failures started at 08:32:00.\n\nRESOLUTION: Payment service fixed connection leak. Order shipments resumed.',
 '2025-01-12 08:32:00 [ERROR] Unable to create shipment - payment not confirmed');

