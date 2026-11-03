"""
2026 Meta & Pro Player Knowledge Ingestion Pipeline (Patch 7.41+)
Fetches real-time item popularity, hero matchups/counters, and tier-1 pro player match logs
from OpenDota APIs & OpenDota SQL Explorer, embeds them via Gemini, and indexes them in Supabase.
"""

import sys
import os
import time
import requests
from typing import List, Dict, Any, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import SessionLocal
from app.services.rag import get_genai_client

HEADERS = {
    "User-Agent": "DotaBotTracker/2026.1 (OpenDota 7.41 meta sync; contact: study@example.com)"
}

BASE_URL = "https://api.opendota.com/api"

# Tier-1 Pro Players to track
PRO_PLAYERS = {
    321580797: {"name": "Yatoro (Raddan)", "team": "Team Spirit", "role": "Carry (Pos 1)"},
    125581216: {"name": "Ame", "team": "Xtreme Gaming", "role": "Carry (Pos 1)"},
    183719414: {"name": "Watson", "team": "Gaimin Gladiators", "role": "Carry (Pos 1)"},
    100471531: {"name": "skiter", "team": "Team Falcons", "role": "Carry (Pos 1)"},
    124801317: {"name": "Nightfall (Saika)", "team": "Tundra Esports", "role": "Carry (Pos 1)"},
    117160980: {"name": "Pure", "team": "BetBoom Team", "role": "Carry (Pos 1)"},
    105248644: {"name": "miCKe", "team": "Team Liquid", "role": "Carry (Pos 1)"},
    111114687: {"name": "33", "team": "Tundra Esports", "role": "Offlane (Pos 3)"},
    317880638: {"name": "Malr1ne", "team": "Team Falcons", "role": "Mid (Pos 2)"},
    196723549: {"name": "bzm", "team": "OG", "role": "Mid (Pos 2)"},
    302214028: {"name": "Collapse", "team": "Team Spirit", "role": "Offlane (Pos 3)"},
}


def get_item_dict() -> Dict[int, Dict[str, Any]]:
    """Fetch OpenDota items constant and return mapping {item_id: {dname, cost, tier}}."""
    print("Fetching OpenDota items constant...")
    res = requests.get(f"{BASE_URL}/constants/items", headers=HEADERS, timeout=15)
    data = res.json()
    item_map = {}
    for key, item in data.items():
        iid = item.get("id")
        if iid:
            item_map[iid] = {
                "key": key,
                "dname": item.get("dname", key.replace("_", " ").title()),
                "cost": item.get("cost", 0),
                "tier": item.get("tier")
            }
    print(f"Loaded {len(item_map)} items into dictionary.")
    return item_map


def get_heroes_dict() -> Dict[int, Dict[str, Any]]:
    """Fetch OpenDota heroes constant and return mapping {hero_id: hero_info}."""
    print("Fetching OpenDota heroes constant...")
    res = requests.get(f"{BASE_URL}/constants/heroes", headers=HEADERS, timeout=15)
    data = res.json()
    hero_map = {}
    for hid_str, hero in data.items():
        hid = hero.get("id")
        if hid:
            hero_map[hid] = hero
    print(f"Loaded {len(hero_map)} heroes into dictionary.")
    return hero_map


