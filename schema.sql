-- Run this script in your Supabase SQL Editor to create the required tables

-- Table: heroes
-- Stores the base hero information
CREATE TABLE IF NOT EXISTS heroes (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

-- Table: hero_stats
-- Stores daily statistics for heroes
CREATE TABLE IF NOT EXISTS hero_stats (
    id SERIAL PRIMARY KEY,
    hero_id INTEGER REFERENCES heroes(id) ON DELETE CASCADE,
    hero_name TEXT,
    win_rate FLOAT,
    match_count INTEGER,
    win_count INTEGER,
    recorded_at TIMESTAMPTZ DEFAULT NOW()
);
