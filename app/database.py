from sqlalchemy import create_engine, event
from sqlalchemy.engine import make_url
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.pool import NullPool
from typing import Generator
from threading import Lock
from app.config import settings

Base = declarative_base()

_engine = None
_SessionLocal = None
_init_lock = Lock()

def get_engine():
    global _engine, _SessionLocal
    with _init_lock:
        if _engine is not None:
            return _engine
        db_url = settings.sqlalchemy_db_url
        if not db_url:
            raise ValueError("SUPABASE_DB_URL is not set in environment variables.")
        
        # NullPool is the official Supabase recommendation for serverless + port 6543
        # Disable prepared statements for psycopg 3 to prevent DuplicatePreparedStatement
        # errors ("prepared statement _pg3_0 already exists") in Supabase transaction pooler mode
        connect_args = {"connect_timeout": 5}
        if make_url(db_url).get_dialect().driver == "psycopg":
            connect_args["prepare_threshold"] = None

        engine = create_engine(
            db_url,
            poolclass=NullPool,
            connect_args=connect_args
        )
        # Transaction-local settings also work through transaction poolers.
        @event.listens_for(engine, "begin")
        def set_timeouts(connection):
            connection.exec_driver_sql("SET LOCAL statement_timeout = '10s'")
            connection.exec_driver_sql("SET LOCAL lock_timeout = '5s'")

        try:
            factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        except Exception:
            engine.dispose()
            raise
        _SessionLocal = factory
        _engine = engine
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
