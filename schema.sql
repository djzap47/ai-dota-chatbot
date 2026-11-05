-- Run this script in your Supabase SQL Editor if creating tables from scratch
-- or running schema updates.

-- pgvector must be enabled before creating vector columns and indexes.
CREATE EXTENSION IF NOT EXISTS vector;

-- Table: heroes
-- Stores base hero information with official Valve/STRATZ roles
CREATE TABLE IF NOT EXISTS heroes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    roles TEXT
);

-- Table: hero_stats
-- Stores the latest current statistics for heroes (one row per hero)
CREATE TABLE IF NOT EXISTS hero_stats (
    id SERIAL PRIMARY KEY,
    hero_id INTEGER NOT NULL REFERENCES heroes(id) ON DELETE CASCADE,
    hero_name TEXT,
    win_rate FLOAT,
    match_count INTEGER,
    win_count INTEGER,
    recorded_at TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT unique_hero_id UNIQUE (hero_id)
);

-- Table: hero_documents
-- Stores hero, item, and mechanics knowledge with 768-dimension embeddings
CREATE TABLE IF NOT EXISTS hero_documents (
    id SERIAL PRIMARY KEY,
    hero_id INTEGER REFERENCES heroes(id) ON DELETE CASCADE,
    hero_name TEXT NOT NULL,
    section_title TEXT NOT NULL,
    content TEXT NOT NULL,
    embedding vector(768),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast approximate nearest neighbor vector search
CREATE INDEX IF NOT EXISTS hero_documents_embedding_idx 
ON hero_documents USING hnsw (embedding vector_cosine_ops);

-- Run once on an existing installation before deploying this release.
-- Existing vectors remain untagged; re-ingest to generate compatible vectors.
BEGIN;
ALTER TABLE public.hero_documents ADD COLUMN IF NOT EXISTS embedding_model TEXT;
CREATE TABLE IF NOT EXISTS public.chat_request_limits (
    name TEXT PRIMARY KEY,
    window_start TIMESTAMPTZ NOT NULL,
    request_count INTEGER NOT NULL CHECK (request_count > 0)
);
ALTER TABLE public.heroes ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hero_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.hero_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.chat_request_limits ENABLE ROW LEVEL SECURITY;
-- The backend connects as the database owner. Browser roles need no table access.
DO $$
DECLARE client_role TEXT;
BEGIN
    FOREACH client_role IN ARRAY ARRAY['anon', 'authenticated'] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = client_role) THEN
            EXECUTE format('REVOKE ALL ON TABLE public.heroes, public.hero_stats, public.hero_documents, public.chat_request_limits FROM %I', client_role);
        END IF;
    END LOOP;
END $$;
COMMIT;
