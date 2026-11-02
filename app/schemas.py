from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str
    status: str = "success"

class HeroStatItem(BaseModel):
    hero_id: int
    hero_name: Optional[str] = None
    win_rate: Optional[float] = None
    match_count: Optional[int] = None
    win_count: Optional[int] = None
    recorded_at: Optional[datetime] = None

    class Config:
        from_attributes = True

class ScraperResponse(BaseModel):
    status: str
    message: str
    updated_count: int

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
