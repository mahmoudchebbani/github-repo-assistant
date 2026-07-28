CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS chunks (
    id           TEXT PRIMARY KEY,
    repo         TEXT NOT NULL,
    source_type  TEXT NOT NULL,
    title        TEXT NOT NULL,
    url          TEXT NOT NULL,
    citation     TEXT NOT NULL,
    text         TEXT NOT NULL,
    embedding    vector(384) NOT NULL,
    lexemes      tsvector GENERATED ALWAYS AS (to_tsvector('english', text)) STORED
);

CREATE INDEX IF NOT EXISTS chunks_embedding_idx ON chunks USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS chunks_lexemes_idx   ON chunks USING gin (lexemes);

CREATE TABLE IF NOT EXISTS conversations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- NULL means the question was asked across every repository, which no slug can claim.
    repo            TEXT,
    question        TEXT NOT NULL,
    answer          TEXT NOT NULL,
    retrieval_mode  TEXT NOT NULL,
    attempts        INTEGER NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Databases created before the all-repositories option still have the old NOT NULL; drop it.
ALTER TABLE conversations ALTER COLUMN repo DROP NOT NULL;

CREATE TABLE IF NOT EXISTS llm_calls (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id    UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    node               TEXT NOT NULL,
    model              TEXT NOT NULL,
    prompt_tokens      INTEGER NOT NULL,
    completion_tokens  INTEGER NOT NULL,
    cost_usd           NUMERIC(16, 10) NOT NULL,
    latency_ms         INTEGER NOT NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS feedback (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id  UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    vote             SMALLINT NOT NULL CHECK (vote IN (-1, 1)),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS llm_calls_conversation_id_idx ON llm_calls (conversation_id);
CREATE INDEX IF NOT EXISTS feedback_conversation_id_idx  ON feedback (conversation_id);