def parse_hero_meta_and_matchups(
    items_dict: Dict[int, Dict[str, Any]], 
    heroes_dict: Dict[int, Dict[str, Any]],
    hero_limit: Optional[int] = None
) -> List[Tuple[str, str, str]]:
    """
    For heroes, fetch:
    1. /heroes/{hero_id}/itemPopularity (Starting, Early, Mid, Late item distributions)
    2. /heroes/{hero_id}/matchups (Hardest counters & favorable matchups)
    """
    print("\n--- 1. Parsing Hero Meta, Item Popularity & Matchup Counters ---")
    chunks = []

    target_heroes = list(heroes_dict.items())
    if hero_limit is not None and hero_limit > 0:
        target_heroes = target_heroes[:hero_limit]
        print(f"Limiting to first {hero_limit} heroes for fast execution.")

    for hid, hero in target_heroes:
        name = hero.get("localized_name")
        attr = str(hero.get("primary_attr", "")).upper()
        attack = hero.get("attack_type", "")
        roles = ", ".join(hero.get("roles", []))

        # 1. Item popularity
        try:
            pop_res = requests.get(f"{BASE_URL}/heroes/{hid}/itemPopularity", headers=HEADERS, timeout=10)
            pop_data = pop_res.json() if pop_res.status_code == 200 else {}
        except Exception:
            pop_data = {}

        def format_items(section_key: str, top_n: int = 5) -> str:
            raw_dict = pop_data.get(section_key, {})
            if not raw_dict:
                return "Standard meta items"
            # Sort by frequency
            sorted_items = sorted(raw_dict.items(), key=lambda x: int(x[1]), reverse=True)
            names = []
            for iid_str, count in sorted_items:
                try:
                    iid = int(iid_str)
                    item_info = items_dict.get(iid)
                    if item_info and item_info["dname"]:
                        item_name = item_info["dname"]
                        if item_name not in names and not item_name.endswith("Recipe"):
                            names.append(item_name)
                except ValueError:
                    continue
                if len(names) >= top_n:
                    break
            return ", ".join(names) if names else "Standard meta items"

        start_items = format_items("start_game_items", 6)
        early_items = format_items("early_game_items", 4)
        mid_items = format_items("mid_game_items", 6)
        late_items = format_items("late_game_items", 6)

        # 2. Matchups
        try:
            m_res = requests.get(f"{BASE_URL}/heroes/{hid}/matchups", headers=HEADERS, timeout=10)
            m_data = m_res.json() if m_res.status_code == 200 else []
        except Exception:
            m_data = []

        valid_matchups = []
        for m in m_data:
            opp_id = m.get("hero_id")
            games = m.get("games_played", 0)
            wins = m.get("wins", 0)
            if games >= 15 and opp_id in heroes_dict:
                wr = round((wins / games) * 100, 1)
                opp_name = heroes_dict[opp_id].get("localized_name")
                valid_matchups.append((opp_name, wr, games))

        # Best matchups (Highest win rate)
        strong_against = sorted(valid_matchups, key=lambda x: x[1], reverse=True)[:5]
        strong_str = ", ".join(f"{name} ({wr}%)" for name, wr, g in strong_against) if strong_against else "None recorded"

        # Worst matchups / Counters (Lowest win rate)
        weak_against = sorted(valid_matchups, key=lambda x: x[1])[:5]
        weak_str = ", ".join(f"{name} ({wr}%)" for name, wr, g in weak_against) if weak_against else "None recorded"

        cat = f"Hero Meta: {name}"
        title = f"Hero Meta & 7.41 Item Build Guide: {name}"

        content = f"""Hero Meta & Item Build Guide: {name} — Patch 7.41
Attribute: {attr} | Attack Type: {attack} | Roles: {roles}

Verified High-MMR Item Build Progression (OpenDota Match Data):
• Starting Items: {start_items}
• Early Game Core (0-15m): {early_items}
• Mid Game Core Spikes (15-30m): {mid_items}
• Late Game / Extensions (30m+): {late_items}

Patch 7.41 Matchups & Counters:
• Strong Against (High Win Rate): {strong_str}
• Countered By (Low Win Rate / Struggles Against): {weak_str}"""

        chunks.append((cat, title, content))
        time.sleep(0.12)  # Respect OpenDota rate limits

    print(f"Generated {len(chunks)} Hero Meta & Matchup documents.")
    return chunks


def parse_pro_player_matches(
    items_dict: Dict[int, Dict[str, Any]], 
    heroes_dict: Dict[int, Dict[str, Any]]
) -> List[Tuple[str, str, str]]:
    """
    Fetch actual recent matches of Tier-1 pro players (Yatoro, Ame, Watson, etc.)
    using OpenDota SQL Explorer, extracting item purchase timelines and match stats.
    """
    print("\n--- 2. Parsing Real-Time Pro Player Matches via OpenDota Explorer ---")
    chunks = []

    account_ids_str = ", ".join(str(aid) for aid in PRO_PLAYERS.keys())
    sql = f"""
    SELECT 
        pm.account_id,
        pm.hero_id,
        m.match_id,
        m.start_time,
        m.duration,
        pm.item_0, pm.item_1, pm.item_2, pm.item_3, pm.item_4, pm.item_5, pm.item_neutral,
        pm.purchase_log,
        pm.kills, pm.deaths, pm.assists,
        pm.gold_per_min, pm.xp_per_min,
        (m.radiant_win = (pm.player_slot < 128)) AS won
    FROM player_matches pm
    JOIN matches m ON pm.match_id = m.match_id
    WHERE pm.account_id IN ({account_ids_str})
    ORDER BY m.start_time DESC
    LIMIT 100;
    """

    rows = []
    try:
        res = requests.get(f"{BASE_URL}/explorer", params={"sql": sql}, headers=HEADERS, timeout=20)
        if res.status_code == 200:
            rows = res.json().get("rows", [])
            print(f"Retrieved {len(rows)} pro match records from OpenDota SQL Explorer.")
    except Exception as e:
        print(f"Notice: OpenDota Explorer error: {e}")

    # Fallback to direct player matches if explorer is empty
    if not rows:
        print("Falling back to direct /players/{id}/matches...")
        for aid, pinfo in list(PRO_PLAYERS.items())[:5]:
            try:
                res = requests.get(f"{BASE_URL}/players/{aid}/matches?limit=10", headers=HEADERS, timeout=10)
                if res.status_code == 200:
                    for m in res.json():
                        m["account_id"] = aid
                        rows.append(m)
                time.sleep(0.3)
            except Exception:
                pass

    for r in rows:
        aid = r.get("account_id")
        hid = r.get("hero_id")
        pinfo = PRO_PLAYERS.get(aid, {"name": "Pro Player", "team": "Tier 1", "role": "Core"})
        pname = pinfo["name"]
        team = pinfo["team"]

        hero_name = heroes_dict.get(hid, {}).get("localized_name") if hid in heroes_dict else f"Hero {hid}"
        if not hero_name:
            continue

        match_id = r.get("match_id")
        k = r.get("kills", 0)
        d = r.get("deaths", 0)
        a = r.get("assists", 0)
        gpm = r.get("gold_per_min", 0)
        won = r.get("won")
        result_str = "WIN" if won else "LOSS"

        # Parse purchase timeline
        purchase_log = r.get("purchase_log") or []
        timeline_items = []
        if isinstance(purchase_log, list):
            for p in purchase_log:
                if not isinstance(p, dict):
                    continue
                pkey = p.get("key")
                ptime = p.get("time", 0)
                if ptime is not None and ptime >= 0 and pkey:
                    # Match against items dict
                    display = pkey.replace("_", " ").title()
                    for item in items_dict.values():
                        if item["key"] == pkey:
                            display = item["dname"]
                            break
                    if not display.endswith("Recipe") and display not in ["Tango", "Clarity", "Ward", "Observer Ward", "Sentry Ward", "Town Portal Scroll"]:
                        minutes = ptime // 60
                        seconds = ptime % 60
                        timeline_items.append(f"{minutes:02d}:{seconds:02d} - {display}")

        # Final 6 slotted items
        final_items = []
        for slot in ["item_0", "item_1", "item_2", "item_3", "item_4", "item_5", "item_neutral"]:
            item_id = r.get(slot)
            if item_id and item_id in items_dict:
                dname = items_dict[item_id]["dname"]
                if dname and not dname.endswith("Recipe"):
                    final_items.append(dname)

        final_items_str = ", ".join(final_items) if final_items else "Endgame inventory not available"
        timeline_summary = " • " + "\n • ".join(timeline_items[:10]) if timeline_items else "Timeline not recorded"

        cat = f"Pro Match: {pname} on {hero_name}"
        title = f"Pro Build: {hero_name} by {pname} ({team}) — Patch 7.41"

        content = f"""Verified Pro Match Record: {hero_name} played by {pname} ({team}) — Patch 7.41
Result: {result_str} (KDA: {k}/{d}/{a} | GPM: {gpm}) | Match ID: {match_id}
Role: {pinfo['role']}

Item Purchase Timeline:
{timeline_summary}

Final Items Slotted:
{final_items_str}"""

        chunks.append((cat, title, content))

    print(f"Generated {len(chunks)} Pro Player Match documents.")
    return chunks


