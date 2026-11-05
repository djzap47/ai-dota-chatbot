import sys
import os
import re
import time
import requests
from typing import List, Dict, Any, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.embeddings import embed_batch_with_retry
from app.services.knowledge_store import replace_documents


HEADERS = {
    "User-Agent": "DotaBotTracker/2.0 (OpenDota automated sync; contact: study@example.com)"
}

BASE_URL = "https://api.opendota.com/api"


def clean_text(raw: Any) -> str:
    if not raw:
        return ""
    if isinstance(raw, list):
        raw = " ".join(str(x) for x in raw)
    elif not isinstance(raw, str):
        raw = str(raw)
    cleaned = re.sub(r'%[a-zA-Z0-9_]+%', '', raw)
    cleaned = re.sub(r'</?(?:h[1-6]|p|div|br)[^>]*>', '\n', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


# =====================================================================
# 1. PARSE ITEMS FROM OPENDOTA
# =====================================================================
def parse_all_items() -> List[Tuple[str, str, str]]:
    print("1. Parsing all items from OpenDota constants...")
    res = requests.get(f"{BASE_URL}/constants/items", headers=HEADERS, timeout=15)
    items_dict = res.json()
    chunks = []

    for key, item in items_dict.items():
        name = item.get("dname")
        if not name or name.endswith("Recipe") or key.startswith("recipe_"):
            continue
        cost = item.get("cost")
        tier = item.get("tier")
        if cost is None and tier is None:
            continue
        if cost is not None and cost <= 0 and tier is None:
            continue

        is_neutral = tier is not None
        if is_neutral:
            title = f"Item: {name} (Tier {tier} Neutral Item)"
            cat = f"Neutral Item: {name}"
            header = f"Item: {name} (Tier {tier} Neutral Item)"
        else:
            title = f"Item: {name} ({cost} Gold)"
            cat = f"Item: {name}"
            header = f"Item: {name} (Total Cost: {cost} gold)"

        parts = [header]

        components = item.get("components")
        if components and isinstance(components, list):
            comp_names = [str(c).replace('_', ' ').title() for c in components if c]
            if comp_names:
                parts.append(f"Components / Recipe: {', '.join(comp_names)}")

        attribs = item.get("attrib", [])
        if isinstance(attribs, list):
            stat_lines = []
            for a in attribs:
                if not isinstance(a, dict):
                    continue
                display = a.get("display")
                val = a.get("value")
                if display and "{value}" in display:
                    stat_lines.append(display.replace("{value}", str(val)))
                elif display:
                    stat_lines.append(f"{display}: {val}")
            if stat_lines:
                parts.append("Stats: " + ", ".join(stat_lines))

        abilities = item.get("abilities", [])
        if isinstance(abilities, list):
            for ab in abilities:
                if not isinstance(ab, dict):
                    continue
                ab_type = str(ab.get("type", "")).capitalize()
                ab_title = str(ab.get("title", ""))
                ab_desc = clean_text(ab.get("description", ""))
                parts.append(f"{ab_type}: {ab_title}\n{ab_desc}")

        notes = clean_text(item.get("notes", ""))
        if notes:
            parts.append(f"Notes: {notes}")

        content = "\n\n".join(parts)
        chunks.append((cat, title, content[:1500]))

    print(f"Parsed {len(chunks)} items.")
    return chunks


# =====================================================================
# 2. PARSE HEROES, ABILITIES, SCEPTER & SHARD
# =====================================================================
def parse_all_heroes() -> List[Tuple[str, str, str]]:
    print("\n2. Parsing heroes, abilities, and Aghanim's Scepter/Shard upgrades...")
    heroes_res = requests.get(f"{BASE_URL}/constants/heroes", headers=HEADERS, timeout=15).json()
    abilities_res = requests.get(f"{BASE_URL}/constants/abilities", headers=HEADERS, timeout=15).json()
    hero_abilities_res = requests.get(f"{BASE_URL}/constants/hero_abilities", headers=HEADERS, timeout=15).json()
    aghs_res = requests.get(f"{BASE_URL}/constants/aghs_desc", headers=HEADERS, timeout=15).json()

    # Index aghs by hero_id
    aghs_by_id = {}
    for entry in aghs_res:
        hid = entry.get("hero_id")
        if hid:
            aghs_by_id[hid] = entry

    chunks = []
    for hid_str, hero in heroes_res.items():
        hid = hero.get("id")
        name = hero.get("localized_name")
        attr = hero.get("primary_attr", "").upper()
        attack = hero.get("attack_type", "")
        roles = ", ".join(hero.get("roles", []))

        hero_key = hero.get("name") # e.g. npc_dota_hero_antimage
        hab_data = hero_abilities_res.get(hero_key, {})
        ability_keys = hab_data.get("abilities", [])

        title = f"Hero: {name} - Abilities & Upgrades"
        cat = f"Hero: {name}"

        parts = [
            f"Hero: {name} ({attr} | {attack} | Roles: {roles})"
        ]

        # Abilities
        flat_ability_keys = []
        for ab in ability_keys:
            if isinstance(ab, list):
                flat_ability_keys.extend(ab)
            elif isinstance(ab, str):
                flat_ability_keys.append(ab)

        ab_lines = []
        for ab_key in flat_ability_keys:
            if ab_key == "generic_hidden":
                continue
            ab_info = abilities_res.get(ab_key, {})
            ab_dname = ab_info.get("dname", ab_key)
            ab_desc = clean_text(ab_info.get("desc", ""))
            mc = ab_info.get("mc", "")
            cd = ab_info.get("cd", "")
            ab_line = f"• {ab_dname}: {ab_desc}"
            if mc:
                ab_line += f" [Mana: {mc}]"
            if cd:
                ab_line += f" [CD: {cd}s]"
            ab_lines.append(ab_line)

        if ab_lines:
            parts.append("Abilities:\n" + "\n".join(ab_lines[:6]))

        # Aghanim's Scepter & Shard
        aghs_entry = aghs_by_id.get(hid, {})
        scepter = clean_text(aghs_entry.get("scepter_desc", ""))
        shard = clean_text(aghs_entry.get("shard_desc", ""))

        if scepter:
            parts.append(f"Aghanim's Scepter Upgrade: {scepter}")
        if shard:
            parts.append(f"Aghanim's Shard Upgrade: {shard}")

        # Facets
        facets = hab_data.get("facets", [])
        if facets and isinstance(facets, list):
            facet_lines = []
            for f in facets:
                if isinstance(f, dict):
                    ftitle = f.get("title", f.get("name", ""))
                    fdesc = clean_text(f.get("description", ""))
                    facet_lines.append(f"• {ftitle}: {fdesc}")
            if facet_lines:
                parts.append("Hero Facets:\n" + "\n".join(facet_lines))

        content = "\n\n".join(parts)
        chunks.append((cat, title, content[:1600]))

    print(f"Parsed {len(chunks)} heroes with full abilities, Scepter, and Shard.")
    return chunks


# =====================================================================
# 3. PARSE PRO TEAMS & ACTIVE ROSTERS
# =====================================================================
def parse_pro_teams() -> List[Tuple[str, str, str]]:
    print("\n3. Parsing Tier-1 Pro Teams and Active Rosters from OpenDota...")
    teams_res = requests.get(f"{BASE_URL}/teams", headers=HEADERS, timeout=15).json()

    # Take top 30 active teams by competitive rating
    top_teams = [t for t in teams_res if t.get("name") and (t.get("rating") or 0) > 1300][:30]
    chunks = []

    for t in top_teams:
        tid = t.get("team_id")
        name = t.get("name")
        tag = t.get("tag", "")
        rating = t.get("rating", 0)
        wins = t.get("wins", 0)
        losses = t.get("losses", 0)

        # Fetch active roster
        try:
            players_res = requests.get(f"{BASE_URL}/teams/{tid}/players", headers=HEADERS, timeout=10).json()
            active_players = [
                p.get("name") for p in players_res 
                if p.get("is_current_team_member") and p.get("name")
            ]
            if not active_players:
                # Top games played fallback
                active_players = [
                    p.get("name") for p in sorted(players_res, key=lambda x: x.get("games_played", 0), reverse=True)[:5] 
                    if p.get("name")
                ]
            time.sleep(0.15)
        except Exception:
            active_players = []

        cat = f"Esports Team: {name}"
        title = f"Team: {name} ({tag}) - Current Roster & Performance"

        roster_str = ", ".join(active_players[:6]) if active_players else "Roster currently shuffling"
        content = f"""Professional Dota 2 Team: {name} (Tag: {tag})
Rating: {rating:.1f} | All-Time Pro Record: {wins} Wins / {losses} Losses
Active Roster / Core Players: {roster_str}
Team ID: {tid} on OpenDota."""

        chunks.append((cat, title, content))

    print(f"Parsed {len(chunks)} pro teams and active rosters.")
    return chunks


# =====================================================================
# 4. PARSE RECENT PRO MATCHES & PREMIER LEAGUES
# =====================================================================
def parse_esports_tournaments() -> List[Tuple[str, str, str]]:
    print("\n4. Parsing recent pro tournaments and high-tier matches from OpenDota...")
    pro_matches = requests.get(f"{BASE_URL}/proMatches", headers=HEADERS, timeout=15).json()

    # Group matches by league
    matches_by_league = {}
    for m in pro_matches:
        league_name = m.get("league_name")
        if not league_name:
            continue
        if league_name not in matches_by_league:
            matches_by_league[league_name] = []
        matches_by_league[league_name].append(m)

    chunks = []
    # Take top 8 active leagues
    for league_name, matches in list(matches_by_league.items())[:8]:
        cat = f"Esports League: {league_name}"
        title = f"Tournament Results: {league_name}"

        match_summaries = []
        for m in matches[:6]:
            rad = m.get("radiant_name", "Radiant")
            dire = m.get("dire_name", "Dire")
            winner = rad if m.get("radiant_win") else dire
            r_score = m.get("radiant_score", 0)
            d_score = m.get("dire_score", 0)
            match_summaries.append(f"• {rad} vs {dire}: Winner {winner} ({r_score} - {d_score})")

        content = f"""Tournament: {league_name}
Recent Pro Match Results:
""" + "\n".join(match_summaries)

        chunks.append((cat, title, content))

    print(f"Parsed {len(chunks)} active pro tournament records.")
    return chunks


# =====================================================================
# 4b. PARSE THE INTERNATIONAL CHAMPIONS (OPENDOTA EXPLORER)
# =====================================================================
def parse_the_international_champions() -> List[Tuple[str, str, str]]:
    print("\n4b. Parsing The International Champions dynamically from OpenDota SQL Explorer...")
    try:
        sql = """
        SELECT l.name as tournament, 
               case when m.radiant_win then r.name else d.name end as winner,
               case when m.radiant_win then d.name else r.name end as runner_up,
               m.start_time
        FROM matches m
        JOIN leagues l ON m.leagueid = l.leagueid
        LEFT JOIN teams r ON m.radiant_team_id = r.team_id
        LEFT JOIN teams d ON m.dire_team_id = d.team_id
        WHERE l.tier = 'premium' AND l.name LIKE 'The International 20%'
        ORDER BY m.start_time DESC
        """
        res = requests.get(f"{BASE_URL}/explorer", params={"sql": sql}, headers=HEADERS, timeout=15)
        rows = res.json().get("rows", [])
        seen = {}
        for r in rows:
            t = r["tournament"]
            if t not in seen and "qualifier" not in t.lower():
                seen[t] = r

        if not seen:
            return []

        sorted_tournaments = sorted(seen.items(), key=lambda x: x[1]["start_time"], reverse=True)
        most_recent = sorted_tournaments[0]

        lines = [f"• {tourn}: Champion {r['winner']} (Runner-up: {r['runner_up']})" for tourn, r in sorted_tournaments]

        content = f"""The International (TI) Champions (Official Match Data from OpenDota):
The most recent edition of The International was {most_recent[1]['tournament']}, won by {most_recent[1]['winner']} (defeated {most_recent[1]['runner_up']} in the Grand Finals).

Historical The International Winners & Grand Finals:
""" + "\n".join(lines)

        cat = "Esports: The International All Champions"
        title = f"The International (TI) Champions - Latest: {most_recent[1]['tournament']} ({most_recent[1]['winner']})"
        return [(cat, title, content)]
    except Exception as e:
        print(f"Notice: Failed to query OpenDota Explorer for TI champions: {e}")
        return []


# =====================================================================
# 5. PARSE LATEST PATCH NOTES (OPENDOTA)
# =====================================================================
def parse_latest_patchnotes() -> List[Tuple[str, str, str]]:
    print("\n5. Parsing latest official patch notes from OpenDota...")
    patchnotes = requests.get(f"{BASE_URL}/constants/patchnotes", headers=HEADERS, timeout=15).json()
    recent_patch_keys = list(patchnotes.keys())[-5:] # Last 5 patches e.g. 7_40, 7_41
    chunks = []

    for pkey in recent_patch_keys:
        pdata = patchnotes[pkey]
        patch_name = pkey.replace('_', '.')
        cat = f"Patch: {patch_name}"
        title = f"Dota 2 Patch {patch_name} - Official Balance Notes & Changes"

        general = pdata.get("general", [])
        items_touched = list(pdata.get("items", {}).keys())
        heroes_touched = list(pdata.get("heroes", {}).keys())

        parts = [f"Dota 2 Gameplay Update: Patch {patch_name}"]
        if general:
            parts.append("General System Changes:\n" + "\n".join(f"• {g}" for g in general[:6]))
        if heroes_touched:
            clean_heroes = [h.replace('_', ' ').title() for h in heroes_touched[:12]]
            parts.append(f"Adjusted Heroes: {', '.join(clean_heroes)}")
        if items_touched:
            clean_items = [it.replace('_', ' ').title() for it in items_touched[:10]]
            parts.append(f"Adjusted Items: {', '.join(clean_items)}")

        content = "\n\n".join(parts)
        chunks.append((cat, title, content[:1500]))

    print(f"Parsed {len(chunks)} recent patch notes.")
    return chunks


# =====================================================================
# EMBEDDING & INGESTION PIPELINE
# =====================================================================


def sync_all():
    print("=" * 65)
    print("STARTING 100% AUTOMATED OPENDOTA KNOWLEDGE INGESTION PIPELINE")
    print("=" * 65)

    all_chunks = []
    all_chunks.extend(parse_all_items())
    all_chunks.extend(parse_all_heroes())
    all_chunks.extend(parse_pro_teams())
    all_chunks.extend(parse_esports_tournaments())
    all_chunks.extend(parse_the_international_champions())
    all_chunks.extend(parse_latest_patchnotes())

    print("\n" + "=" * 65)
    print(f"TOTAL PARSED CHUNKS: {len(all_chunks)}")
    print("=" * 65)

    if not all_chunks:
        raise ValueError("No knowledge fetched; existing documents are preserved.")
    embeddings = embed_batch_with_retry([f"{c[1]}\n{c[2]}" for c in all_chunks])
    replace_documents(all_chunks, embeddings=embeddings)
    return len(all_chunks)


if __name__ == "__main__":
    sync_all()
