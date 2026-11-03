"""
2026 Meta & Pro Player Knowledge Ingestion Pipeline (Patch 7.41+)
Fetches real-time item popularity, hero matchups/counters, and tier-1 pro player match logs
from OpenDota APIs & OpenDota SQL Explorer, embeds them via Gemini, and indexes them in Supabase.
"""

import sys
import os
import time
import requests
from typing import List, Dict, Any, Tuple, Optional

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from sqlalchemy import text
from app.database import SessionLocal
from app.services.rag import get_genai_client

HEADERS = {
    "User-Agent": "DotaBotTracker/2026.1 (OpenDota 7.41 meta sync; contact: study@example.com)"
}

BASE_URL = "https://api.opendota.com/api"

def get_pro_players_dict() -> Dict[int, Dict[str, Any]]:
    """
    Dynamically fetch all official pro players from OpenDota (/proPlayers).
    Zero hardcoded nicknames or IDs — automatically includes every registered pro.
    """
    print("Fetching official pro players dynamically from OpenDota (/proPlayers)...")
    try:
        res = requests.get(f"{BASE_URL}/proPlayers", headers=HEADERS, timeout=15)
        if res.status_code == 200:
            players_data = res.json()
            pro_map = {}
            for p in players_data:
                aid = p.get("account_id")
                name = p.get("name")
                if not aid or not name or len(name.strip()) < 2:
                    continue
                team = p.get("team_name") or p.get("team_tag") or "Pro Player"
                role_num = p.get("fantasy_role", 1)
                role_str = "Core (Pos 1/2/3)" if role_num == 1 else "Support (Pos 4/5)"
                pro_map[aid] = {
                    "account_id": aid,
                    "name": name.strip(),
                    "team": team.strip(),
                    "role": role_str,
                    "is_locked": p.get("is_locked", False),
                    "is_pro": p.get("is_pro", False),
                }
            print(f"Loaded {len(pro_map)} pro players dynamically from OpenDota.")
            return pro_map
    except Exception as e:
        print(f"Notice: Failed to fetch proPlayers: {e}")
    return {}


