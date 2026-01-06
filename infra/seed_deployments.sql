-- Seed data for Deployments Service
-- Auth release lifecycle and idle window during idp incident

INSERT INTO logs (timestamp, level, raw) VALUES
-- Successful auth release
('2025-01-14 07:45:00', 'INFO', '{"service":"deployments-service","service_owner":"deployments-service","msg":"auth release window started","target_service":"auth-service","release_id":"auth-rel-1401","release_version":"2024.6.3","deploy_slot":"green","region":"us-east"}'),
('2025-01-14 07:45:40', 'INFO', '{"service":"deployments-service","service_owner":"deployments-service","msg":"auth release completed successfully","target_service":"auth-service","release_id":"auth-rel-1401","release_version":"2024.6.3","deploy_slot":"green","region":"us-east"}'),

-- Idle window during idp outage incident
('2025-01-14 11:02:04', 'INFO', '{"service":"deployments-service","service_owner":"deployments-service","msg":"no auth deployments detected in window","target_service":"auth-service","window_minutes":30,"incident_id":"inc_2001","incident_cause":"idp_outage"}');
