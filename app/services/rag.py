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


def generate_embedding(text_content: str) -> List[float]:
    """Generate a 768-dimension embedding vector for a given text."""
    client = get_genai_client()
    response = client.models.embed_content(
        model="models/gemini-embedding-001",
        contents=text_content,
        config={"output_dimensionality": 768}
    )
    return response.embeddings[0].values


def search_liquipedia_knowledge(query: str, limit: int = 3, threshold: float = 0.50) -> List[Dict[str, Any]]:
    """
    Search Supabase vector database for relevant Liquipedia wiki documentation.
    Executes in ~50ms using HNSW cosine index.
    """
    try:
        query_vector = generate_embedding(query)
        vector_str = "[" + ",".join(map(str, query_vector)) + "]"
        
        db = SessionLocal()
        try:
            sql = text("""
                SELECT hero_name, section_title, content,
                       1 - (embedding <=> CAST(:query_vec AS vector)) AS similarity
                FROM hero_documents
                WHERE 1 - (embedding <=> CAST(:query_vec AS vector)) > :threshold
                ORDER BY similarity DESC
                LIMIT :limit;
            """)
            result = db.execute(sql, {
                "query_vec": vector_str,
                "threshold": threshold,
                "limit": limit
            })
            rows = result.mappings().all()
            return [dict(row) for row in rows]
        finally:
            db.close()
    except Exception as e:
        print(f"Warning: RAG vector search error: {e}")
        return []