class DotaItemGraph:
    """
    Intelligent Dota 2 item crafting graph.
    Resolves recipe trees, component dependencies, and absorbs ingredients into completed items.
    """
    def __init__(self, raw_items: Dict[str, Any]):
        self.raw = raw_items
        self.id_to_key: Dict[int, str] = {}
        self.key_to_item: Dict[str, Dict[str, Any]] = {}
        self.subcomponents: Dict[str, set] = {}

        for key, item in raw_items.items():
            iid = item.get("id")
            if iid:
                self.id_to_key[iid] = key
            self.key_to_item[key] = {
                "id": iid,
                "key": key,
                "dname": item.get("dname", key.replace("_", " ").title()),
                "cost": item.get("cost", 0),
                "tier": item.get("tier"),
                "components": item.get("components") or [],
                "created": item.get("created", False),
            }

        # Precompute all recursive subcomponents and index all crafting ingredients
        self.ingredient_keys: set = set()
        for item in self.key_to_item.values():
            for comp_key in item["components"]:
                if comp_key and not comp_key.startswith("recipe_") and not comp_key.endswith("recipe"):
                    self.ingredient_keys.add(comp_key)

        for key in self.key_to_item:
            self._compute_subcomponents(key)

    def _compute_subcomponents(self, key: str, visited: Optional[set] = None) -> set:
        if key in self.subcomponents:
            return self.subcomponents[key]
        if visited is None:
            visited = set()
        if key in visited:
            return set()
        visited.add(key)

        item = self.key_to_item.get(key)
        if not item:
            return set()

        all_comps = set()
        for comp_key in item["components"]:
            if not comp_key or comp_key.startswith("recipe_") or comp_key.endswith("recipe"):
                continue
            all_comps.add(comp_key)
            all_comps.update(self._compute_subcomponents(comp_key, visited.copy()))

        self.subcomponents[key] = all_comps
        return all_comps

    def is_raw_component(self, key: str) -> bool:
        """Dynamically identifies basic ingredients that have no recipe and exist to build higher items."""
        item = self.key_to_item.get(key)
        if not item:
            return True
        # If it is used to craft other items and is not a crafted item itself
        if key in self.ingredient_keys and not item.get("created"):
            return True
        return False

    def is_standalone_item(self, key: str) -> bool:
        """Standalone major purchases that are not created via recipes (e.g. Blink Dagger, Ghost Scepter, Gem)."""
        return key in {"blink", "ghost", "gem", "ward_dispenser"}

    def is_trivial_consumable(self, key: str) -> bool:
        """Dynamically identifies consumables and trivial starting items (cost <= 250, not neutral, not created)."""
        item = self.key_to_item.get(key)
        if not item:
            return False
        cost = item.get("cost", 0)
        return cost <= 250 and not item.get("created") and item.get("tier") is None

    def is_subcomponent_of(self, comp_key: str, parent_keys: Any) -> bool:
        """Check if comp_key is a recursive ingredient of any item in parent_keys."""
        for p in parent_keys:
            if comp_key in self.subcomponents.get(p, set()):
                return True
        return False

    def is_completed_boot(self, key: str) -> bool:
        """Dynamically identifies upgraded boots (cost >= 800 and boot keyword in name/key)."""
        item = self.key_to_item.get(key)
        if not item:
            return False
        cost = item.get("cost", 0)
        name = item.get("dname", "").lower()
        k_lower = key.lower()
        is_boot = "boots" in k_lower or "treads" in k_lower or "boots" in name or "treads" in name
        return is_boot and cost >= 800

    def is_valid_start_item(self, key: str) -> bool:
        """Dynamically identifies valid starting items (cost <= 600, basic item, not neutral)."""
        item = self.key_to_item.get(key)
        if not item:
            return False
        cost = item.get("cost", 0)
        return (
            0 < cost <= 600
            and not item.get("created")
            and item.get("tier") is None
            and not key.startswith("recipe_")
            and not key.endswith("recipe")
        )

    def absorb_subcomponents(self, item_keys: List[str]) -> List[str]:
        """
        Deduplication rule: If item A is an ingredient of another item B in the list,
        absorb and drop A (e.g., Phase Boots absorbs Boots of Speed; Radiance absorbs Sacred Relic).
        """
        all_subs = set()
        for k in item_keys:
            all_subs.update(self.subcomponents.get(k, set()))
        return [k for k in item_keys if k not in all_subs]

    def resolve_hero_build(self, pop_data: Dict[str, Any]) -> Dict[str, str]:
        def get_ranked(sec_name: str) -> List[Tuple[str, int]]:
            raw_dict = pop_data.get(sec_name, {})
            ranked = []
            for iid_str, count in sorted(raw_dict.items(), key=lambda x: int(x[1]), reverse=True):
                try:
                    iid = int(iid_str)
                    k = self.id_to_key.get(iid)
                    if k and not k.startswith("recipe_") and not k.endswith("recipe"):
                        ranked.append((k, int(count)))
                except ValueError:
                    continue
            return ranked

        start_r = get_ranked("start_game_items")
        early_r = get_ranked("early_game_items")
        mid_r = get_ranked("mid_game_items")
        late_r = get_ranked("late_game_items")

        # 1. Boot choice: Strictly ONE boot for the entire hero build
        chosen_boot = None
        for k, _ in early_r + start_r:
            if self.is_completed_boot(k):
                chosen_boot = k
                break
        boot_subs = self.subcomponents.get(chosen_boot, set()) if chosen_boot else set()

        # 2. Late Game Luxury Spikes (30m+)
        late_candidates = []
        for k, _ in late_r:
            it = self.key_to_item.get(k, {})
            cost = it.get("cost", 0)
            if it.get("tier") is not None:
                continue
            if self.is_valid_start_item(k) or cost <= 500:
                continue
            if self.is_raw_component(k) and not self.is_standalone_item(k):
                continue
            if self.is_completed_boot(k) or k == "hand_of_midas":
                continue
            if cost >= 2200 or it.get("created"):
                if k not in late_candidates:
                    late_candidates.append(k)
        late_keys = self.absorb_subcomponents(late_candidates)[:5]
        late_subcomps = set()
        for k in late_keys:
            late_subcomps.update(self.subcomponents.get(k, set()))

        # 3. Mid Game Core Spikes (15-30m)
        mid_candidates = []
        has_major_farming_item = any(x in late_keys for x in ["radiance", "battle_fury"])
        for k, _ in mid_r:
            it = self.key_to_item.get(k, {})
            cost = it.get("cost", 0)
            if it.get("tier") is not None:
                continue
            if self.is_valid_start_item(k) or cost <= 500:
                continue
            if k in late_keys or k in late_subcomps:
                continue
            if self.is_raw_component(k) and not self.is_standalone_item(k):
                continue
            # NEVER allow any boot in mid game (exactly 1 boot in early game)
            if self.is_completed_boot(k):
                continue
            # NEVER allow Hand of Midas as a 4th/5th mid item, especially with Radiance/Battle Fury
            if k == "hand_of_midas":
                continue
            if cost >= 1400 or it.get("created"):
                if k not in mid_candidates:
                    mid_candidates.append(k)
                    if k in ["radiance", "battle_fury"]:
                        has_major_farming_item = True
        mid_keys = self.absorb_subcomponents(mid_candidates)[:4]
        mid_subcomps = set()
        for k in mid_keys:
            mid_subcomps.update(self.subcomponents.get(k, set()))

        # 4. Early Game Core (0-15m) - Exactly ONE boot + early core items
        all_higher_subcomps = late_subcomps.union(mid_subcomps).union(boot_subs)
        early_candidates = [chosen_boot] if chosen_boot else []
        for k, _ in early_r:
            it = self.key_to_item.get(k, {})
            if it.get("tier") is not None:
                continue
            # Skip if already chosen boot or another boot (strict 1 boot rule!)
            if self.is_completed_boot(k):
                continue
            if k in early_candidates or k in late_keys or k in mid_keys:
                continue
            if self.is_valid_start_item(k) or k in all_higher_subcomps:
                continue
            if self.is_raw_component(k) and not self.is_standalone_item(k):
                continue
            # Only allow Midas in early game if hero does not build Radiance/Battle Fury
            if k == "hand_of_midas" and has_major_farming_item:
                continue
            if it.get("created") or self.is_standalone_item(k) or it.get("cost", 0) >= 400:
                early_candidates.append(k)

        early_keys = self.absorb_subcomponents(early_candidates)[:4]

        # 5. Starting Items
        start_keys = []
        for k, _ in start_r:
            it = self.key_to_item.get(k, {})
            if it.get("tier") is not None:
                continue
            if self.is_valid_start_item(k) and k not in start_keys:
                start_keys.append(k)
                if len(start_keys) >= 5:
                    break

        def to_dnames(keys: List[str]) -> str:
            names = [self.key_to_item[k]["dname"] for k in keys if k in self.key_to_item and self.key_to_item[k]["dname"]]
            return ", ".join(names) if names else "Situational meta items"

        return {
            "starting": to_dnames(start_keys),
            "early": to_dnames(early_keys),
            "mid": to_dnames(mid_keys),
            "late": to_dnames(late_keys),
        }


