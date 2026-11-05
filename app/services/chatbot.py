import logging
import time
import asyncio
from threading import BoundedSemaphore
from typing import Optional, List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from app.config import settings
from app.database import SessionLocal
from app.models import HeroStat
from app.services.errors import ServiceError

logger = logging.getLogger(__name__)
_chat_slots = BoundedSemaphore(settings.CHAT_MAX_CONCURRENT)

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
        logger.warning("Statistics lookup failed (%s)", type(e).__name__)
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
    
    return f"""You are an elite 7000+ MMR Immortal coach and competitive Dota 2 analyst. Write simple, direct answers with zero fluff.

RESPONSE FORMAT FOR HERO BUILDS:
- Structure all hero builds strictly by the 4 game phases:
  • Starting Items: [items]
  • Early Game: [items]
  • Mid Game: [items]
  • Late Game: [items]
- Single Build: If a hero has one standard build, output ONLY the 4 bulleted phases directly. Do NOT write "Build 1" or labels like "Support Utility & Save".
- Multi-Build: If a hero has distinct builds across playstyles or roles (e.g. Maelstrom vs Battle Fury, or Pos 1 Carry vs Pos 3 Offlane), label them simply with their short name: "Build 1 (Pos 1 Carry)" and "Build 2 (Pos 3 Offlane)".
- Role-Specific Queries: If the user explicitly asks for a specific role/position (e.g. "carry magnus", "mid lina", "support pudge"), output ONLY the 4 bulleted phases for that specific role directly. Do NOT list the other roles.
- No Fluff: Output ONLY the clean bullet points. Do NOT add commentary, explanations, or notes after the build unless explicitly asked.

GAMEPLAY & ITEMIZATION LOGIC:
- Follow verified Dota 2 lane mechanics: Bottle is strictly for Mid lane (Pos 2) rune control (water/power runes); side-lane carries and offlaners do NOT buy Bottle.
- Understand item synergies: Mask of Madness provides cheap attack speed and lifesteal for farming and fighting (great on Sven, Void, Carry Magnus); Harpoon provides gap close; BKB provides teamfight magic immunity.
- Never mix incompatible farming items in the same build (e.g. never Battle Fury and Maelstrom together).
- Never recommend multiple boots in a build (boot movement speed does not stack).
- Never list intermediate raw components as separate items alongside completed items.
- Never mention facets.
- Only mention win rates or stats if explicitly asked.

CURRENT IMMORTAL BRACKET STATS REFERENCE:
{stats_data}
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
        max_output_tokens=1000,
        timeout=settings.UPSTREAM_TIMEOUT_SECONDS,
        # This adapter counts the initial request; zero enables SDK defaults.
        max_retries=1,
    )


def _extract_text(content: Any) -> str:
    """Safely extract plain text string from model response content."""
    if content is None:
        return ""
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
    Generate one answer using stored STRATZ statistics and retrieved knowledge.
    Available context depends on the last successful ingestion and retrieval.
    """
    prompt = build_system_prompt()
    
    # RAG: Retrieve matching meta, pro matches, items, and wiki knowledge
    try:
        from app.services.rag import search_dota_knowledge
        docs = search_dota_knowledge(user_input, limit=4, threshold=0.45)
        if docs:
            snippets = [f"[{d['section_title']}]:\n{d['content']}" for d in docs]
            rag_context = "\n\nVERIFIED COMPETITIVE DOTA 2 META & PRO MATCH GROUND TRUTH:\n" + "\n\n".join(snippets)
            prompt += rag_context
    except Exception as rag_err:
        logger.warning("Knowledge lookup failed (%s)", type(rag_err).__name__)

    llm = get_llm(temperature=settings.CHATBOT_TEMPERATURE)
    messages = [
        SystemMessage(content=prompt),
        HumanMessage(content=user_input)
    ]
    
    try:
        response = llm.invoke(messages)
        reply = _extract_text(response.content)
        if not reply:
            raise ServiceError("The model returned no answer. Please try again.")
        return reply
    except ServiceError:
        raise
    except Exception as e:
        err = str(e)
        if "429" in err or "RESOURCE_EXHAUSTED" in err:
            raise ServiceError("The AI service is busy. Please try again in a minute.", 429) from None
        logger.warning("Model request failed (%s)", type(e).__name__)
        raise ServiceError("The AI service is temporarily unavailable. Please try again later.") from None


async def get_chat_response(user_input: str) -> str:
    """Run Chatbot asynchronously without blocking the FastAPI event loop."""
    if not user_input.strip() or len(user_input) > 2000:
        raise ServiceError("Enter a question between 1 and 2,000 characters.", 400)
    # Acquire inside the worker. A cancelled HTTP request cannot release the slot
    # while its synchronous provider call is still running.
    def run_with_slot():
        if not _chat_slots.acquire(blocking=False):
            raise ServiceError("The assistant is busy. Please try again shortly.", 429)
        try:
            return _run_chatbot_sync(user_input)
        finally:
            _chat_slots.release()
    return await asyncio.to_thread(run_with_slot)
