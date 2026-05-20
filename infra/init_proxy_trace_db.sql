-- Centralized trace storage for distributed agent execution

CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    root_service TEXT,
    root_report_id TEXT
);

CREATE TABLE IF NOT EXISTS agent_calls (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    service_name TEXT,
    agent_name TEXT,
    prompt TEXT,
    response TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL,
    error TEXT,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    total_tokens INTEGER
);
CREATE INDEX IF NOT EXISTS idx_agent_calls_trace_id ON agent_calls(trace_id);

CREATE TABLE IF NOT EXISTS tool_calls (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    service_name TEXT,
    agent_name TEXT,
    tool_name TEXT,
    input TEXT,
    output TEXT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_tool_calls_trace_id ON tool_calls(trace_id);

CREATE TABLE IF NOT EXISTS http_calls (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    service_name TEXT,
    target_service TEXT,
    method TEXT,
    url TEXT,
    request_body TEXT,
    response_body TEXT,
    status_code INTEGER,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_http_calls_trace_id ON http_calls(trace_id);

CREATE TABLE IF NOT EXISTS trace_entries (
    id BIGSERIAL PRIMARY KEY,
    trace_id TEXT NOT NULL,
    parent_event_id BIGINT,
    event_type TEXT NOT NULL,
    service_name TEXT,
    agent_name TEXT,
    tool_name TEXT,
    agent_call_id BIGINT,
    tool_call_id BIGINT,
    http_call_id BIGINT,
    started_at TIMESTAMPTZ,
    ended_at TIMESTAMPTZ,
    duration_ms INTEGER,
    status TEXT NOT NULL,
    error TEXT,
    seq BIGINT
);

CREATE INDEX IF NOT EXISTS idx_trace_entries_trace_id ON trace_entries(trace_id);
CREATE INDEX IF NOT EXISTS idx_trace_entries_parent ON trace_entries(parent_event_id);

-- Migration: add token usage columns to agent_calls (idempotent)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='agent_calls' AND column_name='prompt_tokens') THEN
        ALTER TABLE agent_calls ADD COLUMN prompt_tokens INTEGER;
        ALTER TABLE agent_calls ADD COLUMN completion_tokens INTEGER;
        ALTER TABLE agent_calls ADD COLUMN total_tokens INTEGER;
    END IF;
END $$;
