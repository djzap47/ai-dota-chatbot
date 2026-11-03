import os
import sys
import json
import time
import requests
from typing import Dict, Any

# Ensure project root in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from scripts.sync_opendota_meta_and_pros import get_item_graph, get_heroes_dict

os.makedirs("app/data", exist_ok=True)

print("Fetching bulk Dota constants from dotaconstants CDN...")
heroes = requests.get('https://unpkg.com/dotaconstants/build/heroes.json').json()
items = requests.get('https://unpkg.com/dotaconstants/build/items.json').json()
abilities = requests.get('https://unpkg.com/dotaconstants/build/abilities.json').json()
hero_abilities = requests.get('https://unpkg.com/dotaconstants/build/hero_abilities.json').json()
aghs = requests.get('https://unpkg.com/dotaconstants/build/aghs_desc.json').json()

with open("app/data/heroes.json", "w", encoding="utf-8") as f:
    json.dump(heroes, f)
with open("app/data/items.json", "w", encoding="utf-8") as f:
    json.dump(items, f)
with open("app/data/abilities.json", "w", encoding="utf-8") as f:
    json.dump(abilities, f)
with open("app/data/hero_abilities.json", "w", encoding="utf-8") as f:
    json.dump(hero_abilities, f)
with open("app/data/aghs_desc.json", "w", encoding="utf-8") as f:
    json.dump(aghs, f)

print("Saved all bulk Dota constants to app/data/ successfully!")

