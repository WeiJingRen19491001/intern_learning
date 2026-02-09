-- Database initialization script
CREATE TABLE IF NOT EXISTS chat_logs (
    id SERIAL PRIMARY KEY,
    session_id VARCHAR,
    request_id VARCHAR NOT NULL,
    user_query TEXT NOT NULL,
    ai_response TEXT,
    sources JSON,
    metadata_info JSON,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_chat_logs_id ON chat_logs (id);
CREATE UNIQUE INDEX IF NOT EXISTS ix_chat_logs_request_id ON chat_logs (request_id);
CREATE INDEX IF NOT EXISTS ix_chat_logs_session_id ON chat_logs (session_id);
