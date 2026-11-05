import os
import sys

# Ensure Vercel serverless function can find the 'app' module in the root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import asyncio
import logging
import secrets
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.config import settings
from app.database import get_db, SessionLocal
from app.models import HeroStat
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HeroStatItem,
    ScraperResponse,
    HealthResponse
)
from app.services.chatbot import get_chat_response, invalidate_stats_cache
from app.services.stratz import run_scraper_task
from app.services.errors import ServiceError
from app.services.rate_limit import consume_chat_budget
from app.middleware import ChatBodyLimitMiddleware

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Dota 2 Tracker API",
    description="Dota 2 web chat and analytics API powered by Google Gemini, hybrid knowledge retrieval, and STRATZ statistics.",
    version="2.0.0"
)

# CORS middleware for cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ChatBodyLimitMiddleware)


@app.exception_handler(ServiceError)
async def service_error_handler(request, error: ServiceError):
    headers = {"Retry-After": "60"} if error.status_code == 429 else None
    return JSONResponse({"detail": str(error)}, status_code=error.status_code, headers=headers)


@app.exception_handler(Exception)
async def unexpected_error_handler(request, error: Exception):
    logger.error("Request failed (%s)", type(error).__name__)
    return JSONResponse({"detail": "Service temporarily unavailable."}, status_code=503)


@app.get("/", response_class=HTMLResponse, tags=["Frontend"])
def home():
    """Serves the interactive Dota 2 AI Assistant web interface."""
    html_path = os.path.join(root_dir, "app", "templates", "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(
        content="""
        <html>
            <body style='background:#111;color:#eee;font-family:sans-serif;padding:2rem;'>
                <h1>AI Dota 2 Tracker API</h1>
                <p>Backend is online. Visit <a style='color:#e63946;' href='/docs'>/docs</a> for the API Swagger UI.</p>
            </body>
        </html>
        """
    )


@app.get("/api/info", tags=["General"])
def api_info():
    """JSON metadata about available API endpoints."""
    return {
        "name": "AI Dota 2 Tracker API",
        "version": "2.0.0",
        "status": "online",
        "docs_url": "/docs",
        "endpoints": {
            "web_ui": "GET /",
            "chat": "POST /chat",
            "top_heroes": "GET /heroes/top",
            "health": "GET /health",
            "cron": "GET /api/cron",
            "manual_scraper": "POST /scraper/run"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
def health_check():
    """Health check endpoint that tests connectivity to Supabase without crashing."""
    db_status = "connected"
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
    except Exception as error:
        logger.warning("Database health check failed (%s)", type(error).__name__)
        db_status = "unavailable"

    result = HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        version="2.0.0"
    )
    return JSONResponse(result.model_dump(), status_code=200 if db_status == "connected" else 503)


@app.post("/chat", response_model=ChatResponse, tags=["Chatbot"])
async def chat(request: ChatRequest):
    """
    Ask any Dota 2 question or statistical query.
    Powered by Google Gemini with retrieved game knowledge and stored STRATZ statistics.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        await asyncio.to_thread(consume_chat_budget)
        reply = await get_chat_response(request.message)
        return ChatResponse(reply=reply)
    except ServiceError:
        raise
    except Exception as error:
        logger.warning("Chat failed (%s)", type(error).__name__)
        raise HTTPException(status_code=500, detail="Unable to answer right now. Please try again.") from None


@app.get("/heroes/top", response_model=List[HeroStatItem], tags=["Stats"])
def get_top_heroes(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """
    Get top win rate heroes for the most recent recorded date.
    Fast direct SQL query without calling the AI agent.
    """
    latest_date_subquery = db.query(func.max(func.date(HeroStat.recorded_at))).scalar_subquery()

    top_stats = (
        db.query(HeroStat)
        .filter(func.date(HeroStat.recorded_at) == latest_date_subquery)
        .order_by(HeroStat.win_rate.desc())
        .limit(limit)
        .all()
    )
    return top_stats


def verify_auth(authorization: Optional[str] = None):
    """Maintenance is disabled without a secret; accept bearer headers only."""
    configured = settings.CRON_SECRET
    if not configured or not configured.strip():
        raise HTTPException(status_code=503, detail="Maintenance endpoints are not configured.")
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not secrets.compare_digest(
        token.strip().encode("utf-8"), configured.encode("utf-8")
    ):
        raise HTTPException(
            status_code=401,
            detail="A valid bearer token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/api/cron", response_model=ScraperResponse, tags=["Scraper"])
async def cron_scraper(
    authorization: Optional[str] = Header(None, description="Bearer <CRON_SECRET>")
):
    """
    Daily cron endpoint intended for Vercel Cron.
    Requires a configured CRON_SECRET and its matching bearer token.
    """
    verify_auth(authorization=authorization)

    try:
        updated_count = await asyncio.to_thread(run_scraper_task)
        invalidate_stats_cache()
        return ScraperResponse(
            status="success",
            message=f"Scraper completed successfully. Synced {updated_count} heroes.",
            updated_count=updated_count
        )
    except Exception as error:
        logger.warning("Statistics sync failed (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Statistics sync failed. Please try again later.") from None


@app.post("/scraper/run", response_model=ScraperResponse, tags=["Scraper"])
async def manual_scraper(
    authorization: Optional[str] = Header(None, description="Bearer <CRON_SECRET>")
):
    """
    Manually trigger data scraper to update hero stats from STRATZ API.
    Can be executed directly from Swagger UI (/docs).
    """
    verify_auth(authorization=authorization)

    try:
        updated_count = await asyncio.to_thread(run_scraper_task)
        invalidate_stats_cache()
        return ScraperResponse(
            status="success",
            message=f"Scraper completed successfully. Synced {updated_count} heroes.",
            updated_count=updated_count
        )
    except Exception as error:
        logger.warning("Statistics sync failed (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Statistics sync failed. Please try again later.") from None


@app.post("/scraper/sync-meta", response_model=ScraperResponse, tags=["Scraper"])
async def sync_opendota_meta(
    authorization: Optional[str] = Header(None, description="Bearer <CRON_SECRET>")
):
    """
    Trigger full Bulk Dota 2 Knowledge Ingestion (All Heroes, Abilities, Facets, Talents, Items, Builds).
    Can be executed directly from Swagger UI (/docs).
    """
    verify_auth(authorization=authorization)

    try:
        from scripts.bulk_ingest_all_dota_knowledge import bulk_ingest_into_supabase
        synced_count = await asyncio.to_thread(bulk_ingest_into_supabase)
        return ScraperResponse(
            status="success",
            message="Successfully ingested full Dota 2 encyclopedia (heroes, abilities, items, builds) into pgvector.",
            updated_count=synced_count or 0
        )
    except Exception as error:
        logger.warning("Knowledge sync failed (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Knowledge sync failed. Check server configuration and retry.") from None
