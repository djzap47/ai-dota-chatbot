import os
import sys

# Ensure Vercel serverless function can find the 'app' module in the root directory
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

import asyncio
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Header, Query
from fastapi.responses import HTMLResponse
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

app = FastAPI(
    title="AI Dota 2 Tracker API",
    description="FastAPI backend and Web UI for Dota 2 analytics and AI chatbot powered by Gemini 2.5 Flash and STRATZ.",
    version="2.0.0"
)

# CORS middleware for cross-origin access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
    except Exception as e:
        db_status = f"error: {str(e)}"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        database=db_status,
        version="2.0.0"
    )


@app.post("/chat", response_model=ChatResponse, tags=["Chatbot"])
async def chat(request: ChatRequest):
    """
    Ask any Dota 2 question or statistical query.
    Powered by Google Gemini 2.5 Flash and LangChain SQL Agent.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")
        
    try:
        reply = await get_chat_response(request.message)
        return ChatResponse(reply=reply)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI Agent error: {str(e)}")


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


def verify_auth(authorization: Optional[str] = None, secret: Optional[str] = None):
    """Verify authorization header or secret query parameter against CRON_SECRET."""
    if not settings.CRON_SECRET:
        return
    token = (secret or authorization or "").strip()
    if token.startswith("Bearer "):
        token = token[7:].strip()
    if token != settings.CRON_SECRET:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized. Enter your CRON_SECRET in the 'secret' parameter or Authorization header."
        )


@app.get("/api/cron", response_model=ScraperResponse, tags=["Scraper"])
async def cron_scraper(
    secret: Optional[str] = Query(None, description="CRON_SECRET query parameter"),
    authorization: Optional[str] = Header(None, description="CRON_SECRET or Bearer token")
):
    """
    Daily cron endpoint intended for Vercel Cron.
    Secured by comparing Authorization header or secret query against CRON_SECRET if configured.
    """
    verify_auth(authorization=authorization, secret=secret)

    try:
        updated_count = await asyncio.to_thread(run_scraper_task)
        invalidate_stats_cache()
        return ScraperResponse(
            status="success",
            message=f"Scraper completed successfully. Synced {updated_count} heroes.",
            updated_count=updated_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")


@app.post("/scraper/run", response_model=ScraperResponse, tags=["Scraper"])
async def manual_scraper(
    secret: Optional[str] = Query(None, description="Enter CRON_SECRET here (works reliably in Swagger)"),
    authorization: Optional[str] = Header(None, description="CRON_SECRET or Bearer token")
):
    """
    Manually trigger data scraper to update hero stats from STRATZ API.
    Can be executed directly from Swagger UI (/docs).
    """
    verify_auth(authorization=authorization, secret=secret)

    try:
        updated_count = await asyncio.to_thread(run_scraper_task)
        invalidate_stats_cache()
        return ScraperResponse(
            status="success",
            message=f"Scraper completed successfully. Synced {updated_count} heroes.",
            updated_count=updated_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")


@app.post("/scraper/sync-meta", response_model=ScraperResponse, tags=["Scraper"])
async def sync_opendota_meta(
    secret: Optional[str] = Query(None, description="Enter CRON_SECRET here (works reliably in Swagger)"),
    authorization: Optional[str] = Header(None, description="CRON_SECRET or Bearer token")
):
    """
    Trigger full Bulk Dota 2 Knowledge Ingestion (All Heroes, Abilities, Facets, Talents, Items, Builds).
    Can be executed directly from Swagger UI (/docs).
    """
    verify_auth(authorization=authorization, secret=secret)

    try:
        from scripts.bulk_ingest_all_dota_knowledge import bulk_ingest_into_supabase
        synced_count = await asyncio.to_thread(bulk_ingest_into_supabase)
        return ScraperResponse(
            status="success",
            message="Successfully ingested full Dota 2 encyclopedia (heroes, abilities, items, builds) into pgvector.",
            updated_count=synced_count or 0
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Meta sync failed: {str(e)}")
