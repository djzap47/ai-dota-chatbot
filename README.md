# 🧙‍♂️ AI Dota 2 Tracker & Chatbot

An intelligent analytics platform and AI assistant for Dota 2 powered by **FastAPI**, **Google Gemini 2.5 Flash**, **LangChain**, and **Supabase (PostgreSQL)**.

It continuously tracks hero win rates and match statistics from the highest skill bracket (**Immortal**) via the **STRATZ GraphQL API**, allowing you to ask complex questions in natural language and receive accurate answers derived directly from live database statistics.

---

## ⚡ Features

- **🤖 AI SQL Agent**: Chat naturally about Dota 2 lore, mechanics, counters, or ask for statistics like *"Top 3 carry heroes right now?"* and the AI dynamically translates your query into read-only SQL queries.
- **🚀 High-Performance FastAPI Backend**: Lightweight, asynchronous REST API with auto-generated interactive documentation at `/docs`.
- **📊 Daily Immortal Scraper**: Automated data synchronization fetching daily hero statistics and win rates directly from STRATZ.
- **🛡️ Secure & Safe**: The AI agent is strictly restricted to `SELECT` queries to prevent data corruption.
- **☁️ 100% Free Hosting on Vercel**: Ready for one-click deployment to Vercel Serverless Functions with native daily Cron jobs.

---

## 🛠️ Tech Stack

- **Framework**: [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/)
- **Database ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) + [psycopg2](https://www.psycopg.org/)
- **Database**: [Supabase](https://supabase.com/) (PostgreSQL)
- **AI & LLM**: [Google Gemini 2.5 Flash](https://ai.google.dev/) via [LangChain](https://www.langchain.com/)
- **Data Source**: [STRATZ GraphQL API](https://stratz.com/api)
- **Hosting**: [Vercel](https://vercel.com/) (Serverless + Vercel Cron)

---

## 📁 Project Structure

```text
ai-dota-tracker/
├── api/
│   └── index.py             # FastAPI entrypoint for Vercel & local development
├── app/
│   ├── config.py            # Pydantic environment configuration
│   ├── database.py          # SQLAlchemy engine and session dependency
│   ├── models.py            # SQLAlchemy models (Hero, HeroStat)
│   ├── schemas.py           # Pydantic request & response schemas
│   └── services/
│       ├── chatbot.py       # LangChain SQL agent with Gemini 2.5 Flash
│       └── stratz.py        # STRATZ GraphQL client & DB sync
├── scripts/
│   └── run_scraper.py       # Standalone CLI script to trigger scraper
├── bot.py                   # Local terminal interactive chatbot
├── schema.sql               # Database DDL for Supabase
├── vercel.json              # Vercel routing, timeout, and cron configuration
├── requirements.txt         # Project dependencies
└── .env.example             # Template for required environment variables
```

---

## 🚀 Local Quick Start

### 1. Clone & Install Dependencies

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
# source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SUPABASE_DB_URL="postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:6543/postgres"
GOOGLE_API_KEY="your-gemini-api-key"
STRATZ_API_KEY="your-stratz-api-key"
CRON_SECRET="any_random_secret_string"
```

> **Tip:** For serverless environments like Vercel, use Supabase's **Connection Pooler URL** (port `6543`) from your Supabase Dashboard under *Project Settings → Database*.

### 3. Initialize Database Tables

Run the SQL statements in [`schema.sql`](schema.sql) in your **Supabase SQL Editor** to create the `heroes` and `hero_stats` tables.

### 4. Populate Initial Stats

Fetch the latest Immortal stats from STRATZ:

```bash
python scripts/run_scraper.py
```

### 5. Start the FastAPI Server

```bash
uvicorn api.index:app --reload
```

Visit the interactive Swagger UI at **[http://localhost:8000/docs](http://localhost:8000/docs)** to test the endpoints:
- `POST /chat` — Send a query to the Dota 2 AI assistant
- `GET /heroes/top` — View top win rate heroes
- `POST /scraper/run` — Manually trigger the STRATZ data sync
- `GET /health` — Check database connection status

*(Optional)* You can also run the terminal chatbot:
```bash
python bot.py
```

---

## ☁️ How to Host on Vercel

### Step 1: Push Code to GitHub

```bash
git add .
git commit -m "Migrate from Django to FastAPI with Vercel support"
git push origin main
```

### Step 2: Import into Vercel

1. Go to [vercel.com](https://vercel.com/) and click **Add New... → Project**.
2. Select your `ai-dota-tracker` repository.
3. Keep default build and output settings (Vercel automatically detects `api/index.py` and `requirements.txt`).

### Step 3: Add Environment Variables in Vercel

Under **Environment Variables**, add:
- `SUPABASE_DB_URL`: Your Supabase pooled connection string (`port 6543`)
- `GOOGLE_API_KEY`: Your Google Gemini API key
- `STRATZ_API_KEY`: Your STRATZ API token
- `CRON_SECRET`: A secret string used by Vercel Cron to authorize the daily scraper

### Step 4: Deploy!

Click **Deploy**. Once finished, Vercel gives you a public URL (e.g. `https://your-app.vercel.app`):
- API documentation: `https://your-app.vercel.app/docs`
- Chat endpoint: `POST https://your-app.vercel.app/chat`
- Daily Scraper Cron: Vercel will automatically call `GET /api/cron` every night at `00:00 UTC` using the configuration defined in [`vercel.json`](vercel.json).

---

## 📜 License

MIT License
