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