def get_item_graph() -> DotaItemGraph:
    """Fetch OpenDota items constant and return initialized DotaItemGraph."""
    print("Fetching OpenDota items constant...")
    res = requests.get(f"{BASE_URL}/constants/items", headers=HEADERS, timeout=15)
    data = res.json()
    graph = DotaItemGraph(data)
    print(f"Loaded {len(graph.key_to_item)} items into item crafting graph.")
    return graph


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


def get_current_patch_name() -> str:
    """Dynamically get the latest active patch from OpenDota constants."""
    print("Fetching active patch dynamically from OpenDota (/constants/patch)...")
    try:
        res = requests.get(f"{BASE_URL}/constants/patch", headers=HEADERS, timeout=10)
        if res.status_code == 200:
            patches = res.json()
            if isinstance(patches, list) and patches:
                latest = patches[-1].get("name")
                if latest:
                    patch_str = f"Patch {latest}"
                    print(f"Current Dota 2 patch identified: {patch_str}")
                    return patch_str
    except Exception as e:
        print(f"Notice: Failed to fetch patch constants: {e}")
    return "Current Competitive Meta"


def fetch_json_with_retry(url: str, max_retries: int = 3, initial_delay: float = 1.0) -> Any:
    """Fetch OpenDota JSON with exponential backoff on HTTP 429 rate limits."""
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            res = requests.get(url, headers=HEADERS, timeout=12)
            if res.status_code == 200:
                return res.json()
            elif res.status_code == 429:
                print(f"Notice: OpenDota rate limit (429) on {url}. Backing off {delay}s...")
                time.sleep(delay)
                delay *= 2
            else:
                time.sleep(0.3)
        except Exception:
            time.sleep(0.3)
    return None


