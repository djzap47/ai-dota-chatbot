import sys
import os
import re
import time
import requests
from typing import List, Dict, Any

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import SessionLocal
from app.models import Hero
from app.services.rag import generate_embedding

VALVE_HERODATA_URL = "https://www.dota2.com/datafeed/herodata?language=english"
VALVE_HEROLIST_URL = "https://www.dota2.com/datafeed/herolist?language=english"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json"
}

def clean_text(raw_text: str) -> str:
    """Clean game variables and HTML artifacts from Valve text."""
    if not raw_text:
        return ""
    cleaned = re.sub(r'%[a-zA-Z0-9_]+%', '', raw_text)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def parse_hero_data_into_chunks(hero_data: dict) -> List[Dict[str, str]]:
    """Parse Valve herodata JSON into clean RAG document chunks."""
    hero_name = hero_data.get("name_loc", "Unknown Hero")
    chunks = []
    
    # Chunk 1: Aghanim's Scepter & Shard Upgrades
    scepter_shard_lines = [f"{hero_name} - Official Aghanim's Scepter & Shard Upgrades:"]
    for ab in hero_data.get("abilities", []):
        ab_name = ab.get("name_loc", "")
        scepter = clean_text(ab.get("scepter_loc", ""))
        shard = clean_text(ab.get("shard_loc", ""))
        
        if scepter:
            scepter_shard_lines.append(f"• {ab_name} (Aghanim's Scepter Upgrade): {scepter}")
        if shard:
            scepter_shard_lines.append(f"• {ab_name} (Aghanim's Shard Upgrade): {shard}")
            
    if len(scepter_shard_lines) > 1:
        chunks.append({
            "title": f"{hero_name} - Aghanim's Scepter & Shard",
            "content": "\n".join(scepter_shard_lines)
        })
        
    # Chunk 2: Core Abilities & Innate
    ability_lines = [f"{hero_name} - Abilities & Innates:"]
    for ab in hero_data.get("abilities", []):
        ab_name = ab.get("name_loc", "")
        desc = clean_text(ab.get("desc_loc", ""))
        if desc:
            ability_lines.append(f"• {ab_name}: {desc}")
            
    if len(ability_lines) > 1:
        chunks.append({
            "title": f"{hero_name} - Abilities Overview",
            "content": "\n".join(ability_lines[:6])
        })
        
    return chunks


def ingest_all_heroes():
    print("=" * 65)
    print("Fetching full hero list from official Valve Dota 2 feed...")
    print("=" * 65)
    
    res = requests.get(VALVE_HEROLIST_URL, headers=HEADERS, timeout=15)
    if res.status_code != 200:
        raise Exception(f"Failed to fetch hero list: {res.status_code}")
        
    hero_list = res.json()["result"]["data"]["heroes"]
    print(f"Discovered {len(hero_list)} Dota 2 heroes from official feed.")
    
    db = SessionLocal()
    try:
        total_ingested = 0
        for i, h in enumerate(hero_list, 1):
            h_id = h["id"]
            h_name = h.get("name_loc", f"Hero {h_id}")
            
            # Fetch detailed hero data
            url = f"{VALVE_HERODATA_URL}&hero_id={h_id}"
            h_res = requests.get(url, headers=HEADERS, timeout=15)
            if h_res.status_code != 200:
                print(f"Skipping hero {h_name} ({h_res.status_code})")
                continue
                
            heroes_data = h_res.json().get("result", {}).get("data", {}).get("heroes", [])
            if not heroes_data:
                continue
                
            hero_data = heroes_data[0]
            chunks = parse_hero_data_into_chunks(hero_data)
            
            # Delete existing documents for this hero to avoid duplicates
            db.execute(text("DELETE FROM hero_documents WHERE hero_name = :name"), {"name": h_name})
            db.commit()
            
            for chunk in chunks:
                title = chunk["title"]
                content = chunk["content"]
                
                try:
                    embedding = generate_embedding(f"{title}\n{content}")
                    vector_str = "[" + ",".join(map(str, embedding)) + "]"
                    
                    db.execute(text("""
                        INSERT INTO hero_documents (hero_id, hero_name, section_title, content, embedding)
                        VALUES (:hero_id, :hero_name, :title, :content, CAST(:embedding AS vector))
                    """), {
                        "hero_id": h_id,
                        "hero_name": h_name,
                        "title": title,
                        "content": content,
                        "embedding": vector_str
                    })
                    db.commit()
                    total_ingested += 1
                except Exception as e:
                    print(f"  Embedding error for {title}: {e}")
                    
            print(f"[{i}/{len(hero_list)}] Ingested {len(chunks)} chunks for {h_name}")
            time.sleep(0.1)
            
        print("\n" + "=" * 65)
        print(f"SUCCESS: Ingested {total_ingested} official RAG documents into Supabase!")
        print("=" * 65)
    finally:
        db.close()


if __name__ == "__main__":
    ingest_all_heroes()
