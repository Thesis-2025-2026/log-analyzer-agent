-- Seed data for Service A (Payment Service)
-- Historical logs for demonstrating cross-service analysis

-- Insert sample payment-related error logs
INSERT INTO logs (timestamp, level, raw) VALUES
-- Payment gateway timeouts
('2025-01-10 09:15:23', 'ERROR', '{"service": "payment-service", "message": "Payment gateway timeout after 5000ms", "order_id": "ORD-10001", "amount": 150.00, "customer_id": "CUST-456"}'),
('2025-01-10 09:16:45', 'ERROR', '{"service": "payment-service", "message": "Bank gateway timeout after 5000ms", "order_id": "ORD-10002", "amount": 299.99, "customer_id": "CUST-789"}'),
('2025-01-11 14:22:10', 'ERROR', '{"service": "payment-service", "message": "Connection timeout to payment processor", "order_id": "ORD-10045", "amount": 89.50, "retry_count": 3}'),

-- Database connection issues
('2025-01-12 08:30:00', 'ERROR', '{"service": "payment-service", "message": "Database connection pool exhausted", "active_connections": 100, "max_connections": 100}'),
('2025-01-12 08:30:15', 'ERROR', '{"service": "payment-service", "message": "HikariPool-1 - Connection is not available, request timed out after 30000ms", "pending_transactions": 45}'),
('2025-01-12 08:31:00', 'WARN', '{"service": "payment-service", "message": "High database connection usage", "usage_percent": 95}'),

-- Transaction failures
('2025-01-13 11:45:30', 'ERROR', '{"service": "payment-service", "message": "Transaction rollback due to deadlock", "transaction_id": "TXN-88901", "order_id": "ORD-10089"}'),
('2025-01-13 16:20:00', 'ERROR', '{"service": "payment-service", "message": "Payment declined by bank", "order_id": "ORD-10102", "decline_code": "51", "reason": "Insufficient funds"}'),

-- Successful recoveries (for context)
('2025-01-10 09:20:00', 'INFO', '{"service": "payment-service", "message": "Payment gateway recovered after restart", "downtime_minutes": 5}'),
('2025-01-12 08:45:00', 'INFO', '{"service": "payment-service", "message": "Database connection pool reset successfully", "new_max_connections": 150}');

-- Insert sample reports
INSERT INTO reports (created_at, level, service, content, raw_log) VALUES
('2025-01-10 09:25:00', 'ERROR', 'payment-service', 
 'SEVERITY: HIGH (7/10)\n\nROOT CAUSE: Payment gateway timeout caused by bank API unresponsiveness.\n\nIMPACT: 15 transactions affected, orders stuck in PENDING_PAYMENT state.\n\nRESOLUTION: Gateway auto-recovered after 5 minutes. Recommended: Increase timeout to 8000ms and add circuit breaker.',
 '2025-01-10 09:15:23 [ERROR] Payment gateway timeout after 5000ms'),

('2025-01-12 09:00:00', 'ERROR', 'payment-service',
 'SEVERITY: CRITICAL (9/10)\n\nROOT CAUSE: Database connection pool exhaustion due to connection leak in payment processor.\n\nIMPACT: All payment processing halted for 15 minutes. 45 pending transactions.\n\nRESOLUTION: Identified unclosed connections in PaymentProcessor.processRefund(). Fixed by adding try-with-resources. Pool size increased to 150.',
 '2025-01-12 08:30:00 [ERROR] Database connection pool exhausted');

