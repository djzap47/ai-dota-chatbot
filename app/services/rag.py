import time
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
    response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text_content,
        config={"output_dimensionality": 768}
    )
    vec = response.embeddings[0].values
    if len(_embedding_cache) < 256:
        _embedding_cache[clean_text] = vec
    return vec


# Known pro aliases to assist hybrid search
PRO_ALIASES = {
    "yatoro": "Yatoro",
    "raddan": "Yatoro",
    "ame": "Ame",
    "watson": "Watson",
    "skiter": "skiter",
    "nightfall": "Nightfall",
    "saika": "Nightfall",
    "pure": "Pure",
    "micke": "miCKe",
    "33": "33",
    "malr1ne": "Malr1ne",
    "bzm": "bzm",
    "collapse": "Collapse"
}

def search_dota_knowledge(query: str, limit: int = 4, threshold: float = 0.45) -> List[Dict[str, Any]]:
    """
    Hybrid search: Combines pgvector cosine similarity with direct entity matching
    for pro player names and hero meta guides.
    """
    results: List[Dict[str, Any]] = []
    seen_titles = set()

    try:
        db = SessionLocal()
        try:
            # 1. Hybrid Entity Match: Check if query contains a known pro player
            lower_q = query.lower()
            detected_pro = None
            for alias, canon in PRO_ALIASES.items():
                if re.search(r'\b' + re.escape(alias) + r'\b', lower_q):
                    detected_pro = canon
                    break

            if detected_pro:
                pro_sql = text("""
                    SELECT hero_name, section_title, content, 1.0 AS similarity
                    FROM hero_documents
                    WHERE hero_name ILIKE :pro_pattern OR section_title ILIKE :pro_pattern
                    ORDER BY updated_at DESC
                    LIMIT 2;
                """)
                pro_rows = db.execute(pro_sql, {"pro_pattern": f"%{detected_pro}%"}).mappings().all()
                for row in pro_rows:
                    if row["section_title"] not in seen_titles:
                        results.append(dict(row))
                        seen_titles.add(row["section_title"])

            # 2. Vector Cosine Similarity Search
            query_vector = generate_embedding(query)
            vector_str = "[" + ",".join(map(str, query_vector)) + "]"
            
            vec_sql = text("""
                SELECT hero_name, section_title, content,
                       1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
                FROM hero_documents
                WHERE 1 - (embedding <=> CAST(:query_vec AS vector)) > :threshold
                ORDER BY similarity DESC
                LIMIT :limit;
            """)
            vec_rows = db.execute(vec_sql, {
                "query_vec": vector_str,
                "threshold": threshold,
                "limit": limit
            }).mappings().all()

            for row in vec_rows:
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
