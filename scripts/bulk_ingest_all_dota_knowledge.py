"""
Bulk Dota 2 Knowledge Ingestion Pipeline.
Loads complete authoritative game data (heroes, abilities, facets, talents, aghs, items, builds, matchups)
from precomputed local datasets in app/data/ and bulk-embeds them directly into Supabase pgvector.
Zero one-by-one hero scraping, zero rate-limits.
"""

import os
import sys
import json
import time
from typing import List, Dict, Any, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import SessionLocal
from scripts.sync_opendota_meta_and_pros import embed_batch_with_retry

DATA_DIR = "app/data"

def load_json(filename: str) -> Any:
    path = os.path.join(DATA_DIR, filename)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def build_all_knowledge_chunks() -> List[Tuple[str, str, str]]:
    heroes = load_json("heroes.json")
    items = load_json("items.json")
    abilities = load_json("abilities.json")
    hero_abilities = load_json("hero_abilities.json")
    aghs = load_json("aghs_desc.json")
    hero_builds = load_json("hero_builds.json")
    hero_matchups = load_json("hero_matchups.json")

    chunks = []

    # 1. HERO COMPREHENSIVE GUIDE & ABILITY KITS
    print(f"Building chunks for {len(heroes)} heroes...")
    for hid_str, hero in heroes.items():
        hid = hero.get("id")
        hname = hero.get("localized_name")
        attr = str(hero.get("primary_attr", "")).upper()
        attack = hero.get("attack_type", "")
        roles = ", ".join(hero.get("roles", []))

        hero_key = hero.get("name") # e.g. npc_dota_hero_life_stealer
        h_abs = hero_abilities.get(hero_key, {})
        h_aghs = next((x for x in aghs if x.get("hero_id") == hid), {})

        # Abilities
        ability_lines = []
        raw_abilities = h_abs.get("abilities", [])
        flat_abilities = []
        for item in raw_abilities:
            if isinstance(item, list):
                flat_abilities.extend([str(x) for x in item if x])
            elif isinstance(item, str):
                flat_abilities.append(item)

        for ab_key in flat_abilities:
            if ab_key and not str(ab_key).startswith("generic_"):
                ab_data = abilities.get(ab_key, {})
                dname = ab_data.get("dname", ab_key.replace("_", " ").title())
                desc = ab_data.get("desc", "")
                bkb = ab_data.get("bkbpierce", "No")
                disp = ab_data.get("dispellable", "")
                cd = ab_data.get("cd", "")
                mc = ab_data.get("mc", "")
                info = []
                if cd: info.append(f"CD: {cd}s")
                if mc: info.append(f"Mana: {mc}")
                if bkb: info.append(f"BKB Pierce: {bkb}")
                if disp: info.append(f"Dispel: {disp}")
                meta_tag = f" [{', '.join(info)}]" if info else ""
                ability_lines.append(f"• {dname}{meta_tag}: {desc}")

        # Talents
        talents = []
        for t in h_abs.get("talents", []):
            t_key = t.get("name")
            t_data = abilities.get(t_key, {})
            dname = t_data.get("dname", t_key.replace("special_bonus_", "").replace("_", " ").title())
            lvl = t.get("level", 1) * 5 + 5
            talents.append(f"Lvl {lvl}: {dname}")

        # Aghanim's Scepter & Shard
        scep = h_aghs.get("scepter_desc", "No Scepter upgrade recorded.")
        shard = h_aghs.get("shard_desc", "No Shard upgrade recorded.")

        # Document 1: Full Hero Ability & Mechanics Guide
        cat_kit = hname
        title_kit = f"{hname} - Abilities & Mechanics Guide"
        content_kit = f"""Hero Kit & Mechanics Guide: {hname}
Primary Attribute: {attr} | Attack Type: {attack} | Roles: {roles}

ABILITIES & SKILLS:
{chr(10).join(ability_lines)}

AGHANIM'S SCEPTER & SHARD UPGRADES:
• Aghanim's Scepter: {scep}
• Aghanim's Shard: {shard}

TALENT TREE:
{', '.join(talents) if talents else 'Standard Talents'}"""

        chunks.append((cat_kit, title_kit, content_kit))

        # Document 2: Item Build Progression & Counters
        b_data = hero_builds.get(hid_str, {})
        build_list = b_data.get("builds", [])
        m = hero_matchups.get(hid_str, {})

        build_blocks = []
        for idx, build in enumerate(build_list, 1):
            b_name = build.get("name", f"Build {idx}")
            s_items = build.get("starting", "Quelling Blade, Tango, Iron Branch, Magic Stick")
            e_items = build.get("early", "Phase Boots, Magic Wand")
            m_items = build.get("mid", "Black King Bar, Manta Style")
            l_items = build.get("late", "Eye of Skadi, Butterfly, Refresher Orb")
            
            build_blocks.append(f"""Build {idx} ({b_name}):
• Starting Items: {s_items}
• Early Game: {e_items}
• Mid Game Core: {m_items}
• Late Game: {l_items}""")

        build_text = "\n\n".join(build_blocks)
        strong_str = ", ".join(m.get("strong_against", [])) if m.get("strong_against") else "High win-rate against favorable heroes"
        weak_str = ", ".join(m.get("counters", [])) if m.get("counters") else "Struggles against heavy control/disables"

        cat_meta = hname
        title_meta = f"{hname} - High-MMR Item Build & Matchups"
        content_meta = f"""Hero Meta & Item Build Guide: {hname}
Attribute: {attr} | Attack Type: {attack} | Roles: {roles}

High-MMR Item Build Progression:
{build_text}

Matchups & Counters:
• Strong Against (High Win Rate): {strong_str}
• Countered By (Low Win Rate / Struggles Against): {weak_str}"""

        chunks.append((cat_meta, title_meta, content_meta))

    # 2. MAJOR DOTA 2 ITEM CATALOG (Completed & Major Items)
    print(f"Building chunks for major completed items...")
    for ikey, item in items.items():
        cost = item.get("cost") or 0
        dname = item.get("dname", "")
        if not dname or dname.endswith("Recipe") or ikey.startswith("recipe_"):
            continue
        # Only major items: cost >= 1400 or created or neutral item
        tier = item.get("tier")
        created = item.get("created", False)
        if cost < 1400 and not created and tier is None:
            continue

        comps = item.get("components") or []
        comp_names = [items.get(c, {}).get("dname", c.replace("_", " ").title()) for c in comps if c and not c.startswith("recipe_")]

        desc = item.get("notes", "") or item.get("hint", "") or ""
        attribs = item.get("attrib", [])
        attr_str = ", ".join([f"{a.get('header', '')} {a.get('value', '')} {a.get('footer', '')}".strip() for a in attribs if isinstance(a, dict)])

        cat_item = dname
        title_item = f"Item Guide & Recipe: {dname} ({cost} Gold)" if cost else f"Neutral Item Guide: {dname} (Tier {tier})"
        content_item = f"""Item Guide: {dname}
Cost: {cost} Gold {'(Tier ' + str(tier) + ' Neutral Item)' if tier else ''}
Components: {', '.join(comp_names) if comp_names else 'Bought directly from shop'}
Bonus Stats: {attr_str if attr_str else 'Special unique properties'}
Description / Effects: {desc if desc else 'Core tactical item.'}"""

        chunks.append((cat_item, title_item, content_item))

    print(f"Total compiled rich Dota 2 knowledge chunks: {len(chunks)}")
    return chunks

