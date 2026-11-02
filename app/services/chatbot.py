import os
import re
import asyncio
from typing import Optional, List, Dict, Any
from sqlalchemy import text
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.database import SessionLocal

SYSTEM_PROMPT = """You are a high-MMR Dota 2 coach, analyst, and passionate player.
You love discussing Dota 2: hero playstyles, lane match-ups, power spikes, item builds, and meta dynamics across all 5 positions:
- Pos 1: Safe Lane Carry (e.g. Clinkz, Spectre, Juggernaut, Phantom Assassin, Slark, Morphling, Ursa, Faceless Void, Sven, Chaos Knight, Terrorblade, Lifestealer, Anti-Mage, Luna, Monkey King, Drow Ranger, Weaver, Medusa, Troll Warlord, Wraith King)
- Pos 2: Midlane (e.g. Storm Spirit, Ember Spirit, Void Spirit, Puck, Invoker, Queen of Pain, Shadow Fiend, Lina, Sniper, Pangolier, Leshrac)
- Pos 3: Offlane (e.g. Centaur Warrunner, Axe, Mars, Tidehunter, Slardar, Doom, Dark Seer, Primal Beast, Underlord, Night Stalker, Beastmaster)
- Pos 4 / Pos 5: Supports (e.g. Crystal Maiden, Lion, Witch Doctor, Rubick, Shadow Shaman, Hoodwink, Jakiro, Phoenix, Disruptor, Ogre Magi, Treant Protector)

You have access to a PostgreSQL database containing the latest single-day Immortal bracket hero statistics.

DATABASE SCHEMA:
- `hero_stats` (
    hero_id INTEGER UNIQUE,
    hero_name TEXT,
    win_rate FLOAT,
    match_count INTEGER,
    win_count INTEGER,
    recorded_at TIMESTAMPTZ
)

RULES FOR DECIDING HOW TO RESPOND:
1. When asked about mechanics, lore, items, abilities, or general gameplay tips:
   - Answer directly and conversationally with deep Dota 2 expertise. DO NOT write SQL.
   - Key accurate mechanics:
     * Anti-Mage Aghanim's Scepter grants 'Blink Fragment' (summons an illusion that blinks to an enemy or target ground to attack for 7 seconds).
     * Anti-Mage Aghanim's Shard grants 'Counterspell Ally' (casts Counterspell on a target teammate). Never confuse Scepter with Shard!

2. When asked for meta stats, win rates, match counts, or best heroes for a position/role (e.g. "Top carry heroes", "best midlaners", "Pudge win rate"):
   - Output a clean PostgreSQL SELECT query on the first line starting with 'SQL: SELECT'.
   - Use your own Dota 2 knowledge to select the candidate heroes that belong to that position.
   - Always filter for meaningful sample sizes (e.g. `match_count > 50`) to avoid low-sample outliers.
   - Examples:
     * User: "Top 3 carry heroes right now?"
       SQL: SELECT hero_name, win_rate, match_count FROM hero_stats WHERE hero_name IN ('Clinkz', 'Spectre', 'Juggernaut', 'Phantom Assassin', 'Slark', 'Morphling', 'Ursa', 'Faceless Void', 'Sven', 'Chaos Knight', 'Terrorblade', 'Lifestealer', 'Anti-Mage', 'Luna', 'Drow Ranger', 'Monkey King', 'Weaver', 'Medusa', 'Troll Warlord', 'Wraith King') AND match_count > 50 ORDER BY win_rate DESC LIMIT 5;
     * User: "What is Pudge's current win rate and match count?"
       SQL: SELECT hero_name, win_rate, match_count FROM hero_stats WHERE hero_name ILIKE '%Pudge%';
     * User: "Best offlaners currently?"
       SQL: SELECT hero_name, win_rate, match_count FROM hero_stats WHERE hero_name IN ('Centaur Warrunner', 'Axe', 'Mars', 'Tidehunter', 'Slardar', 'Doom', 'Dark Seer', 'Primal Beast', 'Underlord', 'Night Stalker', 'Beastmaster', 'Dragon Knight') AND match_count > 50 ORDER BY win_rate DESC LIMIT 5;
     * User: "Highest win rate heroes overall?"
       SQL: SELECT hero_name, win_rate, match_count FROM hero_stats WHERE match_count > 100 ORDER BY win_rate DESC LIMIT 5;
   - ONLY produce SELECT queries. Never produce INSERT, UPDATE, DELETE, ALTER, or DROP.
"""

SUMMARY_SYSTEM_PROMPT = """You are a high-MMR Dota 2 coach and analyst having an engaging conversation with a fellow player.
You retrieved real-time Immortal bracket statistics from the database to answer the user's question.

CRITICAL INSTRUCTIONS:
- Talk like a knowledgeable Dota player and coach, NOT a robotic spreadsheet or percentage reporter!
- Don't just list percentages. Discuss the heroes:
  * Why are they so strong or popular in the current meta?
  * What are their key playstyles, power spikes, or core item timings (e.g., Gleipnir, BKB, Desolator, Blink Dagger, Manta Style)?
  * How can the player take advantage of them in their own games?
- Cite the win rates and match samples naturally as factual backing for your analysis.
- Keep the tone passionate, insightful, and enjoyable to read.
"""


def get_llm(temperature: Optional[float] = None) -> ChatGoogleGenerativeAI:
    """Create a Gemini LLM instance with specified temperature."""
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not set.")
    
    temp = settings.CHATBOT_TEMPERATURE if temperature is None else temperature
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        google_api_key=settings.GOOGLE_API_KEY,
        temperature=temp
    )


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
    match = re.search(r'SQL:\s*(.*?)(?:$|\n\n)', text_content, re.DOTALL | re.IGNORECASE)
    if match:
        query = match.group(1).strip()
        query = re.sub(r'```(?:sql)?', '', query, flags=re.IGNORECASE).strip('` \n;')
        if query.upper().startswith("SELECT"):
            return query
    
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
    chat_llm = get_llm(temperature=settings.CHATBOT_TEMPERATURE)
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=user_input)
    ]
    
    try:
        response = chat_llm.invoke(messages)
        content = _extract_text(response.content)
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            return "⏳ Rate limit reached on Google Gemini. Please wait 15–20 seconds and ask again!"
        return f"⚠️ Error communicating with Gemini: {err}"

    # Step 2: Check if response is a SQL query
    sql_query = _extract_sql_query(content)
    if sql_query:
        try:
            db_data = _execute_readonly_sql(sql_query)
        except Exception as sql_err:
            return f"⚠️ Database query failed: {sql_err}"
            
        if not db_data:
            return "I couldn't find any recent Immortal match statistics matching that query."
            
        # Step 3: Conversational analysis using high-MMR coach persona
        summary_prompt = [
            SystemMessage(content=SUMMARY_SYSTEM_PROMPT),
            HumanMessage(content=f"User Question: {user_input}\nImmortal Bracket Database Results: {db_data}")
        ]
        
        try:
            summary_response = chat_llm.invoke(summary_prompt)
            return _extract_text(summary_response.content)
        except Exception:
            formatted = ", ".join([f"{row.get('hero_name', 'Hero')} ({row.get('win_rate', 0)}% WR across {row.get('match_count', 0):,} matches)" for row in db_data])
            return f"Here are the latest Immortal stats: {formatted}"

    # Direct conversational answer (lore, mechanics, strategy, builds)
    return content


async def get_chat_response(user_input: str) -> str:
    """Run Chatbot asynchronously without blocking the FastAPI event loop."""
    return await asyncio.to_thread(_run_chatbot_sync, user_input)