def parse_hero_meta_and_matchups(
    item_graph: DotaItemGraph, 
    heroes_dict: Dict[int, Dict[str, Any]],
    patch_name: str = "Current Competitive Meta",
    hero_limit: Optional[int] = None
) -> List[Tuple[str, str, str]]:
    """
    For heroes, fetch:
    1. /heroes/{hero_id}/itemPopularity (Resolved into completed items via DotaItemGraph)
    2. /heroes/{hero_id}/matchups (Hardest counters & favorable matchups)
    """
    print(f"\n--- 1. Parsing Hero Meta, Item Popularity & Matchup Counters ({patch_name}) ---")
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

        # 1. Item popularity resolved via Item Graph
        pop_data = fetch_json_with_retry(f"{BASE_URL}/heroes/{hid}/itemPopularity")
        if not pop_data or not isinstance(pop_data, dict) or not pop_data.get("early_game_items"):
            print(f"Skipping {name}: incomplete or rate-limited itemPopularity.")
            continue

        build = item_graph.resolve_hero_build(pop_data)
        start_items = build["starting"]
        early_items = build["early"]
        mid_items = build["mid"]
        late_items = build["late"]

        # 2. Matchups
        m_data = fetch_json_with_retry(f"{BASE_URL}/heroes/{hid}/matchups")
        if not m_data or not isinstance(m_data, list):
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
        title = f"Hero Meta & Item Build Guide: {name} ({patch_name})"

        content = f"""Hero Meta & Item Build Guide: {name} — {patch_name}
Attribute: {attr} | Attack Type: {attack} | Roles: {roles}

Verified High-MMR Item Build Progression (OpenDota Match Data):
• Starting Items: {start_items}
• Early Game Core (0-15m): {early_items}
• Mid Game Core Spikes (15-30m): {mid_items}
• Late Game / Extensions (30m+): {late_items}

{patch_name} Matchups & Counters:
• Strong Against (High Win Rate): {strong_str}
• Countered By (Low Win Rate / Struggles Against): {weak_str}"""

        chunks.append((cat, title, content))
        time.sleep(0.3)  # Respect OpenDota rate limits

    print(f"Generated {len(chunks)} Hero Meta & Matchup documents.")
    return chunks


