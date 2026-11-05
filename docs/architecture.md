# Architecture

[Back to the README](../README.md)

AI Dota 2 Tracker is a Python application with a small browser client. FastAPI serves the HTML interface and JSON endpoints; the terminal client calls the same chat service directly. There is no frontend build step.

## Request flow

1. The browser posts a single `message` to `/chat`. Blank messages return HTTP 400; missing fields or messages longer than 2,000 characters return HTTP 422. Middleware rejects bodies above 16 KiB with HTTP 413 before parsing JSON. PostgreSQL atomically enforces a shared request budget before retrieval or generation.
2. [chatbot.py](../app/services/chatbot.py) runs the synchronous retrieval and model work in a worker thread through `asyncio.to_thread`.
3. The service loads hero statistics from PostgreSQL. A process-local cache retains the formatted summary for 600 seconds. Successful scraper API calls invalidate that process's cache; CLI syncs and other serverless instances do not share it.
4. [rag.py](../app/services/rag.py) extracts keywords and uses SQL `ILIKE` matching against document names and titles. It also embeds the question and searches by cosine distance, merging results by category and section title, enforcing the result limit and vector similarity threshold. If embedding fails, it tries keyword matches against titles and content.
5. The service adds the retrieved snippets to a system prompt and calls `ChatGoogleGenerativeAI` with the configured model, temperature, and a 1,000-token output limit.
6. The API returns `{"reply": "...", "status": "success"}`. The browser escapes HTML, formats bold and inline code, and displays the reply.

The browser has a 50-second request timeout. Chat history exists only in the page DOM; it is not included in subsequent API requests or stored in the database.

## Storage

| Table | Contents | Update behavior |
| --- | --- | --- |
| `heroes` | Hero ID, name, and comma-separated roles | STRATZ upsert |
| `hero_stats` | One statistics row per hero, with win rate and match/win counts | STRATZ upsert; not a historical time series |
| `hero_documents` | Text, optional `vector(768)` embeddings, and `embedding_model` | Atomic replacement by the default bulk loader |
| `chat_request_limits` | Shared fixed-window chat counter | Atomic upsert; no user identifiers |

The `hero_documents.hero_name` column is also used for item names and general categories. Its `hero_id` is nullable, and the bulk loader does not populate that foreign key. An HNSW index supports cosine-distance vector queries.

[database.py](../app/database.py) creates the engine lazily and uses `NullPool`. Psycopg 3 connections disable prepared statements for transaction-pooler compatibility; psycopg2 connections receive only options supported by that driver. The example environment selects psycopg 3 explicitly. See the [SQLAlchemy PostgreSQL dialect documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg) for driver URL formats.

## Data freshness

- **Statistics:** [stratz.py](../app/services/stratz.py) asks for Immortal bracket daily results and keeps the latest day returned. `recorded_at` stores the sync time, not the original STRATZ day. `/heroes/top` filters by the latest stored calendar date.
- **Game knowledge:** The standard loader reads checked-in JSON files. It does not contact OpenDota to refresh them.
- **Builds:** A mixture of curated variants and heuristic builds derived from cached item popularity. They are not generated from live match data on each chat request.
- **Cron:** [vercel.json](../vercel.json) schedules stats sync only. Knowledge refresh is a separate maintenance operation.

See [data maintenance](data-maintenance.md) for source files and script effects.

All backend tables have RLS enabled and no browser access is granted by the schema. The application connects as the database owner; a custom restricted backend role needs suitable privileges and RLS policies. Existing installations must apply `migrations/001_security.sql` before deploying.

## Embeddings and retrieval limits

Ingestion and queries share `EMBEDDING_MODEL` (default `gemini-embedding-2`) and request 768 dimensions. Each stored vector records its model; semantic queries exclude incompatible and untagged vectors. No automatic model fallback occurs. Changing this setting requires re-ingestion. Embedding failures leave keyword search available. The query embedding cache is an LRU cache of 256 entries, keyed by model and case-preserving input.

Retrieval deduplicates and caps keywords at eight, uses at most three SELECTs, caps returned documents, and applies the cosine similarity threshold. SQL errors are rolled back before keyword fallback. Latin letters, digits, and hyphens are recognized. Source snippets are not returned as client citations.

## Request budget and failure behavior

`CHAT_REQUESTS_PER_MINUTE` defaults to 30 for the entire deployment. A PostgreSQL upsert counts requests in a fixed one-minute window, including failed requests after admission. Missing storage fails closed with HTTP 503. This budget protects provider usage but is not per-user fairness or a monthly spending cap. A fixed window can allow bursts across its boundary.

`CHAT_MAX_CONCURRENT` defaults to four workers per process. A cancelled request keeps its slot until its provider work actually finishes. `UPSTREAM_TIMEOUT_SECONDS` defaults to 20 seconds per provider request; automatic chat retries are disabled. Database connections have a five-second connection timeout, with transaction-local ten-second statement and five-second lock timeouts. The frontend allows one pending request and waits at most 50 seconds; that timeout can expire before backend work finishes.

Statistics or retrieval failures can still produce an answer with less context. Model failures return HTTP 429 or 503 with a safe error message, and unexpected chat failures return HTTP 500. Successful replies indicate generation completed, not that every context source was available. Internal exceptions and credentials are not included in public error responses.

`/health` runs `SELECT 1`, returning HTTP 200 when connected and HTTP 503 when degraded. It does not inspect schema, freshness, or external API access. The frontend's status badge is static text.

Maintenance requires a configured `CRON_SECRET` and a matching bearer header, compared in constant time. Missing configuration returns HTTP 503; invalid credentials return HTTP 401. Query-string secrets are not accepted. CORS permits public requests without credentials.

There is no startup migration or background ingestion worker. Initialize the schema and populate data separately. Credentials belong in local environment files or hosting settings.