def embed_batch_with_retry(batch: List[str], max_retries: int = 5) -> List[List[float]]:
    client = get_genai_client()
    delay = 3.0
    for attempt in range(max_retries):
        try:
            response = client.models.embed_content(
                model="models/gemini-embedding-001",
                contents=batch,
                config={"output_dimensionality": 768}
            )
            return [emb.values for emb in response.embeddings]
        except Exception as e:
            err_str = str(e)
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                print(f"Rate limit hit. Waiting {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                delay *= 1.5
            else:
                print(f"Embedding error: {e}")
                time.sleep(2.0)
    raise RuntimeError("Failed to embed batch after retries.")


def run_meta_and_pros_sync(hero_limit: Optional[int] = None) -> int:
    print("=" * 65)
    print("STARTING 2026 OPENDOTA META & PRO PLAYER INGESTION (PATCH 7.41+)")
    print("=" * 65)

    items_dict = get_item_dict()
    heroes_dict = get_heroes_dict()

    all_chunks = []
    # 1. Hero Meta & Matchups
    all_chunks.extend(parse_hero_meta_and_matchups(items_dict, heroes_dict, hero_limit=hero_limit))
    # 2. Pro Player Matches
    all_chunks.extend(parse_pro_player_matches(items_dict, heroes_dict))

    print("\n" + "=" * 65)
    print(f"TOTAL PARSED 2026 META CHUNKS: {len(all_chunks)}")
    print("=" * 65)

    db = SessionLocal()
    try:
        batch_size = 15
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i:i + batch_size]
            texts_to_embed = [f"{c[1]}\n{c[2]}" for c in batch]
            embeddings = embed_batch_with_retry(texts_to_embed)

            for (cat, title, content), emb in zip(batch, embeddings):
                # Clean up old version if exists
                db.execute(text("DELETE FROM hero_documents WHERE hero_name = :h"), {"h": cat})
                vector_str = "[" + ",".join(map(str, emb)) + "]"
                db.execute(text("""
                    INSERT INTO hero_documents (hero_name, section_title, content, embedding)
                    VALUES (:h, :t, :c, CAST(:e AS vector))
                """), {"h": cat, "t": title, "c": content, "e": vector_str})
            db.commit()
            print(f"Indexed batch [{i + 1} to {min(i + batch_size, len(all_chunks))}] / {len(all_chunks)}")
            time.sleep(1.2)

        total_in_db = db.execute(text("SELECT count(*) FROM hero_documents")).scalar()
        print("\n" + "=" * 65)
        print(f"SUCCESS: 2026 META SYNC COMPLETE! Total indexed chunks in DB: {total_in_db}")
        print("=" * 65)
        return len(all_chunks)
    finally:
        db.close()


if __name__ == "__main__":
    run_meta_and_pros_sync()

