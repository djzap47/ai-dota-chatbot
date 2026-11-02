import os
import time
import asyncio
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.database import SessionLocal
from app.models import HeroStat

# In-memory cache for the 127 hero stats (cached for 10 minutes to minimize DB queries)
_stats_cache: Optional[str] = None
_stats_cache_time: float = 0.0

def get_hero_stats_summary() -> str:
    """
    Fetch and cache the latest Immortal bracket hero statistics as formatted text.
    All 127 heroes fit into ~900 tokens, enabling instant single-round LLM responses.
    """
    global _stats_cache, _stats_cache_time
    now = time.time()
    
    if _stats_cache and (now - _stats_cache_time < 600):
        return _stats_cache

    try:
        db = SessionLocal()
        try:
            stats = db.query(HeroStat).order_by(HeroStat.win_rate.desc()).all()
            if stats:
                formatted_items = [
                    f"{s.hero_name}: {s.win_rate}% WR ({s.match_count:,} matches)"
                    for s in stats if s.hero_name
                ]
                _stats_cache = " | ".join(formatted_items)
                _stats_cache_time = now
                return _stats_cache
        finally:
            db.close()
    except Exception as e:
        print(f"Warning: Failed to fetch hero stats from DB: {e}")
        if _stats_cache:
            return _stats_cache

    return "No database statistics available yet. Run scraper to populate."


def invalidate_stats_cache():
    """Call after scraper run to force refresh on next request."""
    global _stats_cache, _stats_cache_time
    _stats_cache = None
    _stats_cache_time = 0.0


def build_system_prompt() -> str:
    stats_data = get_hero_stats_summary()
    
    return f"""You are a high-MMR Dota 2 coach, analyst, and passionate player.
You love discussing Dota 2: hero playstyles, lane match-ups, power spikes, item builds, and meta dynamics across all 5 positions.

HOW YOU EVALUATE HERO POSITIONS:
You determine what position a hero belongs to based on your own deep Dota 2 game knowledge and current meta:
- Pos 1: Safe Lane Carry (e.g. Clinkz, Spectre, Juggernaut, Phantom Assassin, Slark, Morphling, Ursa, Faceless Void, Sven, Chaos Knight, Terrorblade, Lifestealer, Anti-Mage, Luna, Monkey King, Drow Ranger, Weaver, Medusa, Troll Warlord, Wraith King)
- Pos 2: Midlane (e.g. Storm Spirit, Ember Spirit, Void Spirit, Puck, Invoker, Queen of Pain, Shadow Fiend, Lina, Sniper, Pangolier, Leshrac)
- Pos 3: Offlane (e.g. Centaur Warrunner, Axe, Mars, Tidehunter, Slardar, Doom, Dark Seer, Primal Beast, Underlord, Night Stalker, Beastmaster)
- Pos 4 / Pos 5: Supports (e.g. Crystal Maiden, Lion, Witch Doctor, Rubick, Shadow Shaman, Hoodwink, Jakiro, Phoenix, Disruptor, Ogre Magi, Treant Protector)

ACCURATE DOTA 2 MECHANICS:
- Anti-Mage's Aghanim's Scepter grants 'Blink Fragment' (summons an illusion that blinks to an enemy or target ground to attack for 7 seconds).
- Anti-Mage's Aghanim's Shard grants 'Counterspell Ally' (allows casting Counterspell on a target teammate). Never confuse Scepter with Shard!

LIVE IMMORTAL BRACKET STATISTICS (from our database, single-day recent snapshot):
{stats_data}

COACHING & CONVERSATIONAL INSTRUCTIONS:
- Talk like a knowledgeable Dota player and coach, NOT a robotic spreadsheet or percentage reporter!
- Don't just list percentages. Discuss the heroes:
  * Why are they so strong or popular in the current meta?
  * What are their key playstyles, power spikes, or core item timings (e.g., Gleipnir, BKB, Desolator, Blink Dagger, Manta Style)?
  * Filter out low match count noise (prioritize heroes with healthy match samples, e.g. >50 matches).
  * How can the player take advantage of them in their own games?
- Cite the real win rates and match samples from the statistics above as factual evidence for your points.
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
        temperature=temp,
        max_output_tokens=600
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


def _run_chatbot_sync(user_input: str) -> str:
    """
    Executes a single, lightning-fast LLM call with live Immortal stats in context.
    Executes in ~3 to 5 seconds, eliminating timeouts on serverless functions.
    """
    llm = get_llm(temperature=settings.CHATBOT_TEMPERATURE)
    prompt = build_system_prompt()
    
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=user_input)
    ]
    
    try:
        response = llm.invoke(messages)
        return _extract_text(response.content)
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            return "⏳ Rate limit reached on Google Gemini. Please wait 15–20 seconds and ask again!"
        return f"⚠️ Error communicating with Gemini: {err}"


async def get_chat_response(user_input: str) -> str:
    """Run Chatbot asynchronously without blocking the FastAPI event loop."""
    return await asyncio.to_thread(_run_chatbot_sync, user_input)
