from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator
from app.config import settings

Base = declarative_base()

_engine = None
_SessionLocal = None

def get_engine():
    global _engine, _SessionLocal
    if _engine is None:
        db_url = settings.sqlalchemy_db_url
        if not db_url:
            raise ValueError("SUPABASE_DB_URL is not set in environment variables.")
        _engine = create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=300
        )
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    return _engine

def SessionLocal() -> Session:
    get_engine()
    return _SessionLocal()

def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency for obtaining a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
