# Architecture

[Back to the README](../README.md)

AI Dota 2 Tracker is a Python application with a small browser client. FastAPI serves the HTML interface and JSON endpoints; the terminal client calls the same chat service directly. There is no frontend build step.

## Request flow

1. The browser posts a single `message` to `/chat`. Blank messages return HTTP 400, and missing required fields return HTTP 422.
2. [chatbot.py](../app/services/chatbot.py) runs the synchronous retrieval and model work in a worker thread through `asyncio.to_thread`.
3. The service loads hero statistics from PostgreSQL. A process-local cache retains the formatted summary for 600 seconds. Successful scraper API calls invalidate that process's cache; CLI syncs and other serverless instances do not share it.
4. [rag.py](../app/services/rag.py) extracts keywords and uses SQL `ILIKE` matching against document names and titles. It also embeds the question and searches by cosine distance, merging results by section title. If embedding fails, it tries keyword matches against titles and content.
5. The service adds the retrieved snippets to a system prompt and calls `ChatGoogleGenerativeAI` with the configured model, temperature, and a 1,000-token output limit.
6. The API returns `{"reply": "...", "status": "success"}`. The browser escapes HTML, formats bold and inline code, and displays the reply.

The browser has a 50-second request timeout. Chat history exists only in the page DOM; it is not included in subsequent API requests or stored in the database.

## Storage

| Table | Contents | Update behavior |
| --- | --- | --- |
| `heroes` | Hero ID, name, and comma-separated roles | STRATZ upsert |
| `hero_stats` | One statistics row per hero, with win rate and match/win counts | STRATZ upsert; not a historical time series |
| `hero_documents` | Hero, item, and mechanics text with optional `vector(768)` embeddings | Full replacement by the default bulk loader |

The `hero_documents.hero_name` column is also used for item names and general categories. Its `hero_id` is nullable, and the bulk loader does not populate that foreign key. An HNSW index supports cosine-distance vector queries.

[database.py](../app/database.py) creates the engine lazily and uses `NullPool`. Psycopg 3 connections disable prepared statements for transaction-pooler compatibility; psycopg2 connections receive only options supported by that driver. The example environment selects psycopg 3 explicitly. See the [SQLAlchemy PostgreSQL dialect documentation](https://docs.sqlalchemy.org/en/20/dialects/postgresql.html#module-sqlalchemy.dialects.postgresql.psycopg) for driver URL formats.

## Data freshness

- **Statistics:** [stratz.py](../app/services/stratz.py) asks for Immortal bracket daily results and keeps the latest day returned. `recorded_at` stores the sync time, not the original STRATZ day. `/heroes/top` filters by the latest stored calendar date.
- **Game knowledge:** The standard loader reads checked-in JSON files. It does not contact OpenDota to refresh them.
- **Builds:** A mixture of curated variants and heuristic builds derived from cached item popularity. They are not generated from live match data on each chat request.
- **Cron:** [vercel.json](../vercel.json) schedules stats sync only. Knowledge refresh is a separate maintenance operation.

See [data maintenance](data-maintenance.md) for source files and script effects.

## Embeddings and retrieval limits

The runtime and primary bulk-ingestion helper try `gemini-embedding-2-preview`, then `gemini-embedding-2`, then `gemini-embedding-001`, requesting 768 dimensions. Model availability depends on the configured Google account. The chat model is separately controlled by `GEMINI_MODEL`.

Embeddings from different models are not guaranteed to share a comparable vector space. The fallback chain can mix models because the database does not record which model produced each row. Rebuild the index when intentionally changing the embedding model, and keep ingestion and query generation consistent. The older `sync_opendota_knowledge.py` script uses its own embedding helper.

Other current retrieval limits:

- The `threshold` argument is accepted but is not applied as a similarity cutoff.
- Keyword extraction currently recognizes Latin letters, digits, underscores, and hyphens.
- The embedding cache holds up to 256 normalized questions per process; it does not evict older entries once full.
- Retrieved source snippets are used internally but are not returned as citations to the client.

## Failure behavior and deployment

If statistics or retrieval fail, chat may still answer using the model with less context. Some Gemini errors are returned as reply text with a `success` status; other exceptions become HTTP 500. A successful chat response therefore does not prove that retrieval or model generation succeeded.

`/health` executes `SELECT 1` and returns HTTP 200 with either `healthy` or `degraded` in its JSON body. It does not inspect the schema, data freshness, or external API access. The frontend's “Immortal Stats Online” badge is static text, not a health probe.

The scraper routes compare a configured `CRON_SECRET` against a bearer header or a `secret` query parameter. When the secret is empty, authentication is skipped. Prefer the header when calling these routes. There is currently no application-level user authentication or rate limiting, and CORS allows all origins.

The API has no startup migration or background ingestion worker. Initialize the schema and populate data separately. Credentials belong in local environment files or the hosting platform's environment settings.