def parse_pro_player_matches(
    item_graph: DotaItemGraph, 
    heroes_dict: Dict[int, Dict[str, Any]],
    patch_name: str = "Current Competitive Meta"
) -> List[Tuple[str, str, str]]:
    """
    Fetch actual recent matches of pro players dynamically from OpenDota.
    Zero hardcoded nicknames or IDs — uses OpenDota's /proPlayers registry and pro league matches.
    """
    print(f"\n--- 2. Parsing Real-Time Pro Player Matches via OpenDota Explorer ({patch_name}) ---")
    chunks = []

    pro_players = get_pro_players_dict()

    # Query official pro tournament matches directly from OpenDota SQL Explorer
    sql = """
    SELECT 
        pm.account_id,
        coalesce(p.name, 'Pro Player') AS pro_name,
        coalesce(t.name, 'Pro Team') AS team_name,
        pm.hero_id,
        h.localized_name AS hero_name,
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
    JOIN players p ON pm.account_id = p.account_id
    LEFT JOIN teams t ON p.team_id = t.team_id
    JOIN heroes h ON pm.hero_id = h.id
    WHERE m.leagueid > 0 AND p.name IS NOT NULL AND length(p.name) > 1
    ORDER BY m.start_time DESC
    LIMIT 120;
    """

    rows = []
    try:
        res = requests.get(f"{BASE_URL}/explorer", params={"sql": sql}, headers=HEADERS, timeout=20)
        if res.status_code == 200:
            rows = res.json().get("rows", [])
            print(f"Retrieved {len(rows)} pro match records from OpenDota SQL Explorer.")
    except Exception as e:
        print(f"Notice: OpenDota Explorer query notice: {e}")

    # Fallback to direct player matches if explorer is empty: take active pro players from dynamic pro_players dict
    if not rows and pro_players:
        print("Falling back to active /players/{id}/matches from dynamic pro players...")
        active_pros = [p for p in pro_players.values() if p.get("is_locked") or p.get("team") != "Pro Player"][:15]
        for p in active_pros:
            aid = p["account_id"]
            try:
                res = requests.get(f"{BASE_URL}/players/{aid}/matches?limit=10", headers=HEADERS, timeout=10)
                if res.status_code == 200:
                    for m in res.json():
                        m["account_id"] = aid
                        m["pro_name"] = p["name"]
                        m["team_name"] = p["team"]
                        rows.append(m)
                time.sleep(0.2)
            except Exception:
                pass

    for r in rows:
        aid = r.get("account_id")
        hid = r.get("hero_id")
        
        # Dynamic player and team names from OpenDota data
        pname = r.get("pro_name")
        if not pname or pname == "Pro Player":
            pname = pro_players.get(aid, {}).get("name") if aid in pro_players else "Pro Player"
        if not pname or pname == "Pro Player":
            continue

        team = r.get("team_name")
        if not team or team == "Pro Team":
            team = pro_players.get(aid, {}).get("team", "Tier 1")

        role = pro_players.get(aid, {}).get("role", "Core")

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

        # Final 6 slotted items
        completed_keys = set()
        final_items = []
        for slot in ["item_0", "item_1", "item_2", "item_3", "item_4", "item_5", "item_neutral"]:
            item_id = r.get(slot)
            if item_id and item_id in item_graph.id_to_key:
                k_item = item_graph.id_to_key[item_id]
                completed_keys.add(k_item)
                dname = item_graph.key_to_item.get(k_item, {}).get("dname")
                if dname and not dname.endswith("Recipe"):
                    final_items.append(dname)

        # Parse purchase timeline - highlight completed items, suppress basic ingredients
        purchase_log = r.get("purchase_log") or []
        timeline_items = []
        if isinstance(purchase_log, list):
            for p in purchase_log:
                if not isinstance(p, dict):
                    continue
                pkey = p.get("key")
                ptime = p.get("time", 0)
                if ptime is not None and ptime >= 0 and pkey:
                    # Suppress raw ingredients of completed items (e.g. chainmail/boots for phase)
                    if item_graph.is_raw_component(pkey) and item_graph.is_subcomponent_of(pkey, completed_keys):
                        continue
                    # Suppress trivial consumables dynamically (cost <= 250, not created)
                    if item_graph.is_trivial_consumable(pkey):
                        continue
                    item_data = item_graph.key_to_item.get(pkey)
                    display = item_data["dname"] if item_data else pkey.replace("_", " ").title()
                    if not display.endswith("Recipe"):
                        minutes = ptime // 60
                        seconds = ptime % 60
                        timeline_items.append(f"{minutes:02d}:{seconds:02d} - {display}")

        final_items_str = ", ".join(final_items) if final_items else "Endgame inventory not available"
        timeline_summary = " • " + "\n • ".join(timeline_items[:10]) if timeline_items else "Timeline not recorded"

        cat = f"Pro Match: {pname} on {hero_name}"
        title = f"Pro Build: {hero_name} by {pname} ({team}) — {patch_name}"

        content = f"""Verified Pro Match Record: {hero_name} played by {pname} ({team}) — {patch_name}
Result: {result_str} (KDA: {k}/{d}/{a} | GPM: {gpm}) | Match ID: {match_id}
Role: {role}

Item Purchase Timeline:
{timeline_summary}

Final Items Slotted:
{final_items_str}"""

        chunks.append((cat, title, content))

    print(f"Generated {len(chunks)} Pro Player Match documents.")
    return chunks


