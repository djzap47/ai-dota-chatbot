import time
import re
from functools import lru_cache
from typing import List, Dict, Any, Optional
from google import genai
from sqlalchemy import text
from app.config import settings
from app.database import SessionLocal

_client = None

def get_genai_client():
    global _client
    if _client is None:
        if not settings.GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY is not set.")
        _client = genai.Client(api_key=settings.GOOGLE_API_KEY)
    return _client


# Simple in-memory LRU cache for query embeddings (saves 200-400ms per repeated question)
_embedding_cache: Dict[str, List[float]] = {}

def generate_embedding(text_content: str) -> List[float]:
    """Generate a 768-dimension embedding vector for a given text, with in-memory caching."""
    clean_text = text_content.strip().lower()
    if clean_text in _embedding_cache:
        return _embedding_cache[clean_text]

    client = get_genai_client()
    for model_name in ["gemini-embedding-2-preview", "gemini-embedding-2", "gemini-embedding-001"]:
        try:
            response = client.models.embed_content(
                model=model_name,
                contents=text_content,
                config={"output_dimensionality": 768}
            )
            vec = response.embeddings[0].values
            if len(_embedding_cache) < 256:
                _embedding_cache[clean_text] = vec
            return vec
        except Exception:
            continue
    raise RuntimeError("Failed to generate embedding with available models.")


def search_dota_knowledge(query: str, limit: int = 4, threshold: float = 0.45) -> List[Dict[str, Any]]:
    """
    Hybrid search: Combines pgvector cosine similarity with dynamic keyword matching
    for pro player names and hero meta guides. Zero hardcoded player names.
    """
    results: List[Dict[str, Any]] = []
    seen_titles = set()

    try:
        db = SessionLocal()
        try:
            # 1. Dynamic Entity Match: Extract meaningful keywords (player names, heroes) from user query
            stop_words = {
                "what", "should", "build", "builds", "item", "items", "best", "play", "guide",
                "hero", "heroes", "dota", "patch", "current", "when", "with", "does", "from",
                "game", "like", "order", "meta", "timing", "timings", "tell", "about",
                "buy", "buying", "get", "getting", "purchase", "purchases", "suggest",
                "give", "for", "the", "you", "can", "how", "make", "take", "taking", "show"
            }
            words = [
                w.strip().lower() for w in re.findall(r'[a-zA-Z0-9_\-]+', query)
                if len(w.strip()) >= 3 and w.strip().lower() not in stop_words
            ]

            for word in words:
                pattern = f"%{word}%"
                pattern_nospaces = f"%{word.replace(' ', '')}%"
                match_sql = text("""
                    SELECT hero_name, section_title, content, 1.0 AS similarity
                    FROM hero_documents
                    WHERE hero_name ILIKE :pattern 
                       OR section_title ILIKE :pattern
                       OR REPLACE(LOWER(hero_name), ' ', '') ILIKE :pattern_nospaces
                    ORDER BY updated_at DESC
                    LIMIT 3;
                """)
                rows = db.execute(match_sql, {
                    "pattern": pattern,
                    "pattern_nospaces": pattern_nospaces
                }).mappings().all()
                for row in rows:
                    if row["section_title"] not in seen_titles:
                        results.append(dict(row))
                        seen_titles.add(row["section_title"])
                if len(results) >= 3:
                    break

            # 2. Vector Cosine Similarity Search (with graceful fallback if embedding quota reached)
            try:
                query_vector = generate_embedding(query)
                vector_str = "[" + ",".join(map(str, query_vector)) + "]"
                
                vec_sql = text("""
                    SELECT hero_name, section_title, content,
                           1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
                    FROM hero_documents
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> CAST(:query_vec AS vector) ASC
                    LIMIT :limit;
                """)
                vec_rows = db.execute(vec_sql, {
                    "query_vec": vector_str,
                    "limit": limit
                }).mappings().all()

                for row in vec_rows:
                    if row["section_title"] not in seen_titles and len(results) < limit:
                        results.append(dict(row))
                        seen_titles.add(row["section_title"])
            except Exception as vec_err:
                # Quota exceeded or embedding error fallback: search by content & section title
                fallback_sql = text("""
                    SELECT hero_name, section_title, content, 0.85 AS similarity
                    FROM hero_documents
                    WHERE section_title ILIKE :pat OR content ILIKE :pat
                    ORDER BY updated_at DESC
                    LIMIT :limit;
                """)
                for word in words:
                    if len(results) >= limit:
                        break
                    fb_rows = db.execute(fallback_sql, {
                        "pat": f"%{word}%",
                        "limit": limit
                    }).mappings().all()
                    for row in fb_rows:
                        if row["section_title"] not in seen_titles and len(results) < limit:
                            results.append(dict(row))
                            seen_titles.add(row["section_title"])

            return results
        finally:
            db.close()
    except Exception as e:
        print(f"Warning: RAG knowledge search error: {e}")
        return results


def search_liquipedia_knowledge(query: str, limit: int = 3, threshold: float = 0.50) -> List[Dict[str, Any]]:
    """Backward-compatible alias pointing to improved hybrid search."""
    return search_dota_knowledge(query, limit=limit, threshold=threshold)
