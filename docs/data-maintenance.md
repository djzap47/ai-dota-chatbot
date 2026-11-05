# Data maintenance

[Back to the README](../README.md)

Run scripts from the repository root with your virtual environment activated. The normal application reads knowledge from PostgreSQL; changing a JSON file alone does not update chat retrieval.

## Bundled snapshot

| File in `app/data/` | Entries | Purpose |
| --- | ---: | --- |
| `heroes.json` | 127 | Hero identifiers, attributes, roles, and base stats |
| `hero_abilities.json` | 127 | Ability keys, talents, and facet metadata by hero |
| `abilities.json` | 3,084 | Ability and talent definitions |
| `aghs_desc.json` | 127 | Aghanim's Scepter and Shard descriptions |
| `items.json` | 501 | Item constants, including components and recipes |
| `hero_builds.json` | 127 | 159 build variants using four game phases |
| `hero_matchups.json` | 127 | Favorable and unfavorable matchup summaries |
| `raw_popularity.json` | 105 | Cached OpenDota item-popularity responses |
| `game_mechanics.json` | 6 | Project-maintained mechanics and role guides |

Counts describe the checked-in snapshot. The files do not include a shared patch ID or retrieval timestamp. Downloaded constants, curated text, and popularity caches can reflect different points in time.

The bulk loader makes two documents per hero, selects 190 major or neutral items, and adds the six mechanics documents, for 450 total. It excludes recipe-only entries and some inexpensive items. The presence of facet metadata in a source file does not imply facet support in chat: the current prompt tells the model not to mention facets.

## Routine operations

### Refresh statistics

```bash
python scripts/run_scraper.py
```

Requires `SUPABASE_DB_URL` and `STRATZ_API_KEY`. Updates `heroes` and `hero_stats`, keeping one statistics row per hero. The scheduled `/api/cron` route runs this same scraper; API-triggered syncs also invalidate their process's chat statistics cache.

### Rebuild the knowledge index

```bash
python scripts/bulk_ingest_all_dota_knowledge.py
```

Requires `SUPABASE_DB_URL`; `GOOGLE_API_KEY` is needed for embeddings. **This truncates `hero_documents` and commits the deletion before inserting new data.** It also removes any documents previously added by alternate ingestion scripts. Save custom knowledge separately before running it.

Text is committed before vector generation. If embedding quota is exhausted, the text remains searchable by keywords, while some rows may have no vector. The reported document count is not an embedding-coverage count. The `/scraper/sync-meta` endpoint invokes this loader as well.

### Refresh game constants

```bash
python scripts/download_bulk_constants.py
```

Downloads heroes, items, abilities, hero ability mappings, and Aghanim's descriptions from the `dotaconstants` package via its CDN. It overwrites those five JSON files. Review the changes before rebuilding the index; this script does not refresh builds, matchups, mechanics text, or the popularity cache.

### Regenerate builds

```bash
python scripts/recompute_clean_builds.py
```

Uses curated entries from `CURATED_BUILDS` and `DotaItemGraph` heuristics for other heroes. Existing entries in `raw_popularity.json` are reused; only missing popularity data is fetched. It overwrites `hero_builds.json` and the popularity cache. Review any manual edits to those files first, because regeneration can replace them.

After making dataset changes, run the offline tests and inspect the diff before re-ingesting:

```bash
python -m unittest discover -s tests -v
git diff --stat
git diff -- app/data/
```

## Other scripts

These are separate maintenance paths, not prerequisites for the quick start.

| Script | What it does | Important behavior |
| --- | --- | --- |
| `fetch_hero_builds_and_matchups.py` | Downloads OpenDota popularity and matchups into local files | Uses the older flat build format. Run the current build generator afterward before bulk ingestion. Existing matchup entries are reused. |
| `sync_opendota_meta_and_pros.py` | Fetches hero meta and pro match records, then writes embedded documents | Calls OpenDota and Gemini; replaces documents by category/name. Also contains the item graph and embedding helper used by other scripts. |
| `sync_opendota_knowledge.py` | Fetches items, heroes, teams, tournaments, and patch notes | Uses a separate embedding helper and skips categories already present. It is not a complete refresh of existing knowledge. |
| `ingest_all_heroes_rag.py` | Fetches Valve hero data and writes ability/upgrade documents | Deletes existing documents per hero. Referenced heroes must already exist in `heroes`. |
| `ingest_liquipedia.py` | Fetches selected Liquipedia hero sections | Deletes existing documents per hero; its CLI targets five example heroes. Configure an appropriate contact user-agent before use. |
| `migrate_and_sync.py` | Adds roles, deduplicates old stats, adds uniqueness, then syncs STRATZ | Deletes older duplicate stats rows. Review before using on an existing database; unnecessary for a new database initialized with `schema.sql`. |

Some download scripts execute network requests and file writes at import time. Run them intentionally as commands; avoid importing them from tests or application startup. Live ingestion may consume provider quota and can take longer than a serverless request allows.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| `type "vector" does not exist` | Run the extension statement in `schema.sql`; see [Supabase's pgvector guide](https://supabase.com/docs/guides/database/extensions/pgvector). |
| Database connection fails | Check the pooler URI, password encoding, and SSL mode. The template selects `postgresql+psycopg://`. |
| `/heroes/top` returns an empty list | Initialize the schema and complete a STRATZ scraper run. |
| Chat says no statistics are available | Check database connectivity and the last successful scraper run. |
| Hero builds contain missing sections | Verify that `hero_builds.json` uses a `builds` list with `starting`, `early`, `mid`, and `late` fields. |
| New local data does not appear in chat | Re-run bulk ingestion against the same database the app uses. |
| Embedding or model errors | Check Google API access, model availability, and quota. `GEMINI_MODEL` controls chat only. |
| Scraper API returns HTTP 401 | Send the configured `CRON_SECRET` in an authorization header. |

For a bug report, include the command, sanitized error, Python version, and whether you ran locally or on Vercel. Do not include API tokens or your full database URI.
