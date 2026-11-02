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
from app.services.rag import get_genai_client

# Comprehensive Esports & Modern Game Mechanics knowledge documents
ESPORTS_AND_MECHANICS_DOCS = [
    {
        "category": "Esports: The International 2024 (TI13)",
        "title": "The International 2024 (TI13) - Champions, Roster, Location & Results",
        "content": """The International 2024 (TI13) took place in the Royal Arena in Copenhagen, Denmark from September 4 to 15, 2024.
Grand Finals Result: Team Liquid defeated Gaimin Gladiators with a dominant 3-0 sweep to claim the Aegis of Champions.

Team Liquid Championship Roster (TI 2024):
• Pos 1 (Carry): miCKe (Michael Vu) - Sweden
• Pos 2 (Mid): Nisha (Michal Jankowski) - Poland [Named Tournament MVP]
• Pos 3 (Offlane): 33 (Neta Shapira) - Israel [Became a two-time TI champion after winning TI11 with Tundra]
• Pos 4 (Support): Boxi (Samuel Svahn) - Sweden
• Pos 5 (Hard Support / Captain): Insania (Aydin Sarkohi) - Sweden
• Coach: Blitz (William Lee)

Top 4 Finishers:
1st Place: Team Liquid ($1,160,000+)
2nd Place: Gaimin Gladiators (dyrachyo, Quinn, Ace, tOfu, Seleri)
3rd Place: Tundra Esports (Pure~, Topson, RAMZES666, Saksa, Whitemon)
4th Place: Team Falcons (skiter, Malr1ne, ATF, Cr1t-, Sneyking)

Key Narrative: Team Liquid had previously lost 6 consecutive Tier-1 Grand Finals to Gaimin Gladiators throughout 2023 and 2024, but decisively broke the curse on the TI stage with an unstoppable 3-0 victory."""
    },
    {
        "category": "Esports: The International All-Time Champions",
        "title": "The International (TI) All-Time Champions History (TI1 to TI13)",
        "content": """Official History of The International Champions (TI1 to TI13):
• TI1 (2011, Cologne): Natus Vincere / Na'Vi (3-1 vs EHOME) — Artstyle, Dendi, XBOCT, Puppey, LightOfHeaVen.
• TI2 (2012, Seattle): Invictus Gaming / IG (3-1 vs Na'Vi) — Zhou, Ferrari_430, YYF, ChuaN, Faith.
• TI3 (2013, Seattle): Alliance (3-2 vs Na'Vi) — Loda, s4, AdmiralBulldog, EGM, Akke (Iconic $1M Dream Coil).
• TI4 (2014, Seattle): Newbee (3-1 vs Vici Gaming) — Hao, Mu, Xiao8, Banana, SanSheng.
• TI5 (2015, Seattle): Evil Geniuses / EG (3-1 vs CDEC) — Fear, SumaiL, UNiVeRsE, Aui_2000, ppd (6-Million-Dollar Echo Slam).
• TI6 (2016, Seattle): Wings Gaming (3-1 vs Digital Chaos) — shadow, bLink, Faith_bian, iceice, y`.
• TI7 (2017, Seattle): Team Liquid (3-0 vs Newbee) — MATUMBAMAN, Miracle-, MinD_ContRoL, GH, KuroKy.
• TI8 (2018, Vancouver): OG (3-2 vs PSG.LGD) — ana, Topson, Ceb, JerAx, N0tail (Legendary Cinderella run from open qualifiers).
• TI9 (2019, Shanghai): OG (3-1 vs Team Liquid) — ana, Topson, Ceb, JerAx, N0tail (First back-to-back TI champions in history).
• TI10 (2021, Bucharest): Team Spirit (3-2 vs PSG.LGD) — Yatoro, TORONTOTOKYO, Collapse, Mira, Miposhka (Collapse Magnus masterclass).
• TI11 (2022, Singapore): Tundra Esports (3-0 vs Team Secret) — skiter, Nine, 33, Saksa, Sneyking (Coached by Aui_2000).
• TI12 (2023, Seattle): Team Spirit (3-0 vs Gaimin Gladiators) — Yatoro, Larl, Collapse, Mira, Miposhka (Team Spirit becomes 2-time TI champions).
• TI13 (2024, Copenhagen): Team Liquid (3-0 vs Gaimin Gladiators) — miCKe, Nisha, 33, Boxi, Insania."""
    },
    {
        "category": "Esports: Riyadh Masters & Esports World Cup",
        "title": "Riyadh Masters / Esports World Cup History and Champions",
        "content": """Riyadh Masters (part of Esports World Cup in Riyadh, Saudi Arabia) is the premier multi-million dollar annual summer championship in Dota 2:
• Riyadh Masters 2024 (EWC 2024):
  - Champion: Gaimin Gladiators (3-0 vs Team Liquid in Grand Finals, earning $1,500,000).
  - Roster: dyrachyo, Quinn, Ace, tOfu, Seleri.
  - 3rd Place: Team Falcons; 4th Place: Tundra Esports.
• Riyadh Masters 2023:
  - Champion: Team Spirit (3-1 vs Team Liquid, earning $5,000,000).
  - Roster: Yatoro, Larl, Collapse, Mira, Miposhka.
• Riyadh Masters 2022:
  - Champion: PSG.LGD (2-0 vs Team Spirit)."""
    },
    {
        "category": "Esports: Tier-1 Pro Teams and Rosters",
        "title": "Top Tier-1 Dota 2 Pro Teams and Current Rosters (2024-2025)",
        "content": """Current Tier-1 Competitive Dota 2 Teams and Rosters:
1. Team Falcons (The dominant team of 2024 - won BetBoom Dacha Dubai, DreamLeague S22, ESL One Birmingham, DreamLeague S23):
   • Pos 1: skiter (Oliver Lepko)
   • Pos 2: Malr1ne (Stanislav Potorak)
   • Pos 3: ATF / Ammar The F (Ammar Al-Assaf)
   • Pos 4: Cr1t- (Andreas Nielsen)
   • Pos 5 / Captain: Sneyking (Jingjun Wu)
   • Coach: Aui_2000 (Kurtis Ling)

2. Team Liquid (TI13 Champions):
   • Pos 1: miCKe
   • Pos 2: Nisha
   • Pos 3: SaberLight- (Jonás Volek, joined post-TI13 replacing 33)
   • Pos 4: Boxi
   • Pos 5 / Captain: Insania
   • Coach: Blitz

3. Gaimin Gladiators (Riyadh Masters 2024 Champions):
   • Pos 1: watson (Alimzhan Islambekov, joined post-TI13 replacing dyrachyo)
   • Pos 2: Quinn (Quinn Callahan)
   • Pos 3: Ace (Marcus Hoelgaard)
   • Pos 4: tOfu (Erik Engel)
   • Pos 5 / Captain: Seleri (Melchior Hillenkamp)

4. Team Spirit (Two-time TI Champions):
   • Post-TI13 lineup: Satanic (Alan Gallyamov), larl (Denis Sigitov), Malik (Abdimalik Sailau), rue (Aleksandr Filin), Miposhka (Yaroslav Naidenov). Iconic stars Yatoro (Raddan) and Collapse took a temporary hiatus.

5. BetBoom Team:
   • Pos 1: Pure~ (Ivan Moskalenko)
   • Pos 2: kiyotaka (Gleb Zyryanov)
   • Pos 3: MieRo` (Matvey Vasyunin)
   • Pos 4: Save- (Vitalie Melnic)
   • Pos 5: Kataomi` (Vladislav Semenov)

6. Tundra Esports:
   • Pos 1: Nightfall (Egor Grigorenko)
   • Pos 2: Lorenof (Artem Melnick)
   • Pos 3 / Captain: 33 (Neta Shapira)
   • Pos 4: Saksa (Martin Sazdov)
   • Pos 5: Whitemon (Matthew Filemon)

7. Heroic:
   • Historic South American roster that won PGL Wallachia Season 2 (first SA team ever to win a Tier-1 international LAN): K1 (Hector Rodriguez), 4nalog, Davai Lama, Scofield, KJ."""
    },
    {
        "category": "Esports: Legendary Players & Records",
        "title": "Dota 2 Legendary Players, Records and Two-Time TI Winners",
        "content": """Dota 2 Legends & Hall of Fame Records:
• Two-Time TI Champions Club:
  - OG: N0tail (Johan Sundstein), Ceb (Sebastien Debs), Topson (Topias Taavitsainen), JerAx (Jesse Vainikka), ana (Anathan Pham) — Won TI8 & TI9 consecutively.
  - Team Spirit: Yatoro / Raddan (Illya Mulyarchuk), Collapse (Magomed Khalilov), Miposhka (Yaroslav Naidenov), Mira (Miroslav Kolpakov) — Won TI10 & TI12.
  - 33 (Neta Shapira) — Won TI11 with Tundra Esports and TI13 with Team Liquid.
• The GOAT Captains:
  - Puppey (Clement Ivanov): Won TI1, reached 4 TI finals, attended 11 consecutive TIs.
  - KuroKy (Kuro Salehi Takhasomi): Won TI7 with Liquid, reached 3 TI finals.
  - N0tail: 4 Valve Majors and 2 The Internationals.
• The Uncrowned King: Ame (Wang Chunyu) — Reached multiple TI grand finals with PSG.LGD and won numerous Majors."""
    },
    {
        "category": "Mechanics: Map Objectives & Timers",
        "title": "Tormentors, Lotus Pools, Twin Gates, Watchers & Map Objectives",
        "content": """Key Dota 2 Map Objectives & Critical Timers (Patch 7.33+ / 7.36+):
1. Tormentors:
   • Spawn at exactly 20:00 near each team's offlane edge.
   • Features 2500 Shield, 0 movespeed, and reflects 70% of damage taken back as physical damage to all nearby heroes in a 1200 radius.
   • Slaying a Tormentor rewards an Aghanim's Shard to one of the two lowest net-worth heroes on the team who lacks one, plus 250 gold to all allies.
   • Respawns 10 minutes after death, gaining +500 shield, +20 HP/sec regen, and +20% damage reflection each respawn.
2. Lotus Pools:
   • Spawns Healing Lotuses every 3:00 on the edges of the side lanes.
   • Lotuses combine automatically in inventory: 3 Healing Lotuses -> Great Lotus (restores 400 HP/MP); 2 Great Lotuses -> Greater Lotus (restores 900 HP/MP).
   • Greater Lotus + Cheese in Fountain = Block of Cheese (grants a permanent 500 HP barrier that regenerates when not taking damage for 5 seconds).
3. Twin Gates:
   • Positioned at the top-right and bottom-left map corners.
   • Allows heroes to channel for 3 seconds to instantly teleport across the map to the other gate (75 mana cost).
4. Watchers:
   • Capturable vision lanterns. Channel for 1.5 seconds to turn on, granting 800 radius vision for 7 minutes. Enemy heroes can channel for 1.5s to disable them for 2 minutes."""
    },
    {
        "category": "Mechanics: Roshan Cycle & Drops",
        "title": "Roshan Day/Night Cycle, Pit Locations, and Drops",
        "content": """Roshan Mechanics & Drop Cycle:
1. Day/Night Pits:
   • Daytime (starts at 0:00, 10:00, 20:00...): Roshan occupies the Southeast (Radiant) pit near bottom rune.
   • Nighttime (starts at 5:00, 15:00, 25:00...): Roshan travels through the Twin Gate to the Northwest (Dire) pit near top rune.
   • If attacked while walking through the Twin Gate, he knocks back and stuns anyone in his path.
2. Kill Drops:
   • 1st Kill: Aegis of the Immortal (resurrects bearer with full HP/mana after a 5s delay; expires after 5 minutes).
   • 2nd Kill: Aegis of the Immortal + Cheese (instantly restores 2500 HP and 1500 Mana) OR Roshan's Banner (places a banner in a lane that buffs allied lane creeps with +75% health and +50% damage for 5 minutes).
   • 3rd Kill: Aegis of the Immortal + Cheese + either Aghanim's Blessing (consumable Scepter) OR Refresher Shard (resets all cooldowns and mana costs once).
3. Respawn Timer:
   • Roshan respawns at a random time between 8 and 11 minutes after death."""
    },
    {
        "category": "Mechanics: Runes and Timings",
        "title": "Dota 2 Runes Guide: Power Runes, Water Runes, Wisdom Runes & Bounty Runes",
        "content": """Dota 2 Runes and Spawn Intervals:
1. Power Runes:
   • Spawn at 6:00 and every 2 minutes thereafter (8:00, 10:00, 12:00...) in one of the two river locations.
   • Types:
     - Amplify Damage (formerly Double Damage): +80% base attack damage and +15% spell amp for 45s.
     - Haste: Sets movement speed to maximum (550), immune to slows for 30s.
     - Invisibility: True invisibility for 45s (2s fade time).
     - Regeneration: Restores 100 HP/sec and 67 Mana/sec until full or damaged.
     - Arcane: 30% cooldown reduction and 30% mana cost reduction for 50s.
     - Shield: Grants a barrier absorbing 50% of the hero's max HP for 75s.
2. Water Runes:
   • Spawn at both river rune spots at minute 2:00 and minute 4:00. Restores 80 HP and 80 Mana instantly. Crucial for midlaners.
3. Wisdom Runes:
   • Spawn at 7:00, 14:00, 21:00, 28:00... near the offlane bases.
   • Grants substantial XP to the player who collects it and the lowest-level hero on the team.
4. Bounty Runes:
   • Spawn at 0:00 and every 3 minutes (3:00, 6:00, 9:00...) at 4 jungle rune locations, awarding gold to the entire team."""
    },
    {
        "category": "Mechanics: Neutral Items & Tokens",
        "title": "Neutral Items and Neutral Tokens System (Tiers 1 to 5)",
        "content": """Neutral Items System:
Neutral items are dropped by killing jungle neutral creeps as 'Neutral Tokens'. A token lets the player choose 1 of 5 randomized neutral items suitable for their hero.
Tiers and Drop Timings:
• Tier 1 (7:00+): Trusty Shovel, Arcane Ring, Safety Bubble, Occult Bracelet, Spark of Courage, Pig Pole, Broom Handle, Fairie's Trinket, Duelist Gloves.
• Tier 2 (17:00+): Philosopher's Stone, Specialist's Array, Bullwhip, Dragon Scale, Vambrace, Gossamer Cape, Eye of the Vizier, Orb of Destruction.
• Tier 3 (27:00+): Defiant Shell, Paladin Sword, Nemesis Curse, Enchanted Quiver, Elven Tunic, Ceremonial Robe, Dandelion Amulet, Doubloon.
• Tier 4 (37:00+): Mind Breaker, Ninja Gear, Timeless Relic, Ascetic's Cap, Stormcrafter, Trickster Cloak, Aviana's Feather, Havoc Hammer.
• Tier 5 (60:00+): Apex, Mirror Shield, Book of Shadows, Piracy Cloak, Giant's Ring, Force Boots, Seer Stone, Unwavering Condition, Book of the Dead."""
    },
    {
        "category": "Mechanics: Innates & Facets System",
        "title": "Dota 2 Innate Abilities and Hero Facets Explained (Patch 7.36+)",
        "content": """The Innate Abilities and Hero Facets System (Introduced in Patch 7.36):
1. Innate Abilities:
   • Every single hero in Dota 2 now possesses a free Innate Ability from minute 0.
   • Some Innates are unique passives that level up automatically with hero level (e.g. Dawnbreaker reveals the whole map at sunrise; Faceless Void slows projectile speeds).
   • Other Innates grant level 1 of an existing signature skill for free at level 1 (e.g. Anti-Mage starts with Mana Break at level 1 and can allocate 4 additional skill points).
2. Hero Facets:
   • During the pre-game strategy phase, each player chooses between 2 to 3 distinct 'Facets' for their hero.
   • Facets customize abilities, enhance specific playstyles, or grant unique passive bonuses.
   • Examples:
     - Anti-Mage: 'Magebane's Mirror' (Counterspell reflects targeted spells) vs 'Mana Thirst' (bonus damage & true sight on low-mana enemies).
     - Shadow Fiend: 'Last Reflection' vs 'Shadowmire'.
     - Juggernaut: 'Bladestorm' (Blade Fury can critically strike) vs 'Relentless'."""
    },
    {
        "category": "Mechanics: Ranked Matchmaking & MMR",
        "title": "Ranked Matchmaking, MMR Brackets, and Behavior Score",
        "content": """Dota 2 Ranked Brackets and Matchmaking System:
1. Medal Brackets (Approximate MMR values):
   • Herald: 0 – 770 MMR
   • Guardian: 770 – 1540 MMR
   • Crusader: 1540 – 2310 MMR
   • Archon: 2310 – 3080 MMR
   • Legend: 3080 – 3850 MMR
   • Ancient: 3850 – 4620 MMR
   • Divine: 4620 – 5420 MMR
   • Immortal: 5420+ MMR (Features numbered leaderboards from rank 5000 down to Rank 1).
2. Behavior & Communication Score:
   • Range: 0 to 12,000 score.
   • Score 12,000 gives access to all communication features, coaching, and tipping.
   • Below 3,000 score completely disables ranked matchmaking, text chat, voice chat, and pinging allies."""
    }
]


