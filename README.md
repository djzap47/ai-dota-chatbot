# AI Dota 2 Tracker

An interactive chat assistant powered by **Gemini 2.5 Flash** and **Langchain**. It uses a **Supabase** database to analyze high-level Dota 2 statistics. The project includes a lightweight **Django-based scraper** that fetches up-to-date hero win rates for the **Immortal bracket** via the **STRATZ API**.

## Key Features
- **AI Chatbot**: Chat naturally about Dota 2 lore, mechanics, and esports.
- **Real-Time Data**: Ask questions like "Top 3 carry heroes?" and the AI will generate SQL to answer using live data.
- **Lightweight Django Backend**: Uses Django's powerful ORM and management commands purely as an automated background scraper to pull the latest Immortal stats from STRATZ, without the overhead of a full web server.
- **Secure**: The AI is strictly limited to `SELECT` operations to prevent database corruption.

## Tech Stack
- **Python**
- **Langchain & Gemini** (AI logic)
- **Supabase** (PostgreSQL)
- **Django ORM** (Database modeling & data ingestion)
- **STRATZ GraphQL API** (Data source)

## Quick Start

### 1. Install
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure
Create a `.env` file in the root directory:
```env
SUPABASE_DB_URL="postgresql://[user]:[password]@[host]:[port]/[db]"
GOOGLE_API_KEY="your-gemini-key"
STRATZ_API_KEY="your-stratz-key"
```

### 3. Setup Database
If you are starting with a fresh Supabase database, copy the contents of `schema.sql` and run it in your Supabase SQL Editor to create the required tables.

### 4. Fetch Data
Run the scraper to populate your database with current stats:
```bash
python manage.py run_scraper
```
*(Press `Ctrl+C` once the fetch is complete)*

### 5. Run Bot
```bash
python bot.py
```

## License
MIT License
