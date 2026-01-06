CREATE TABLE IF NOT EXISTS logs (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level TEXT,
    raw JSONB
);

-- Stores analysis reports
CREATE TABLE IF NOT EXISTS reports (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    level TEXT,
    service TEXT,
    content TEXT NOT NULL,
    raw_log TEXT
);

CREATE INDEX IF NOT EXISTS idx_reports_created_at ON reports (created_at DESC);
