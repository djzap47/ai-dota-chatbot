"""A deployment-wide budget backed by an atomic PostgreSQL upsert."""

from sqlalchemy import text
from app.config import settings
from app.database import SessionLocal
from app.services.errors import ServiceError


def consume_chat_budget():
    try:
        with SessionLocal() as db:
            accepted = db.execute(text("""
                INSERT INTO chat_request_limits (name, window_start, request_count)
                VALUES ('chat', statement_timestamp(), 1)
                ON CONFLICT (name) DO UPDATE SET
                    window_start = CASE
                        WHEN chat_request_limits.window_start <= statement_timestamp() - INTERVAL '1 minute'
                        THEN statement_timestamp() ELSE chat_request_limits.window_start END,
                    request_count = CASE
                        WHEN chat_request_limits.window_start <= statement_timestamp() - INTERVAL '1 minute'
                        THEN 1 ELSE chat_request_limits.request_count + 1 END
                WHERE chat_request_limits.window_start <= statement_timestamp() - INTERVAL '1 minute'
                   OR chat_request_limits.request_count < :budget
                RETURNING request_count
            """), {"budget": settings.CHAT_REQUESTS_PER_MINUTE}).scalar()
            db.commit()
    except Exception:
        # Do not fall back to an unbounded paid endpoint when storage is unavailable.
        raise ServiceError("Chat is temporarily unavailable. Please try again later.") from None
    if accepted is None:
        raise ServiceError("Chat request limit reached. Please try again in a minute.", 429)