def bulk_ingest_into_supabase(batch_size: int = 15):
    chunks = build_all_knowledge_chunks()
    print(f"Starting bulk ingestion of {len(chunks)} knowledge chunks into Supabase pgvector...")

    db = SessionLocal()
    try:
        # Wipe old stale/broken/facet chunks first to guarantee a pure, clean state
        print("Purging old knowledge documents from Supabase...")
        db.execute(text("TRUNCATE TABLE hero_documents;"))
        db.commit()
        print("Cleaned hero_documents table. Embedding and inserting fresh chunks...")

        total = len(chunks)
        for i in range(0, total, batch_size):
            batch = chunks[i:i + batch_size]
            texts_to_embed = [f"{c[1]}\n{c[2]}" for c in batch]
            embeddings = embed_batch_with_retry(texts_to_embed)

            for (cat, title, content), emb in zip(batch, embeddings):
                vector_str = "[" + ",".join(map(str, emb)) + "]"
                db.execute(text("""
                    INSERT INTO hero_documents (hero_name, section_title, content, embedding)
                    VALUES (:h, :t, :c, CAST(:e AS vector))
                """), {"h": cat, "t": title, "c": content, "e": vector_str})
            db.commit()
            print(f"Indexed [{i + 1} to {min(i + batch_size, total)}] / {total} chunks into Supabase.")
            time.sleep(1.0)

        total_db = db.execute(text("SELECT count(*) FROM hero_documents")).scalar()
        print(f"\nBULK INGESTION COMPLETE! Total documents in Supabase: {total_db}")
        return total_db
    finally:
        db.close()

if __name__ == "__main__":
    bulk_ingest_into_supabase()

