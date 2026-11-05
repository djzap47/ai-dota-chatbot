from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class ChatRequest(BaseModel):
    message: str = Field(max_length=2000)

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

    model_config = ConfigDict(from_attributes=True)

class ScraperResponse(BaseModel):
    status: str
    message: str
    updated_count: int

class HealthResponse(BaseModel):
    status: str
    database: str
    version: str
