# 🧙‍♂️ AI Dota 2 Tracker & High-MMR Coach

An intelligent competitive assistant and analytics platform for **Dota 2**, powered by **FastAPI**, **Google Gemini 2.5 Flash**, **Supabase (pgvector)**, and real-time **STRATZ GraphQL API** Immortal bracket statistics.

The assistant acts as an elite 7000+ MMR coach, delivering instant, structured build progressions, ability mechanics, matchups, and item recipes with zero fluff.

---

## ⚡ Core Features

- **🏆 7000+ MMR Cohesive Itemization**:
  - **4-Phase Game Progression**: Strictly structured into **Starting Items**, **Early Game**, **Mid Game Core**, and **Late Game**.
  - **Multi-Variant Build Understanding**: Identifies alternative playstyles and cleanly separates alternative paths (e.g. *Faceless Void: Build 1 (Maelstrom) vs Build 2 (Battle Fury)*; *Juggernaut: Battle Fury vs Maelstrom*; *Lifestealer: Radiance vs Desolator*) rather than mashing incompatible items together.
  - **Inherent Dota Logic**: Enforces single-boot choice (boots movement speed does not stack), absorbs raw components into completed items, and prevents early greed items (like Hand of Midas) from appearing in late-game builds.
  - **Clean & Direct**: Simple, punchy answers without generic textbook filler or robotic templates.
