import sys
import os
import re
import time
import requests
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import SessionLocal
from app.models import Hero
from app.services.embeddings import embed_batch_with_retry
from app.services.knowledge_store import replace_documents

LIQUIPEDIA_API_URL = "https://liquipedia.net/dota2/api.php"
HEADERS = {
    "User-Agent": "DotaAITracker/1.0 (https://github.com/djzap47/ai-dota-chatbot; contact: studyproject@example.com)",
    "Accept-Encoding": "gzip"
}

def clean_html(raw_html: str) -> str:
    """Clean raw MediaWiki rendered HTML into clean, human-readable text."""
    # Replace headers and breaks with newlines
    cleaned = re.sub(r'</?(?:h[1-6]|p|div|tr|li|br)[^>]*>', '\n', raw_html, flags=re.IGNORECASE)
    # Remove all remaining HTML tags
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    # Clean up whitespace and wiki artifacts
    cleaned = re.sub(r'\[\s*edit\s*\]', '', cleaned, flags=re.IGNORECASE)
    lines = [line.strip() for line in cleaned.split('\n') if line.strip()]
    return '\n'.join(lines)


def fetch_hero_liquipedia_chunks(hero_name: str) -> List[Dict[str, str]]:
    """
    Fetch and chunk key sections from a hero's Liquipedia page:
    - Upgrades (Aghanim's Scepter & Shard)
    - Innate & Abilities
    """
    chunks = []

    # 1. Fetch sections list
    params = {
        "action": "parse",
        "page": hero_name,
        "prop": "sections",
        "format": "json"
    }

    try:
        res = requests.get(LIQUIPEDIA_API_URL, headers=HEADERS, params=params, timeout=12)
        if res.status_code != 200:
            print(f"Failed to fetch sections for {hero_name}: {res.status_code}")
            return []

        sections = res.json().get("parse", {}).get("sections", [])
    except Exception as e:
        print(f"Error fetching sections for {hero_name}: {e}")
        return []

    # Identify target sections
    target_sections = []
    for s in sections:
        line = s.get("line", "").lower()
        idx = s.get("index")
        if "upgrades" in line or "aghanim" in line:
            target_sections.append((idx, f"{hero_name} - Aghanim's Scepter & Shard Upgrades"))
        elif "innate" in line or "facets" in line:
            target_sections.append((idx, f"{hero_name} - Innate & Facets"))
        elif "abilities" in line:
            target_sections.append((idx, f"{hero_name} - Abilities"))

    # 2. Fetch content for each target section
    for idx, title in target_sections:
        try:
            sec_params = {
                "action": "parse",
                "page": hero_name,
                "section": idx,
                "prop": "text",
                "format": "json"
            }
            sec_res = requests.get(LIQUIPEDIA_API_URL, headers=HEADERS, params=sec_params, timeout=12)
            if sec_res.status_code != 200:
                continue

            raw_html = sec_res.json().get("parse", {}).get("text", {}).get("*", "")
            cleaned_text = clean_html(raw_html)

            if len(cleaned_text) > 40:
                # Truncate if excessively long to keep chunk compact
                chunks.append({
                    "title": title,
                    "content": cleaned_text[:1200]
                })
            time.sleep(0.5)  # Be polite to Liquipedia rate limits
        except Exception as e:
            print(f"Error parsing section {title}: {e}")

    return chunks


def ingest_heroes(hero_names: List[str]):
    """Ingest Liquipedia documentation chunks with embeddings into Supabase."""
    for name in hero_names:
        print(f"\nProcessing {name} from Liquipedia...")
        chunks = fetch_hero_liquipedia_chunks(name)

        if not chunks:
            print(f"No chunks found for {name}.")
            continue

        with SessionLocal() as db:
            hero = db.query(Hero).filter(Hero.name.ilike(name)).first()
            hero_id = hero.id if hero else None
        documents = [(name, c["title"], c["content"]) for c in chunks]
        embeddings = embed_batch_with_retry([f"{c[1]}\n{c[2]}" for c in documents])
        replace_documents(documents, embeddings=embeddings, hero_ids={name: hero_id})
        print(f"Done ingesting {len(chunks)} chunks for {name}.")



if __name__ == "__main__":
    # Test with prominent heroes first
    test_heroes = ["Anti-Mage", "Clinkz", "Pudge", "Spectre", "Juggernaut"]
    ingest_heroes(test_heroes)
