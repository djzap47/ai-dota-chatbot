"""Validated, atomic knowledge replacement shared by maintenance scripts."""

from sqlalchemy import text
from app.config import settings
from app.database import SessionLocal
from app.services.embeddings import validate_embedding


def replace_documents(chunks, *, replace_all=False, embeddings=None, hero_ids=None):
    chunks = list(chunks)
    if not chunks or any(len(c) != 3 or any(not isinstance(v, str) or not v.strip() for v in c) for c in chunks):
        raise ValueError("Knowledge documents must be nonempty strings.")
    if len({(c[0], c[1]) for c in chunks}) != len(chunks):
        raise ValueError("Duplicate knowledge document titles.")
    if embeddings is not None:
        if len(embeddings) != len(chunks):
            raise ValueError("Embedding count does not match documents.")
        embeddings = [validate_embedding(e) for e in embeddings]
    with SessionLocal() as db, db.begin():
        # All writers share this transaction lock; competing refreshes fail safely.
        if not db.execute(text("SELECT pg_try_advisory_xact_lock(71402501)")).scalar():
            raise RuntimeError("Another knowledge refresh is running.")
        if replace_all:
            db.execute(text("DELETE FROM hero_documents"))
        else:
            db.execute(text("DELETE FROM hero_documents WHERE hero_name = ANY(CAST(:names AS text[]))"),
                       {"names": sorted({c[0] for c in chunks})})
        ids = []
        for i, (category, title, content) in enumerate(chunks):
            ids.append(db.execute(text("""
                INSERT INTO hero_documents (hero_id, hero_name, section_title, content, embedding, embedding_model)
                VALUES (:hero_id, :category, :title, :content, CAST(:embedding AS vector), :model)
                RETURNING id
            """), {"category": category, "title": title, "content": content,
                   "hero_id": (hero_ids or {}).get(category),
                   "embedding": str(embeddings[i]) if embeddings is not None else None,
                   "model": settings.EMBEDDING_MODEL if embeddings is not None else None}).scalar_one())
        return ids
