import os
import sys
import json
import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.sync_opendota_meta_and_pros import DotaItemGraph

with open("app/data/items.json", "r", encoding="utf-8") as f:
    items_data = json.load(f)
with open("app/data/heroes.json", "r", encoding="utf-8") as f:
    heroes_data = json.load(f)

graph = DotaItemGraph(items_data)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def fetch_hero_build(hero):
    hid = hero.get("id")
    name = hero.get("localized_name")
    hid_str = str(hid)
    for attempt in range(5):
        try:
            res = requests.get(f"https://api.opendota.com/api/heroes/{hid}/itemPopularity", headers=headers, timeout=12)
            if res.status_code == 200:
                pop = res.json()
                b = graph.resolve_hero_build(pop)
                if b.get("early"):
                    return hid_str, b, name
            elif res.status_code == 429:
                time.sleep(2.0 * (attempt + 1))
        except Exception:
            time.sleep(1.0)
    return hid_str, None, name

print("Recomputing clean high-MMR builds (strictly 1 boot, no mid-game Midas)...")
hero_builds = {}

# Use 4 workers to stay well within OpenDota rate limits
with ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(fetch_hero_build, h) for h in heroes_data.values()]
    for i, fut in enumerate(as_completed(futures)):
        hid_str, b, name = fut.result()
        if b:
            hero_builds[hid_str] = b
            print(f"[{i+1}/{len(heroes_data)}] {name} -> Boot: {b['early'].split(',')[0]} | Mid: {b['mid']}")
        time.sleep(0.2)

with open("app/data/hero_builds.json", "w", encoding="utf-8") as f:
    json.dump(hero_builds, f, indent=2)

print(f"\nFINISHED! Saved {len(hero_builds)} clean hero builds.")

