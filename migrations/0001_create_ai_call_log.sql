-- Minimal migration: create ai_call_log table for SQLite
CREATE TABLE IF NOT EXISTS ai_call_log (
    id INTEGER PRIMARY KEY,
    image_id INTEGER,
    call_type TEXT NOT NULL,
    status TEXT NOT NULL,
    model_name TEXT,
    model_version TEXT,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    total_tokens INTEGER NOT NULL DEFAULT 0,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    retry_count INTEGER NOT NULL DEFAULT 0,
    cost_usd REAL NOT NULL DEFAULT 0.0,
    meta JSON,
    created_at DATETIME DEFAULT (datetime('now'))
);
