import asyncio
from typing import Optional
from langchain_community.utilities import SQLDatabase
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.agent_toolkits import create_sql_agent
from app.config import settings

PREFIX = """You are a versatile and expert Dota 2 AI assistant. You can engage in general conversations about Dota 2 lore, items, mechanics (e.g., what Aghanim's Scepter does), and esports. Additionally, you are equipped with database tools to analyze hero statistics, win rates, and match counts from the highest skill brackets (Immortal). You must strictly communicate in English.

Strict Constraints:
- Exclusively discuss topics related to Dota 2, heroes, mechanics, items, patches, and esports. If the user asks about ANY unrelated topic, politely decline.
- SECURITY: ONLY generate and execute valid SELECT queries. Never run INSERT, UPDATE, DELETE, ALTER, or DROP commands.

Data Resolution Logic:
- The database stores hero statistics using 'hero_id'. Before querying statistics, resolve the hero's name to its 'hero_id' from the `heroes` table. 
- HISTORICAL DATA BUG PREVENTION: The `hero_stats` table contains records from multiple days. When querying current stats, YOU MUST ONLY use the most recent data. Filter your queries using `WHERE DATE(recorded_at) = (SELECT MAX(DATE(recorded_at)) FROM hero_stats)` or use `DISTINCT ON (hero_id)`.
- If the database query returns no rows or the table is empty, simply state: "No statistics are available in the database yet. Please run the scraper to fetch the latest Immortal stats."
- ROLE FILTERING: If the user asks for a specific role (e.g., 'top carry heroes'), use your internal Dota 2 knowledge to identify traditional heroes for that role and filter using the IN clause.
- FORMATTING: Format your final response concisely, for example: "Top 3 heroes right now: Anti-Mage (55.4%), Pudge (54.2%), Slark (53.1%)."
"""

_agent = None

def get_agent():
    global _agent
    if _agent is None:
        if not settings.sqlalchemy_db_url:
            raise ValueError("SUPABASE_DB_URL is not set.")
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")
            
        # Limit inspection to only our relevant tables to save LLM calls and avoid scanning PostgreSQL system catalogs
        db = SQLDatabase.from_uri(
            settings.sqlalchemy_db_url,
            include_tables=["heroes", "hero_stats"],
            sample_rows_in_table_info=1
        )
        
        llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0
        )
        
        # zero-shot-react-description ensures turns strictly alternate and never end on a model message,
        # perfectly matching Google Gemini's strict conversational API requirements.
        _agent = create_sql_agent(
            llm=llm,
            db=db,
            agent_type="zero-shot-react-description",
            verbose=False,
            max_iterations=5,
            agent_executor_kwargs={"handle_parsing_errors": True},
            prefix=PREFIX
        )
    return _agent


def _run_agent_sync(user_input: str) -> str:
    agent = get_agent()
    try:
        response = agent.invoke({"input": user_input})
        output = response.get('output', '')
        
        if isinstance(output, list):
            output = "".join([item.get('text', '') if isinstance(item, dict) else str(item) for item in output])
        elif isinstance(output, dict) and 'text' in output:
            output = output['text']
            
        result = str(output).strip()
        if not result:
            return "No hero statistics are found in the database yet. Please run the scraper to populate data!"
        return result
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg:
            return "⏳ Rate limit reached on Google Gemini free tier. Please wait 15–20 seconds and ask again!"
        if "No generation chunks" in err_msg:
            return "No statistics are recorded in the database yet. Please run the scraper endpoint (/scraper/run) to fetch today's stats!"
        return f"⚠️ Agent Notice: {err_msg}"


async def get_chat_response(user_input: str) -> str:
    """Run SQL Agent asynchronously without blocking the FastAPI event loop."""
    return await asyncio.to_thread(_run_agent_sync, user_input)