def clean_text(raw_text: Any) -> str:
    if not raw_text:
        return ""
    if isinstance(raw_text, list):
        raw_text = " ".join(str(x) for x in raw_text)
    elif not isinstance(raw_text, str):
        raw_text = str(raw_text)
    cleaned = re.sub(r'%[a-zA-Z0-9_]+%', '', raw_text)
    cleaned = re.sub(r'</?(?:h[1-6]|p|div|br)[^>]*>', '\n', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned


def format_item_chunk(raw_item: dict) -> tuple[str, str, str]:
    """Format an OpenDota item dictionary into a clean, searchable RAG document chunk."""
    name = raw_item.get("dname") or "Unknown Item"
    cost = raw_item.get("cost")
    tier = raw_item.get("tier")
    is_neutral = tier is not None

    if is_neutral:
        title = f"Item: {name} (Tier {tier} Neutral Item)"
        category = f"Neutral Item: {name}"
        header = f"Item: {name} (Tier {tier} Neutral Item)"
    else:
        title = f"Item: {name} ({cost} Gold)"
        category = f"Item: {name}"
        header = f"Item: {name} (Total Cost: {cost} gold)"

    parts = [header]

    components = raw_item.get("components")
    if components and isinstance(components, list):
        comp_names = [str(c).replace('_', ' ').title() for c in components if c]
        if comp_names:
            parts.append(f"Recipe / Built from: {', '.join(comp_names)}")

    attribs = raw_item.get("attrib", [])
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

    abilities = raw_item.get("abilities", [])
    if isinstance(abilities, list):
        for ab in abilities:
            if not isinstance(ab, dict):
                continue
            ab_type = str(ab.get("type", "")).capitalize()
            ab_title = str(ab.get("title", ""))
            ab_desc = clean_text(ab.get("description", ""))
            parts.append(f"{ab_type}: {ab_title}\n{ab_desc}")

    notes = clean_text(raw_item.get("notes", ""))
    if notes:
        parts.append(f"Notes: {notes}")

    lore = clean_text(raw_item.get("lore", ""))
    if lore:
        parts.append(f"Lore: {lore}")

    content = "\n\n".join(parts)
    return category, title, content[:1500]


def embed_batch_with_retry(batch: List[str], max_retries: int = 5) -> List[List[float]]:
    """Embed a single batch of texts with automatic backoff on 429 rate limit."""
    client = get_genai_client()
    delay = 4.0
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
                print(f"Rate limited (429). Backing off for {delay:.1f}s (attempt {attempt + 1}/{max_retries})...")
                time.sleep(delay)
                delay *= 1.5
            else:
                print(f"Error during embed: {e}")
                time.sleep(2)
    raise RuntimeError("Exceeded maximum retries for embedding batch.")


def ingest_all():
    print("=" * 65)
    print("INGESTING ALL DOTA 2 KNOWLEDGE: ESPORTS, MECHANICS, & ITEMS")
    print("=" * 65)

    db = SessionLocal()
    try:
        # 1. Ingest Esports and Game Mechanics
        print("\n1. Ingesting Esports & Game Mechanics documents...")
        for doc in ESPORTS_AND_MECHANICS_DOCS:
            cat = doc["category"]
            title = doc["title"]
            content = doc["content"]
            
            # Check if exists
            exists = db.execute(text("SELECT 1 FROM hero_documents WHERE hero_name = :h"), {"h": cat}).first()
            if not exists:
                text_to_embed = f"{title}\n{content}"
                emb = embed_batch_with_retry([text_to_embed])[0]
                vector_str = "[" + ",".join(map(str, emb)) + "]"
                db.execute(text("""
                    INSERT INTO hero_documents (hero_name, section_title, content, embedding)
                    VALUES (:h, :t, :c, CAST(:e AS vector))
                """), {"h": cat, "t": title, "c": content, "e": vector_str})
                db.commit()
                print(f" -> Ingested: {title}")
                time.sleep(1.0)
            else:
                print(f" -> Already exists: {title}")

        # 2. Ingest All Dota 2 Items from OpenDota Constants
        print("\n2. Fetching comprehensive Dota 2 items constants...")
        res = requests.get("https://api.opendota.com/api/constants/items", timeout=15)
        raw_items_dict = res.json()

        valid_items = []
        for key, item in raw_items_dict.items():
            name = item.get("dname")
            if not name or name.endswith("Recipe") or key.startswith("recipe_"):
                continue
            cost = item.get("cost")
            tier = item.get("tier")
            if (cost is not None and cost > 0) or tier is not None:
                valid_items.append(item)

        print(f"Found {len(valid_items)} official items (standard + neutral items).")

        # Query existing item categories to skip already-ingested ones
        existing_rows = db.execute(text("SELECT hero_name FROM hero_documents WHERE hero_name LIKE 'Item:%' OR hero_name LIKE 'Neutral Item:%'")).fetchall()
        existing_names = set(r[0] for r in existing_rows)
        print(f"Currently have {len(existing_names)} items already indexed.")

        items_to_process = []
        for item in valid_items:
            cat, title, content = format_item_chunk(item)
            if cat not in existing_names:
                text_to_embed = f"{title}\n{content}"
                items_to_process.append((cat, title, content, text_to_embed))

        print(f"Items remaining to embed and index: {len(items_to_process)}")

        batch_size = 15
        for i in range(0, len(items_to_process), batch_size):
            chunk = items_to_process[i:i + batch_size]
            texts = [c[3] for c in chunk]
            embeddings = embed_batch_with_retry(texts)

            for (cat, title, content, _), emb in zip(chunk, embeddings):
                db.execute(text("DELETE FROM hero_documents WHERE hero_name = :h"), {"h": cat})
                vector_str = "[" + ",".join(map(str, emb)) + "]"
                db.execute(text("""
                    INSERT INTO hero_documents (hero_name, section_title, content, embedding)
                    VALUES (:h, :t, :c, CAST(:e AS vector))
                """), {"h": cat, "t": title, "c": content, "e": vector_str})
            db.commit()
            print(f"Indexed batch [{i + 1} to {min(i + batch_size, len(items_to_process))}] / {len(items_to_process)}")
            time.sleep(2.0)

        # 3. Print Final Summary Count
        res_count = db.execute(text("SELECT count(*) FROM hero_documents")).scalar()
        print("\n" + "=" * 65)
        print(f"SUCCESS! Total documents now indexed in vector DB: {res_count}")
        print("=" * 65)

    finally:
        db.close()


if __name__ == "__main__":
    ingest_all()
