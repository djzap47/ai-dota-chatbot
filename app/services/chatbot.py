import os
import re
import asyncio
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.database import SessionLocal

SYSTEM_PROMPT = """You are a highly knowledgeable, precise Dota 2 AI assistant.
You can answer questions about Dota 2 lore, mechanics, items (Aghanim's Scepter, Shard), patches, and competitive esports.
You also have access to a PostgreSQL database containing the latest Immortal bracket hero statistics.

DATABASE SCHEMA:
1. `heroes` (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    roles TEXT -- Official Valve/STRATZ roles, e.g. 'CARRY, ESCAPE, PUSHER', 'NUKER, DISABLER, SUPPORT'
)
2. `hero_stats` (
    id SERIAL PRIMARY KEY,
    hero_id INTEGER UNIQUE REFERENCES heroes(id),
    hero_name TEXT,
    win_rate FLOAT,
    match_count INTEGER,
    win_count INTEGER,
    recorded_at TIMESTAMPTZ
)
Note: `hero_stats` contains the latest recent Immortal bracket statistics for every hero (exactly one row per hero).

CRITICAL DOTA 2 KNOWLEDGE:
- Anti-Mage's Aghanim's Scepter grants 'Blink Fragment' (summons an illusion that blinks to an enemy or target ground to attack for 7 seconds).
- Anti-Mage's Aghanim's Shard grants 'Counterspell Ally' (allows casting Counterspell on a target teammate). Never confuse Scepter with Shard!

DECISION RULES:
1. If the user asks about mechanics, lore, items, abilities, or gameplay tips:
   - Answer directly and factually in English. DO NOT write SQL.
2. If the user asks for stats, win rates, match counts, meta rankings, or best heroes by role:
   - Output a PostgreSQL SELECT query on the first line starting with 'SQL: SELECT'.
   - To filter by role (carry, support, initiator, nuker, durable, etc.):
     Join `heroes` and `hero_stats` and filter with `h.roles ILIKE '%ROLE%'`.
     Example for carry:
     SQL: SELECT h.name, s.win_rate, s.match_count FROM heroes h JOIN hero_stats s ON h.id = s.hero_id WHERE h.roles ILIKE '%CARRY%' ORDER BY s.win_rate DESC LIMIT 3;
     Example for support:
     SQL: SELECT h.name, s.win_rate, s.match_count FROM heroes h JOIN hero_stats s ON h.id = s.hero_id WHERE h.roles ILIKE '%SUPPORT%' ORDER BY s.win_rate DESC LIMIT 3;
   - To query a specific hero's win rate or matches:
     SQL: SELECT hero_name, win_rate, match_count FROM hero_stats WHERE hero_name ILIKE '%Pudge%';
   - To query top overall heroes:
     SQL: SELECT hero_name, win_rate, match_count FROM hero_stats ORDER BY win_rate DESC LIMIT 5;
   - ONLY produce SELECT queries. Never produce INSERT, UPDATE, DELETE, ALTER, or DROP.
"""

_llm = None

def get_llm():
    global _llm
    if _llm is None:
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")
        _llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0
        )
    return _llm


def _extract_text(content: Any) -> str:
    """Safely extract plain text string from model response content."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "".join(parts).strip()
    return str(content).strip()


def _extract_sql_query(text_content: str) -> Optional[str]:
    """Extract and sanitize SQL query from model output."""
    # Match SQL: ... or ```sql ... ```
    match = re.search(r'SQL:\s*(.*?)(?:$|\n\n)', text_content, re.DOTALL | re.IGNORECASE)
    if match:
        query = match.group(1).strip()
        query = re.sub(r'```(?:sql)?', '', query, flags=re.IGNORECASE).strip('` \n;')
        if query.upper().startswith("SELECT"):
            return query
    
    # Match standalone ```sql SELECT ... ```
    block_match = re.search(r'```(?:sql)?\s*(SELECT.*?)```', text_content, re.DOTALL | re.IGNORECASE)
    if block_match:
        return block_match.group(1).strip().rstrip('; \n`')
        
    if text_content.strip().upper().startswith("SELECT"):
        return text_content.strip().rstrip('; \n`')

    return None


def _execute_readonly_sql(query: str) -> List[Dict[str, Any]]:
    """Safely execute a read-only SELECT query against Supabase."""
    cleaned = query.strip().rstrip(";")
    if not cleaned.upper().startswith("SELECT"):
        raise ValueError("Security violation: Only SELECT queries are permitted.")
    
    # Block destructive SQL operations
    blocked = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE", "GRANT", "REVOKE"]
    for word in blocked:
        if re.search(r'\b' + word + r'\b', cleaned, re.IGNORECASE):
            raise ValueError(f"Security violation: Keyword '{word}' is not allowed.")

    db = SessionLocal()
    try:
        result = db.execute(text(cleaned))
        rows = result.mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


def _run_chatbot_sync(user_input: str) -> str:
    llm = get_llm()
    
    # Step 1: Query Gemini to answer directly or write a SQL query
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_input)
    ]
    
    try:
        response = llm.invoke(messages)
        content = _extract_text(response.content)
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            return "⏳ Rate limit reached on Google Gemini. Please wait 15–20 seconds and ask again!"
        return f"⚠️ Error communicating with Gemini: {err}"

    # Step 2: Check if response contains a SQL query
    sql_query = _extract_sql_query(content)
    if sql_query:
        try:
            db_data = _execute_readonly_sql(sql_query)
        except Exception as sql_err:
            return f"⚠️ Database query failed: {sql_err}"
            
        if not db_data:
            return "No statistics were found matching your query."
            
        # Step 3: Format the final response using the fetched data
        summary_prompt = [
            SystemMessage(content="You are a Dota 2 expert. Summarize these database query results clearly, accurately, and concisely to answer the user's question in a single sentence or brief paragraph."),
            HumanMessage(content=f"User Question: {user_input}\nDatabase Results: {db_data}")
        ]
        
        try:
            summary_response = llm.invoke(summary_prompt)
            return _extract_text(summary_response.content)
        except Exception:
            formatted = ", ".join([f"{row.get('name', row.get('hero_name', 'Hero'))} ({row.get('win_rate', 0)}% WR across {row.get('match_count', 0):,} matches)" for row in db_data])
            return f"Here are the latest stats: {formatted}"

    # Direct answer for mechanics, lore, items, etc.
    return content


async def get_chat_response(user_input: str) -> str:
    """Run Chatbot asynchronously without blocking the FastAPI event loop."""
    return await asyncio.to_thread(_run_chatbot_sync, user_input)
