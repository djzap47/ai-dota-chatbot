"""One configured vector space for ingestion and queries."""

import math
import time
from functools import lru_cache
from google import genai
from app.config import settings


@lru_cache(maxsize=1)
def _client_for(api_key, timeout):
    return genai.Client(api_key=api_key, http_options={
        "timeout": timeout * 1000,
        "retry_options": {"attempts": 1},
    })


def get_genai_client():
    if not settings.GOOGLE_API_KEY:
        raise ValueError("GOOGLE_API_KEY is not configured.")
    return _client_for(settings.GOOGLE_API_KEY, settings.UPSTREAM_TIMEOUT_SECONDS)


def validate_embedding(values):
    if len(values) != 768 or not all(math.isfinite(float(value)) for value in values):
        raise ValueError("Expected a finite 768-dimensional embedding.")
    return [float(value) for value in values]


@lru_cache(maxsize=256)
def _embed(model, content):
    response = get_genai_client().models.embed_content(
        model=model, contents=content, config={"output_dimensionality": 768}
    )
    return tuple(validate_embedding(response.embeddings[0].values))


def generate_embedding(text_content):
    # Preserve case: normalization must not change the embedded input.
    return list(_embed(settings.EMBEDDING_MODEL, text_content.strip()))


def embed_batch_with_retry(batch, max_retries=3):
    embeddings = []
    for content in batch:
        for attempt in range(max(1, min(max_retries, 3))):
            try:
                embeddings.append(generate_embedding(content))
                break
            except Exception:
                if attempt + 1 >= max(1, min(max_retries, 3)):
                    raise
                time.sleep(2 ** attempt)
    return embeddings
