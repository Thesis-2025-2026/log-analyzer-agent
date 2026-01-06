-- Seed data for Auth Service
-- Auth login flow: happy paths + idp_outage incident

INSERT INTO logs (timestamp, level, raw) VALUES
-- Happy path #1
('2025-01-14 09:00:12', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"login request accepted at edge","component":"gateway","route":"/api/login","trace_id":"tr_auth_001","request_id":"req_7c2a","user_id":391204,"device":"web","region":"us-east","env":"prod-us-east"}'),
('2025-01-14 09:00:14', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"credentials validated","component":"auth","method":"password","token_latency_ms":42,"trace_id":"tr_auth_001","user_id":391204}'),
('2025-01-14 09:00:15', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"account profile loaded","component":"accounts","loyalty_status":"silver","marketing_opt_in":true,"trace_id":"tr_auth_001","user_id":391204}'),
('2025-01-14 09:00:16', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"session established","component":"session","session_duration_minutes":60,"region_hint":"us-east","trace_id":"tr_auth_001","user_id":391204}'),

-- Happy path #2
('2025-01-14 10:12:02', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"login request accepted at edge","component":"gateway","route":"/api/login","trace_id":"tr_auth_002","request_id":"req_91fd","user_id":812045,"device":"ios","region":"eu-west","env":"prod-eu-west"}'),
('2025-01-14 10:12:04', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"credentials validated","component":"auth","method":"sso","token_latency_ms":33,"trace_id":"tr_auth_002","user_id":812045}'),
('2025-01-14 10:12:05', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"account profile loaded","component":"accounts","loyalty_status":"gold","marketing_opt_in":false,"trace_id":"tr_auth_002","user_id":812045}'),
('2025-01-14 10:12:06', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"session established","component":"session","session_duration_minutes":90,"region_hint":"eu-west","trace_id":"tr_auth_002","user_id":812045}'),

-- Error path (idp_outage incident)
('2025-01-14 11:02:06', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"login request accepted at edge","component":"gateway","route":"/api/login","trace_id":"tr_auth_003","request_id":"req_4b88","user_id":902144,"device":"web","region":"us-east","env":"prod-us-east","incident_id":"inc_2001","incident_cause":"idp_outage"}'),
('2025-01-14 11:02:08', 'WARN', '{"service":"auth-service","service_owner":"auth-service","msg":"authentication rejected","component":"auth","method":"oauth","error_code":"idp_unreachable","retryable":false,"trace_id":"tr_auth_003","user_id":902144,"incident_id":"inc_2001","incident_cause":"idp_outage"}'),

-- Error path (internal signing key issue)
('2025-01-15 13:47:18', 'INFO', '{"service":"auth-service","service_owner":"auth-service","msg":"token signing requested","component":"token","trace_id":"tr_auth_004","request_id":"req_6f2c","user_id":551902,"region":"us-east","env":"prod-us-east"}'),
('2025-01-15 13:47:19', 'ERROR', '{"service":"auth-service","service_owner":"auth-service","msg":"token signing key missing","component":"token","error_code":"signing_key_missing","key_id":"kid_2024_11","trace_id":"tr_auth_004","user_id":551902,"region":"us-east","env":"prod-us-east"}');

INSERT INTO reports (created_at, level, service, title, content, raw_log) VALUES
('2025-01-14 11:05:00', 'WARN', 'auth-service',
 'OAuth login rejected due to idp outage',
 'SEVERITY: MEDIUM (5/10)\n\nROOT CAUSE: OAuth token exchange failed because the identity provider was unreachable.\n\nIMPACT: Users attempting OAuth login saw authentication rejected.\n\nCROSS-SERVICE: idp-service reported provider degraded at 11:02.\n\nRECOMMENDATION: Monitor idp error rates, add retry/backoff, and fall back to password login when possible.',
 '2025-01-14 11:02:08 [WARN] authentication rejected (idp_unreachable)');
