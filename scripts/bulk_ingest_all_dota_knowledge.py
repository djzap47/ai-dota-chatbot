"""
Compile bundled Dota 2 datasets into searchable knowledge documents.
Atomically replace the text index, then generate embeddings within provider quota.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Any, Tuple

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import SessionLocal
from app.services.embeddings import embed_batch_with_retry
from app.services.knowledge_store import replace_documents
from app.config import settings

DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"

def load_json(filename: str) -> Any:
    with (DATA_DIR / filename).open(encoding="utf-8") as source:
        value = json.load(source)
    expected = list if filename in {"aghs_desc.json", "game_mechanics.json"} else dict
    if not isinstance(value, expected) or not value:
        raise ValueError(f"Missing or invalid dataset: {filename}")
    return value

def describe_item(item):
    def stringify(value):
        return " / ".join(map(str, value)) if isinstance(value, list) else str(value or "")
    effects = [stringify(item.get(key)) for key in ("notes", "hint", "desc") if item.get(key)]
    for ability in item.get("abilities", []):
        effects.append(f"{ability.get('type', '').title()}: {ability.get('title', '')}: {stringify(ability.get('description'))}")
    stats = []
    for attribute in item.get("attrib", []):
        value = stringify(attribute.get("value"))
        label = attribute.get("display") or attribute.get("key", "Stat").replace("_", " ").title()
        stats.append(label.replace("{value}", value) if "{value}" in label else f"{label}: {value}")
    return "\n".join(effects), ", ".join(stats)

def build_all_knowledge_chunks() -> List[Tuple[str, str, str]]:
    heroes = load_json("heroes.json")
    items = load_json("items.json")
    abilities = load_json("abilities.json")
    hero_abilities = load_json("hero_abilities.json")
    aghs = load_json("aghs_desc.json")
    hero_builds = load_json("hero_builds.json")
    hero_matchups = load_json("hero_matchups.json")

    for hero_id in heroes:
        builds = hero_builds.get(hero_id, {}).get("builds")
        if not isinstance(builds, list) or not builds or any(
            not isinstance(build.get(phase), str) or not build[phase].strip()
            for build in builds for phase in ("starting", "early", "mid", "late")
        ):
            raise ValueError(f"Invalid build data for hero {hero_id}")
        if hero_id not in hero_matchups:
            raise ValueError(f"Missing matchup data for hero {hero_id}")
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
        if len(build_list) == 1:
            b = build_list[0]
            build_blocks.append(f"""• Starting Items: {b.get('starting')}
• Early Game: {b.get('early')}
• Mid Game: {b.get('mid')}
• Late Game: {b.get('late')}""")
        else:
            for idx, build in enumerate(build_list, 1):
                b_name = build.get("name", f"Option {idx}")
                build_blocks.append(f"""Build {idx} ({b_name}):
• Starting Items: {build.get('starting')}
• Early Game: {build.get('early')}
• Mid Game: {build.get('mid')}
• Late Game: {build.get('late')}""")

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

        desc, attr_str = describe_item(item)

        cat_item = dname
        title_item = f"Item Guide & Recipe: {dname} ({cost} Gold)" if cost else f"Neutral Item Guide: {dname} (Tier {tier})"
        content_item = f"""Item Guide: {dname}
Cost: {cost} Gold {'(Tier ' + str(tier) + ' Neutral Item)' if tier else ''}
Components: {', '.join(comp_names) if comp_names else 'Bought directly from shop'}
Bonus Stats: {attr_str if attr_str else 'Special unique properties'}
Description / Effects: {desc if desc else 'Core tactical item.'}"""

        chunks.append((cat_item, title_item, content_item))

    # 3. DOTA 2 GENERAL GAME MECHANICS, LANING, AND ROLE TAXONOMY
    game_mechanics = load_json("game_mechanics.json")
    if isinstance(game_mechanics, list):
        print(f"Building chunks for {len(game_mechanics)} Dota 2 game mechanics & fundamentals...")
        for gm in game_mechanics:
            cat = gm.get("category", "Game Mechanics")
            title = gm.get("title", "Dota 2 Mechanics")
            content = gm.get("content", "")
            chunks.append((cat, title, content))

    print(f"Total compiled rich Dota 2 knowledge chunks: {len(chunks)}")
    return chunks

def bulk_ingest_into_supabase(batch_size: int = 15):
    if not 1 <= batch_size <= 100:
        raise ValueError("batch_size must be between 1 and 100")
    chunks = build_all_knowledge_chunks()
    # Validate first, then replace in a single transaction. Readers keep the old snapshot.
    ids = replace_documents(chunks, replace_all=True)
    for start in range(0, len(chunks), batch_size):
        batch = chunks[start:start + batch_size]
        try:
            embeddings = embed_batch_with_retry([f"{c[1]}\n{c[2]}" for c in batch], max_retries=1)
            with SessionLocal() as db, db.begin():
                for document_id, embedding in zip(ids[start:start + batch_size], embeddings):
                    # IDs prevent a concurrent replacement receiving vectors for older text.
                    db.execute(text("""
                        UPDATE hero_documents SET embedding = CAST(:embedding AS vector), embedding_model = :model
                        WHERE id = :id
                    """), {"id": document_id, "embedding": str(embedding), "model": settings.EMBEDDING_MODEL})
        except Exception as error:
            print(f"Vectorization unavailable ({type(error).__name__}); text search remains available.")
            break
    print(f"Loaded {len(chunks)} knowledge documents.")
    return len(chunks)

if __name__ == "__main__":
    bulk_ingest_into_supabase()
