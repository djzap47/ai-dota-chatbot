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
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text, func

from app.config import settings
from app.database import get_db
from app.models import HeroStat
from app.schemas import (
    ChatRequest,
    ChatResponse,
    HeroStatItem,
    ScraperResponse,
    HealthResponse
)
from app.services.chatbot import get_chat_response
from app.services.stratz import run_scraper_task, sync_hero_stats

app = FastAPI(
    title="AI Dota 2 Tracker API",
    description="FastAPI backend for Dota 2 analytics and AI chatbot powered by Gemini 2.5 Flash and STRATZ.",
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


@app.get("/", tags=["General"])
def root():
    return {
        "name": "AI Dota 2 Tracker API",
        "version": "2.0.0",
        "status": "online",
        "docs_url": "/docs",
        "endpoints": {
            "chat": "POST /chat",
            "top_heroes": "GET /heroes/top",
            "health": "GET /health",
            "cron": "GET /api/cron",
            "manual_scraper": "POST /scraper/run"
        }
    }


@app.get("/health", response_model=HealthResponse, tags=["General"])
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "connected"
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


@app.get("/api/cron", response_model=ScraperResponse, tags=["Scraper"])
async def cron_scraper(authorization: Optional[str] = Header(None)):
    """
    Daily cron endpoint intended for Vercel Cron.
    Secured by comparing Authorization header against CRON_SECRET if configured.
    """
    if settings.CRON_SECRET:
        expected = f"Bearer {settings.CRON_SECRET}"
        if authorization != expected:
            raise HTTPException(status_code=401, detail="Unauthorized cron request.")

    try:
        updated_count = await asyncio.to_thread(run_scraper_task)
        return ScraperResponse(
            status="success",
            message=f"Scraper completed successfully. Synced {updated_count} heroes.",
            updated_count=updated_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")


@app.post("/scraper/run", response_model=ScraperResponse, tags=["Scraper"])
async def manual_scraper(db: Session = Depends(get_db)):
    """
    Manually trigger data scraper to update hero stats from STRATZ API.
    """
    try:
        updated_count = await asyncio.to_thread(sync_hero_stats, db)
        return ScraperResponse(
            status="success",
            message=f"Scraper completed successfully. Synced {updated_count} heroes.",
            updated_count=updated_count
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Scraper failed: {str(e)}")
