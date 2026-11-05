import logging
import re
from sqlalchemy import text
from app.config import settings
from app.database import SessionLocal
from app.services.embeddings import generate_embedding, get_genai_client

logger = logging.getLogger(__name__)
STOP_WORDS = {
    "what", "should", "build", "builds", "item", "items", "best", "play", "guide",
    "hero", "heroes", "dota", "patch", "current", "when", "with", "does", "from",
    "game", "like", "order", "meta", "timing", "timings", "tell", "about", "buy",
    "buying", "get", "getting", "purchase", "purchases", "suggest", "give", "for",
    "the", "you", "can", "how", "make", "take", "taking", "show",
}


def extract_keywords(query):
    words = re.findall(r"[a-zA-Z0-9-]{3,}", query[:2000].lower())
    return list(dict.fromkeys(word for word in words if word not in STOP_WORDS))[:8]


def search_dota_knowledge(query, limit=4, threshold=0.45):
    """At most three bounded SELECTs, with matching-model semantic retrieval."""
    limit = max(0, min(limit, 20))
    if not limit:
        return []
    results = []
    seen = set()
    patterns = [f"%{word}%" for word in extract_keywords(query)]

    def append_rows(rows, minimum=None):
        for row in rows:
            if len(results) >= limit:
                break
            if minimum is not None and row["similarity"] < minimum:
                continue
            key = (row["hero_name"], row["section_title"])
            if key not in seen:
                results.append(dict(row))
                seen.add(key)

    try:
        with SessionLocal() as db:
            if patterns:
                rows = db.execute(text("""
                    SELECT hero_name, section_title, content, 1.0 AS similarity
                    FROM hero_documents
                    WHERE hero_name ILIKE ANY(CAST(:patterns AS text[]))
                       OR section_title ILIKE ANY(CAST(:patterns AS text[]))
                    ORDER BY updated_at DESC, section_title
                    LIMIT :limit
                """), {"patterns": patterns, "limit": limit}).mappings().all()
                append_rows(rows)
                # Release the read connection before a provider request.
                db.rollback()
            if len(results) >= limit:
                return results
            try:
                vector = generate_embedding(query[:2000])
                rows = db.execute(text("""
                    SELECT hero_name, section_title, content,
                           1 - (embedding <=> CAST(:vector AS vector)) AS similarity
                    FROM hero_documents
                    WHERE embedding IS NOT NULL AND embedding_model = :model
                      AND 1 - (embedding <=> CAST(:vector AS vector)) >= :threshold
                    ORDER BY embedding <=> CAST(:vector AS vector), section_title
                    LIMIT :limit
                """), {"vector": str(vector), "model": settings.EMBEDDING_MODEL,
                       "threshold": threshold, "limit": limit}).mappings().all()
                append_rows(rows, threshold)
            except Exception as error:
                # PostgreSQL rejects further statements in a failed transaction.
                db.rollback()
                logger.warning("Vector retrieval unavailable (%s)", type(error).__name__)
                if patterns:
                    rows = db.execute(text("""
                        SELECT hero_name, section_title, content, 0.85 AS similarity
                        FROM hero_documents
                        WHERE section_title ILIKE ANY(CAST(:patterns AS text[]))
                           OR content ILIKE ANY(CAST(:patterns AS text[]))
                        ORDER BY updated_at DESC, section_title
                        LIMIT :limit
                    """), {"patterns": patterns, "limit": limit}).mappings().all()
                    append_rows(rows)
    except Exception as error:
        logger.warning("Knowledge retrieval unavailable (%s)", type(error).__name__)
    return results


def search_liquipedia_knowledge(query, limit=3, threshold=0.50):
    return search_dota_knowledge(query, limit=limit, threshold=threshold)
