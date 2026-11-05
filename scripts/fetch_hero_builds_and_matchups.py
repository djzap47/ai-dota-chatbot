import os
import sys
import time
import json
import requests
from typing import Dict, Any

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.sync_opendota_meta_and_pros import DotaItemGraph

from pathlib import Path
DATA_DIR = Path(__file__).resolve().parents[1] / "app" / "data"

def normalize_build(entry, hero_name):
    if "builds" in entry:
        builds = entry["builds"]
    elif entry:
        builds = [dict(entry, name=entry.get("name", "Standard"))]
    else:
        builds = []
    if not isinstance(builds, list) or any(
        not isinstance(b.get(phase), str) or not b[phase].strip()
        for b in builds for phase in ("starting", "early", "mid", "late")
    ):
        raise ValueError(f"Invalid cached build for {hero_name}")
    return dict(entry, hero_name=hero_name, builds=builds)

def main():
    # Load local constants
    with open(DATA_DIR / "items.json", "r", encoding="utf-8") as f:
        items_data = json.load(f)
    with open(DATA_DIR / "heroes.json", "r", encoding="utf-8") as f:
        heroes_data = json.load(f)

    graph = DotaItemGraph(items_data)

    builds_file = DATA_DIR / "hero_builds.json"
    matchups_file = DATA_DIR / "hero_matchups.json"

    hero_builds = {}
    if os.path.exists(builds_file):
        with open(builds_file, "r", encoding="utf-8") as f:
            hero_builds = json.load(f)

    hero_matchups = {}
    if os.path.exists(matchups_file):
        with open(matchups_file, "r", encoding="utf-8") as f:
            hero_matchups = json.load(f)

    print(f"Loaded existing: {len(hero_builds)} builds, {len(hero_matchups)} matchups.")

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    heroes_list = sorted(heroes_data.values(), key=lambda h: h.get("id", 0))

    for idx, hero in enumerate(heroes_list):
        hid = hero.get("id")
        name = hero.get("localized_name")
        hid_str = str(hid)

        if hid_str in hero_builds:
            hero_builds[hid_str] = normalize_build(hero_builds[hid_str], name)

        # 1. Fetch item build if not already cached or empty
        if hid_str not in hero_builds or not hero_builds[hid_str].get("builds"):
            for attempt in range(4):
                try:
                    res = requests.get(f"https://api.opendota.com/api/heroes/{hid}/itemPopularity", headers=headers, timeout=10)
                    if res.status_code == 200:
                        pop = res.json()
                        b = graph.resolve_hero_build(pop)
                        if b.get("mid") and b["mid"] != "Standard meta items" and b["mid"] != "Situational meta items":
                            hero_builds[hid_str] = normalize_build(b, name)
                            print(f"[{idx+1}/{len(heroes_list)}] {name}: Mid core items -> {b['mid']}")
                            break
                    elif res.status_code == 429:
                        print(f"Rate limited on {name}. Waiting 2s...")
                        time.sleep(2.0)
                except Exception as e:
                    time.sleep(1.0)
            time.sleep(0.3)

        # 2. Fetch matchups if not already cached
        if hid_str not in hero_matchups or not hero_matchups[hid_str].get("counters"):
            for attempt in range(4):
                try:
                    m_res = requests.get(f"https://api.opendota.com/api/heroes/{hid}/matchups", headers=headers, timeout=10)
                    if m_res.status_code == 200:
                        m_data = m_res.json()
                        valid = []
                        for m in m_data:
                            opp_id = str(m.get("hero_id"))
                            g = m.get("games_played", 0)
                            w = m.get("wins", 0)
                            if g >= 15 and opp_id in heroes_data:
                                wr = round((w / g) * 100, 1)
                                opp_name = heroes_data[opp_id].get("localized_name")
                                valid.append((opp_name, wr))
                        strong = sorted(valid, key=lambda x: x[1], reverse=True)[:5]
                        weak = sorted(valid, key=lambda x: x[1])[:5]
                        hero_matchups[hid_str] = {
                            "hero_name": name,
                            "strong_against": [f"{n} ({w}%)" for n, w in strong],
                            "counters": [f"{n} ({w}%)" for n, w in weak],
                        }
                        break
                    elif m_res.status_code == 429:
                        print(f"Rate limited on {name} matchups. Waiting 2s...")
                        time.sleep(2.0)
                except Exception:
                    time.sleep(1.0)
            time.sleep(0.3)

        # Save progress every 10 heroes
        if (idx + 1) % 10 == 0 or idx == len(heroes_list) - 1:
            with open(builds_file, "w", encoding="utf-8") as f:
                json.dump(hero_builds, f, indent=2)
            with open(matchups_file, "w", encoding="utf-8") as f:
                json.dump(hero_matchups, f, indent=2)

    print(f"\nCOMPLETED! Total builds cached: {len(hero_builds)}, matchups: {len(hero_matchups)}")



if __name__ == "__main__":
    main()
