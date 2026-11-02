-- Run this script in your Supabase SQL Editor if creating tables from scratch
-- or running schema updates.

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
-- Stores chunked Liquipedia knowledge with 768-dimension vector embeddings
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