- **📚 Hybrid RAG Knowledge Base (444 Chunks)**:
  - Complete authoritative kits for **all 127 heroes** (skills, mana costs, cooldowns, BKB pierce status, dispel types, official Aghanim's Scepter & Shard upgrades, and counter matchups).
  - High-MMR item build guides for **all 127 heroes**.
  - Full item catalog with recipe components, gold costs, and active/passive stats for **190 major completed items**.
- **⚡ Hybrid Vector + Entity Search**:
  - Combines SQL keyword entity matching with 768-dimensional cosine vector similarity in Supabase `pgvector` powered by Google's `gemini-embedding-2-preview`.
- **📊 Real-Time Immortal Bracket Statistics**:
  - Live hero win rates and match volumes scraped directly from the STRATZ GraphQL API.
- **☁️ Serverless & Free Deployment**:
  - Optimized for **Vercel Serverless Functions** with automated daily Vercel Cron sync.

---

## 🛠️ Tech Stack

- **Backend Framework**: [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **Database**: [Supabase](https://supabase.com/) (PostgreSQL with `pgvector` extension)
- **Database ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) + [psycopg2](https://www.psycopg.org/)
- **LLM**: [Google Gemini 2.5 Flash](https://ai.google.dev/) via LangChain Google GenAI
- **Embeddings**: Google `gemini-embedding-2-preview` (768 dimensions)
- **Data Providers**: [STRATZ GraphQL API](https://stratz.com/api) & [OpenDota API](https://docs.opendota.com/)
- **Hosting**: [Vercel](https://vercel.com/) (Serverless Functions + Vercel Cron)

---

## 📁 Project Structure

```text
ai-dota-tracker/
├── api/
│   └── index.py                           # FastAPI application entrypoint (REST API & Vercel serverless)
├── app/
│   ├── config.py                          # Pydantic environment configuration
│   ├── database.py                        # SQLAlchemy engine and session pooler
│   ├── models.py                          # SQLAlchemy models (Hero, HeroStat)
│   ├── schemas.py                         # Pydantic request & response schemas
│   ├── data/                              # Precomputed authoritative Dota datasets
│   │   ├── heroes.json                    # All 127 Dota 2 heroes with roles & attributes
│   │   ├── hero_abilities.json            # Full ability kits & talent trees
│   │   ├── hero_builds.json               # 7000+ MMR multi-variant build progressions
│   │   ├── hero_matchups.json             # Top favorable & counter matchups
│   │   ├── items.json                     # Complete item catalog with recipe trees
│   │   ├── abilities.json                 # Ability metadata (mana, CD, dispel, BKB pierce)
│   │   └── aghs_desc.json                 # Official Aghanim's Scepter & Shard upgrades
│   └── services/
│       ├── chatbot.py                     # High-MMR AI Coach logic with Gemini 2.5 Flash
│       ├── rag.py                         # Hybrid RAG search & embedding pipeline
│       └── stratz.py                      # STRATZ GraphQL scraper & DB sync
├── scripts/
│   ├── bulk_ingest_all_dota_knowledge.py  # Bulk ingests all 444 knowledge chunks into Supabase
│   ├── recompute_clean_builds.py          # Builds multi-variant 4-phase hero builds
│   ├── sync_opendota_meta_and_pros.py     # Dota item graph & crafting dependency logic
│   └── run_scraper.py                     # Standalone CLI script for STRATZ stats scraper
├── schema.sql                             # Database DDL for Supabase (tables, indexes, pgvector)
├── vercel.json                            # Vercel deployment routes and daily cron schedule
├── requirements.txt                       # Project Python dependencies
└── .env.example                           # Required environment variables template
```

---

## 🚀 Local Quick Start

### 1. Clone & Set Up Virtual Environment

```bash
# Windows:
python -m venv .venv
.venv\Scripts\activate

# Linux / macOS:
# python3 -m venv .venv
# source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SUPABASE_DB_URL="postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
GOOGLE_API_KEY="your-gemini-api-key"
STRATZ_API_KEY="your-stratz-api-key"
CRON_SECRET="your-random-secret-token"
```

> **Note:** Use Supabase's **Connection Pooler URL** (port `6543`) from your Supabase Dashboard under *Project Settings → Database*.

### 3. Initialize Database & Run Ingestion

1. Execute the SQL definitions in [`schema.sql`](schema.sql) in your **Supabase SQL Editor** to create `heroes`, `hero_stats`, and `hero_documents` (with the `vector` extension).
2. Bulk-ingest the full Dota 2 knowledge catalog into Supabase:
   ```bash
   python scripts/bulk_ingest_all_dota_knowledge.py
   ```
3. Sync the latest Immortal bracket hero statistics from STRATZ:
   ```bash
   python scripts/run_scraper.py
   ```

### 4. Start the Application

```bash
uvicorn api.index:app --reload
```

Visit the interactive Swagger UI at **[http://localhost:8000/docs](http://localhost:8000/docs)** to test the API:
- `POST /chat` — Ask the AI coach questions about hero builds, counter-picks, or item recipes
- `GET /heroes/top` — View top win-rate heroes in the Immortal bracket
- `POST /scraper/sync-meta` — Re-index all Dota knowledge chunks into Supabase
- `POST /scraper/run` — Manually trigger STRATZ stats sync
- `GET /health` — Check database connection status

---

## 💡 Example Queries & Verified Output

### Hero with Alternative Build Paths (`POST /chat`)
**Query:** *"What should i buy on faceless void"*

```markdown
Build 1 (Maelstrom)
• Starting Items: Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet
• Early Game: Power Treads, Magic Wand, Maelstrom
• Mid Game: Manta Style, Black King Bar, Mjollnir
• Late Game: Eye of Skadi, Butterfly, Refresher Orb, Satanic

Build 2 (Battle Fury)
• Starting Items: Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet
• Early Game: Power Treads, Wraith Band, Battle Fury
• Mid Game: Manta Style, Aghanim's Scepter, Black King Bar
• Late Game: Butterfly, Eye of Skadi, Refresher Orb, Swift Blink
```

### Single-Build Support Hero (`POST /chat`)
**Query:** *"What should i buy on Lion?"*

```markdown
• Starting Items: Tango, Blood Grenade, Sentry Ward, Observer Ward, Iron Branch, Magic Stick
• Early Game: Tranquil Boots or Arcane Boots, Magic Wand, Glimmer Cape or Force Staff
• Mid Game: Blink Dagger, Ghost Scepter, Aghanim's Shard, Eul's Scepter or Aeon Disk
• Late Game: Aghanim's Scepter, Scythe of Vyse, Wind Waker, Lotus Orb, Refresher Orb
```

### Item Recipe Query (`POST /chat`)
**Query:** *"How do I build Battle Fury?"*

```markdown
Battle Fury (3900 Gold)
Components: Perseverance, Broadsword, Broadsword, Quelling Blade
Effects: +50 Damage, +7.5 HP Regen, +2.75 Mana Regen. Active: Chop Tree. Passive: Cleave dealing 60% physical damage in a cone.
```

---

## ☁️ Deployment on Vercel

1. Import the repository into [Vercel](https://vercel.com/).
2. Add your environment variables (`SUPABASE_DB_URL`, `GOOGLE_API_KEY`, `STRATZ_API_KEY`, `CRON_SECRET`).
3. Deploy! Vercel will automatically provision:
   - Serverless REST API at `https://your-domain.vercel.app/chat`
   - Automated Daily Cron at `00:00 UTC` via `/api/cron` (configured in [`vercel.json`](vercel.json)).

---

## 📜 License

MIT License
