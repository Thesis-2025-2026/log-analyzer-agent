-- Seed data for IDP Service
-- OAuth provider health checks (healthy + degraded)

INSERT INTO logs (timestamp, level, raw) VALUES
-- Healthy provider check
('2025-01-14 08:30:00', 'INFO', '{"service":"idp-service","service_owner":"idp-service","msg":"oauth provider health check started","component":"idp","provider":"okta","region":"us-east"}'),
('2025-01-14 08:30:12', 'INFO', '{"service":"idp-service","service_owner":"idp-service","msg":"provider responded healthy","component":"idp","provider":"okta","region":"us-east","error_rate":0.002}'),

-- Degraded provider tied to auth incident
('2025-01-14 11:02:03', 'INFO', '{"service":"idp-service","service_owner":"idp-service","msg":"oauth provider health check started","component":"idp","provider":"auth0","region":"us-east","incident_id":"inc_2001","incident_cause":"idp_outage"}'),
('2025-01-14 11:02:05', 'WARN', '{"service":"idp-service","service_owner":"idp-service","msg":"provider degraded","component":"idp","provider":"auth0","region":"us-east","error_rate":0.18,"failure_mode":"token_endpoint_timeout","incident_id":"inc_2001","incident_cause":"idp_outage"}');
