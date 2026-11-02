from sqlalchemy import Column, Integer, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base

class Hero(Base):
    __tablename__ = "heroes"

    id = Column(Integer, primary_key=True)
    name = Column(Text, nullable=False)
    roles = Column(Text, nullable=True)  # Comma-separated roles, e.g. "CARRY, ESCAPE, PUSHER"

    stats = relationship("HeroStat", back_populates="hero", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Hero {self.id}: {self.name} ({self.roles})>"


class HeroStat(Base):
    __tablename__ = "hero_stats"

    id = Column(Integer, primary_key=True, index=True)
    hero_id = Column(Integer, ForeignKey("heroes.id", ondelete="CASCADE"), nullable=False, unique=True)
    hero_name = Column(Text, nullable=True)
    win_rate = Column(Float, nullable=True)
    match_count = Column(Integer, nullable=True)
    win_count = Column(Integer, nullable=True)
    recorded_at = Column(DateTime(timezone=True), server_default=func.now())

    hero = relationship("Hero", back_populates="stats")

    def __repr__(self):
        return f"<HeroStat {self.hero_name} - {self.win_rate}% ({self.recorded_at})>"
