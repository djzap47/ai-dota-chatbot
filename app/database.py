from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool
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
        
        # NullPool is the official Supabase recommendation for serverless + port 6543
        # Disable prepared statements for psycopg 3 to prevent DuplicatePreparedStatement
        # errors ("prepared statement _pg3_0 already exists") in Supabase transaction pooler mode
        connect_args = {}
        try:
            import psycopg  # psycopg v3
            connect_args["prepare_threshold"] = None
        except ImportError:
            pass

        _engine = create_engine(
            db_url,
            poolclass=NullPool,
            connect_args=connect_args
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