def embed_batch_with_retry(batch: List[str], max_retries: int = 5) -> List[List[float]]:
    client = get_genai_client()
    models_to_try = ["gemini-embedding-2-preview", "gemini-embedding-2", "gemini-embedding-001"]
    individual_embeddings = []

    for text_item in batch:
        item_emb = None
        for model_name in models_to_try:
            delay = 1.0
            for attempt in range(max_retries):
                try:
                    res = client.models.embed_content(
                        model=model_name,
                        contents=text_item,
                        config={"output_dimensionality": 768}
                    )
                    item_emb = res.embeddings[0].values
                    break
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                        time.sleep(delay)
                        delay *= 1.5
                    elif "404" in err_str or "NOT_FOUND" in err_str or "not found" in err_str.lower():
                        break
                    else:
                        time.sleep(1.0)
            if item_emb is not None:
                break
        if item_emb is not None:
            individual_embeddings.append(item_emb)
        else:
            raise RuntimeError(f"Failed to embed item with all models: {batch}")

    return individual_embeddings


def run_meta_and_pros_sync(hero_limit: Optional[int] = None) -> int:
    patch_name = get_current_patch_name()
    print("=" * 65)
    print(f"STARTING OPENDOTA META & PRO PLAYER INGESTION ({patch_name})")
    print("=" * 65)

    item_graph = get_item_graph()
    heroes_dict = get_heroes_dict()

    all_chunks = []
    # 1. Hero Meta & Matchups (resolved with Item Crafting Graph)
    all_chunks.extend(parse_hero_meta_and_matchups(item_graph, heroes_dict, patch_name=patch_name, hero_limit=hero_limit))
    # 2. Pro Player Matches
    all_chunks.extend(parse_pro_player_matches(item_graph, heroes_dict, patch_name=patch_name))

    print("\n" + "=" * 65)
    print(f"TOTAL PARSED META CHUNKS ({patch_name}): {len(all_chunks)}")
    print("=" * 65)

    db = SessionLocal()
    try:
        batch_size = 10
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
            time.sleep(2.0)

        total_in_db = db.execute(text("SELECT count(*) FROM hero_documents")).scalar()
        print("\n" + "=" * 65)
        print(f"SUCCESS: 2026 META SYNC COMPLETE! Total indexed chunks in DB: {total_in_db}")
        print("=" * 65)
        return len(all_chunks)
    finally:
        db.close()


if __name__ == "__main__":
    run_meta_and_pros_sync()

