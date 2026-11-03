"""
Authoritative High-MMR Dota 2 Build Generator.
Structures builds for all 127 heroes into distinct coherent variants (Build 1 & Build 2 where applicable),
strictly following the 4 gameplay phases:
  - Starting Items: initial laning sustain and stats
  - Early Game: Primary Boot + first farming/tempo engine (or support save item)
  - Mid Game Core: 2-3 core items the hero needs to fight
  - Late Game: Expensive luxury game-closers (Refresher Orb, Eye of Skadi, Butterfly, Abyssal Blade, Satanic, etc.)
Zero neutral items, zero conflicting farming engines (no BF + Mjollnir), zero troll components.
"""

import os
import sys
import json
from typing import Dict, Any, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

DATA_DIR = "app/data"
heroes_path = os.path.join(DATA_DIR, "heroes.json")
with open(heroes_path, "r", encoding="utf-8") as f:
    heroes_data = json.load(f)

# Explicit, expert 7000+ MMR dual-build specifications for key flexible heroes
CURATED_BUILDS = {
    # Faceless Void
    "41": {
        "hero_name": "Faceless Void",
        "builds": [
            {
                "name": "Maelstrom",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Magic Wand, Maelstrom",
                "mid": "Manta Style or Black King Bar, Mjollnir",
                "late": "Eye of Skadi, Butterfly, Refresher Orb, Satanic"
            },
            {
                "name": "Battle Fury",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Wraith Band, Battle Fury",
                "mid": "Manta Style, Aghanim's Scepter, Black King Bar",
                "late": "Butterfly, Eye of Skadi, Refresher Orb, Swift Blink"
            }
        ]
    },
    # Juggernaut
    "8": {
        "hero_name": "Juggernaut",
        "builds": [
            {
                "name": "Battle Fury",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Faerie Fire",
                "early": "Phase Boots, Magic Wand, Battle Fury",
                "mid": "Manta Style, Aghanim's Scepter, Butterfly",
                "late": "Swift Blink, Eye of Skadi, Abyssal Blade, Refresher Orb"
            },
            {
                "name": "Maelstrom",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Faerie Fire",
                "early": "Phase Boots, Wraith Band, Maelstrom",
                "mid": "Manta Style, Diffusal Blade or Gleipnir, Aghanim's Scepter",
                "late": "Butterfly, Nullifier, Swift Blink, Eye of Skadi"
            }
        ]
    },
    # Lifestealer
    "54": {
        "hero_name": "Lifestealer",
        "builds": [
            {
                "name": "Radiance",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Bracer, Armlet of Mordiggian",
                "mid": "Radiance, Sange and Yasha, Skull Basher",
                "late": "Abyssal Blade, Assault Cuirass, Nullifier, Satanic"
            },
            {
                "name": "Desolator",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Orb of Corrosion, Armlet of Mordiggian",
                "mid": "Desolator, Sange and Yasha or Black King Bar, Skull Basher",
                "late": "Abyssal Blade, Assault Cuirass, Nullifier, Bloodthorn"
            }
        ]
    },
    # Phantom Assassin
    "44": {
        "hero_name": "Phantom Assassin",
        "builds": [
            {
                "name": "Battle Fury",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Wraith Band, Battle Fury",
                "mid": "Desolator, Black King Bar, Aghanim's Scepter",
                "late": "Skull Basher into Abyssal Blade, Satanic, Nullifier"
            },
            {
                "name": "Desolator",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Orb of Corrosion, Desolator",
                "mid": "Black King Bar, Skull Basher, Aghanim's Scepter",
                "late": "Abyssal Blade, Satanic, Eye of Skadi, Nullifier"
            }
        ]
    },
    # Anti-Mage
    "1": {
        "hero_name": "Anti-Mage",
        "builds": [
            {
                "name": "Battle Fury",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Magic Wand, Battle Fury",
                "mid": "Manta Style, Black King Bar, Skull Basher",
                "late": "Abyssal Blade, Butterfly, Eye of Skadi, Aghanim's Scepter"
            }
        ]
    },
    # Spectre
    "67": {
        "hero_name": "Spectre",
        "builds": [
            {
                "name": "Radiance",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Blade Mail, Radiance",
                "mid": "Manta Style, Aghanim's Scepter, Heart of Tarrasque",
                "late": "Eye of Skadi, Abyssal Blade, Butterfly, Bloodthorn"
            },
            {
                "name": "Blade Mail",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Blade Mail, Orchid Malevolence",
                "mid": "Manta Style, Aghanim's Scepter, Skull Basher",
                "late": "Bloodthorn, Abyssal Blade, Eye of Skadi, Nullifier"
            }
        ]
    },
    # Wraith King
    "42": {
        "hero_name": "Wraith King",
        "builds": [
            {
                "name": "Radiance",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Armlet of Mordiggian, Radiance",
                "mid": "Blink Dagger, Black King Bar, Assault Cuirass",
                "late": "Refresher Orb, Abyssal Blade, Overwhelming Blink, Heart of Tarrasque"
            },
            {
                "name": "Desolator",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Armlet of Mordiggian, Desolator",
                "mid": "Blink Dagger, Black King Bar, Assault Cuirass",
                "late": "Nullifier, Abyssal Blade, Overwhelming Blink, Refresher Orb"
            }
        ]
    },
    # Sniper
    "35": {
        "hero_name": "Sniper",
        "builds": [
            {
                "name": "Maelstrom & Attack Speed Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Circlet, Slippers of Agility",
                "early": "Power Treads, Dragon Lance, Maelstrom",
                "mid": "Hurricane Pike, Mjollnir or Gleipnir, Black King Bar",
                "late": "Daedalus, Butterfly, Eye of Skadi, Swift Blink"
            },
            {
                "name": "Aghanim's Shard & Burst Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Circlet, Slippers of Agility",
                "early": "Power Treads, Dragon Lance, Falcon Blade",
                "mid": "Aghanim's Scepter, Silver Edge, Black King Bar",
                "late": "Daedalus, Eye of Skadi, Swift Blink, Refresher Orb"
            }
        ]
    },
    # Ursa
    "70": {
        "hero_name": "Ursa",
        "builds": [
            {
                "name": "Battle Fury Farming Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Phase Boots, Magic Wand, Battle Fury",
                "mid": "Blink Dagger, Black King Bar, Skull Basher",
                "late": "Abyssal Blade, Aghanim's Scepter, Satanic, Swift Blink"
            },
            {
                "name": "Diffusal Fast Aggression Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Phase Boots, Orb of Corrosion, Diffusal Blade",
                "mid": "Blink Dagger, Black King Bar, Skull Basher",
                "late": "Abyssal Blade, Aghanim's Scepter, Nullifier, Disperser"
            }
        ]
    },
    # Sven
    "18": {
        "hero_name": "Sven",
        "builds": [
            {
                "name": "Echo Sabre & Cleave Burst Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Power Treads, Magic Wand, Echo Sabre",
                "mid": "Blink Dagger, Black King Bar, Harpoon",
                "late": "Daedalus, Bloodthorn, Swift Blink, Satanic"
            },
            {
                "name": "Mask of Madness & S&Y Fighting Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Power Treads, Mask of Madness, Sange and Yasha",
                "mid": "Blink Dagger, Black King Bar, Daedalus",
                "late": "Bloodthorn, Swift Blink, Satanic, Assault Cuirass"
            }
        ]
    },
    # Slark
    "93": {
        "hero_name": "Slark",
        "builds": [
            {
                "name": "Diffusal & Orchid Aggressive Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Magic Wand, Diffusal Blade",
                "mid": "Orchid Malevolence, Aghanim's Scepter, Black King Bar",
                "late": "Eye of Skadi, Disperser, Bloodthorn, Abyssal Blade"
            },
            {
                "name": "Mage Slayer & Echo Sabre Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
                "early": "Power Treads, Mage Slayer, Echo Sabre",
                "mid": "Aghanim's Scepter, Black King Bar, Harpoon",
                "late": "Eye of Skadi, Abyssal Blade, Butterfly, Satanic"
            }
        ]
    },
    # Alchemist
    "73": {
        "hero_name": "Alchemist",
        "builds": [
            {
                "name": "Radiance Sustain Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Soul Ring, Radiance",
                "mid": "Black King Bar, Blink Dagger, Assault Cuirass",
                "late": "Abyssal Blade, Heart of Tarrasque, Refresher Orb, Shiva's Guard"
            },
            {
                "name": "Battle Fury Physical Burst Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Quelling Blade, Battle Fury",
                "mid": "Black King Bar, Sange and Yasha, Assault Cuirass",
                "late": "Abyssal Blade, Swift Blink, Bloodthorn, Moon Shard"
            }
        ]
    },
    # Morphling
    "10": {
        "hero_name": "Morphling",
        "builds": [
            {
                "name": "Dragon Lance & Manta Physical Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Circlet, Slippers of Agility",
                "early": "Power Treads, Morbid Mask, Dragon Lance",
                "mid": "Manta Style, Linken's Sphere or Black King Bar, Butterfly",
                "late": "Eye of Skadi, Satanic, Swift Blink, Daedalus"
            },
            {
                "name": "Kaya & Sange Shotgun / Magic Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Circlet, Slippers of Agility",
                "early": "Power Treads, Falcon Blade, Kaya",
                "mid": "Kaya and Sange, Ethereal Blade, Black King Bar",
                "late": "Eye of Skadi, Butterfly, Satanic, Swift Blink"
            }
        ]
    },
    # Ember Spirit
    "106": {
        "hero_name": "Ember Spirit",
        "builds": [
            {
                "name": "Physical / Battle Fury & Daedalus Build",
                "starting": "Tango, Iron Branch, Quelling Blade, Faerie Fire, Bottle",
                "early": "Phase Boots, Bottle, Battle Fury",
                "mid": "Desolator, Black King Bar, Daedalus",
                "late": "Refresher Orb, Eye of Skadi, Linken's Sphere, Divine Rapier"
            },
            {
                "name": "Magic / Mage Slayer & Radiance Build",
                "starting": "Tango, Iron Branch, Quelling Blade, Faerie Fire, Bottle",
                "early": "Phase Boots, Bottle, Mage Slayer",
                "mid": "Maelstrom, Eul's Scepter or Black King Bar, Aghanim's Scepter",
                "late": "Shiva's Guard, Gleipnir, Refresher Orb, Wind Waker"
            }
        ]
    },
    # Storm Spirit
    "17": {
        "hero_name": "Storm Spirit",
        "builds": [
            {
                "name": "Witch Blade & Orchid Burst Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Bottle",
                "early": "Power Treads, Bottle, Witch Blade",
                "mid": "Orchid Malevolence, Kaya and Sange, Black King Bar",
                "late": "Bloodthorn, Scythe of Vyse, Shiva's Guard, Parasma"
            },
            {
                "name": "Bloodstone Scaling Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Bottle",
                "early": "Power Treads, Bottle, Kaya",
                "mid": "Bloodstone, Black King Bar, Aghanim's Scepter",
                "late": "Scythe of Vyse, Shiva's Guard, Refresher Orb, Wind Waker"
            }
        ]
    },
    # Queen of Pain
    "39": {
        "hero_name": "Queen of Pain",
        "builds": [
            {
                "name": "Witch Blade & Orchid Burst Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Bottle",
                "early": "Power Treads, Bottle, Witch Blade",
                "mid": "Orchid Malevolence, Black King Bar, Aghanim's Scepter",
                "late": "Scythe of Vyse, Bloodthorn, Parasma, Refresher Orb"
            },
            {
                "name": "Kaya & Sange / Shiva's Teamfight Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Bottle",
                "early": "Power Treads, Bottle, Kaya",
                "mid": "Kaya and Sange, Black King Bar, Shiva's Guard",
                "late": "Scythe of Vyse, Refresher Orb, Wind Waker, Octarine Core"
            }
        ]
    },
    # Shadow Fiend
    "11": {
        "hero_name": "Shadow Fiend",
        "builds": [
            {
                "name": "Physical / Dragon Lance & Daedalus Build",
                "starting": "Tango, Iron Branch, Circlet, Slippers of Agility, Faerie Fire",
                "early": "Power Treads, Wraith Band, Dragon Lance",
                "mid": "Shadow Blade, Black King Bar, Daedalus",
                "late": "Silver Edge, Butterfly, Swift Blink, Satanic"
            },
            {
                "name": "Magic / Eul's & Blink Requiem Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Bottle",
                "early": "Power Treads, Bottle, Eul's Scepter",
                "mid": "Blink Dagger, Black King Bar, Aghanim's Scepter",
                "late": "Scythe of Vyse, Arcane Blink, Refresher Orb, Wind Waker"
            }
        ]
    },
    # Tiny
    "19": {
        "hero_name": "Tiny",
        "builds": [
            {
                "name": "Carry / Echo Sabre & Tree Burst Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Power Treads, Magic Wand, Echo Sabre",
                "mid": "Blink Dagger, Black King Bar, Harpoon",
                "late": "Daedalus, Assault Cuirass, Satanic, Swift Blink"
            },
            {
                "name": "Mid / Bottle & Blink Ganking Build",
                "starting": "Tango, Iron Branch, Gauntlets of Strength, Faerie Fire, Bottle",
                "early": "Power Treads, Bottle, Blink Dagger",
                "mid": "Black King Bar, Aghanim's Scepter, Daedalus",
                "late": "Assault Cuirass, Satanic, Swift Blink, Refresher Orb"
            }
        ]
    },
    # Lina
    "25": {
        "hero_name": "Lina",
        "builds": [
            {
                "name": "Physical Carry / Falcon Blade & Maelstrom Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Circlet, Slippers of Agility",
                "early": "Power Treads, Falcon Blade, Maelstrom",
                "mid": "Dragon Lance, Black King Bar, Gleipnir",
                "late": "Daedalus, Satanic, Butterfly, Swift Blink"
            },
            {
                "name": "Magic / Eul's & Aghanim's Burst Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Bottle",
                "early": "Power Treads, Bottle, Eul's Scepter",
                "mid": "Aghanim's Scepter, Black King Bar, Octarine Core",
                "late": "Scythe of Vyse, Ethereal Blade, Refresher Orb, Wind Waker"
            }
        ]
    },
    # Doom
    "69": {
        "hero_name": "Doom",
        "builds": [
            {
                "name": "Blink & Shiva Teamfight Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Hand of Midas, Blink Dagger",
                "mid": "Black King Bar, Shiva's Guard, Aghanim's Scepter",
                "late": "Refresher Orb, Octarine Core, Overwhelming Blink, Heart of Tarrasque"
            },
            {
                "name": "Radiance & Aura Tank Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Hand of Midas, Radiance",
                "mid": "Black King Bar, Blink Dagger, Assault Cuirass",
                "late": "Shiva's Guard, Refresher Orb, Heart of Tarrasque, Overwhelming Blink"
            }
        ]
    },
    # Invoker
    "74": {
        "hero_name": "Invoker",
        "builds": [
            {
                "name": "Quas-Wex / Witch Blade & Urn Aggressive Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Faerie Fire",
                "early": "Phase Boots, Urn of Shadows, Witch Blade",
                "mid": "Spirit Vessel, Black King Bar, Aghanim's Scepter",
                "late": "Scythe of Vyse, Octarine Core, Refresher Orb, Parasma"
            },
            {
                "name": "Quas-Exort / Midas & Eul's Scaling Build",
                "starting": "Tango, Iron Branch, Circlet, Mantle of Intelligence, Faerie Fire",
                "early": "Boots of Travel, Hand of Midas, Eul's Scepter",
                "mid": "Blink Dagger, Black King Bar, Aghanim's Scepter",
                "late": "Scythe of Vyse, Octarine Core, Refresher Orb, Shiva's Guard"
            }
        ]
    },
    # Pudge
    "14": {
        "hero_name": "Pudge",
        "builds": [
            {
                "name": "Core / Tank & Initiator Build",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Bottle or Vanguard, Blade Mail",
                "mid": "Blink Dagger, Black King Bar, Aghanim's Scepter",
                "late": "Heart of Tarrasque, Shiva's Guard, Overwhelming Blink, Bloodstone"
            },
            {
                "name": "Support / Roaming & Utility Build",
                "starting": "Tango, Blood Grenade, Observer Ward, Sentry Ward, Iron Branch, Magic Stick",
                "early": "Tranquil Boots, Magic Wand, Glimmer Cape",
                "mid": "Blink Dagger, Force Staff, Aghanim's Shard",
                "late": "Lotus Orb, Wind Waker, Aghanim's Scepter, Scythe of Vyse"
            }
        ]
    }
}

def generate_default_build_for_hero(hero: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generate high-MMR role-appropriate single-boot 4-phase build for uncurated heroes."""
    name = hero.get("localized_name", "")
    roles = hero.get("roles", [])
    attr = str(hero.get("primary_attr", "")).upper()
    is_support = "Support" in roles and "Carry" not in roles

    if is_support:
        # Standard Support Progression
        return [{
            "name": "Standard",
            "starting": "Tango, Blood Grenade, Sentry Ward, Observer Ward, Iron Branch, Magic Stick",
            "early": "Tranquil Boots or Arcane Boots, Magic Wand, Glimmer Cape or Force Staff",
            "mid": "Blink Dagger, Ghost Scepter, Aghanim's Shard, Eul's Scepter or Aeon Disk",
            "late": "Aghanim's Scepter, Scythe of Vyse, Wind Waker, Lotus Orb, Refresher Orb"
        }]

    # Initiator / Offlane Tank
    if "Initiator" in roles or "Durable" in roles:
        boot = "Phase Boots" if attr == "STR" else "Power Treads"
        return [{
            "name": "Standard",
            "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
            "early": f"{boot}, Bracer, Blade Mail or Vanguard",
            "mid": "Blink Dagger, Black King Bar, Pipe of Insight or Crimson Guard",
            "late": "Overwhelming Blink, Shiva's Guard, Heart of Tarrasque, Assault Cuirass, Refresher Orb"
        }]

    # Standard Carry / Mid Core
    boot = "Power Treads" if attr == "AGI" else ("Power Treads" if attr == "INT" else "Phase Boots")
    return [{
        "name": "Standard",
        "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Circlet",
        "early": f"{boot}, Magic Wand, Maelstrom or Falcon Blade",
        "mid": "Manta Style or Sange and Yasha, Black King Bar, Skull Basher",
        "late": "Butterfly, Eye of Skadi, Abyssal Blade, Satanic, Swift Blink"
    }]

def build_all_clean_hero_builds():
    output_builds = {}
    print(f"Generating clean multi-variant builds for all {len(heroes_data)} heroes...")

    for hid_str, hero in heroes_data.items():
        hname = hero.get("localized_name")
        if hid_str in CURATED_BUILDS:
            output_builds[hid_str] = CURATED_BUILDS[hid_str]
        else:
            output_builds[hid_str] = {
                "hero_name": hname,
                "builds": generate_default_build_for_hero(hero)
            }

    with open(os.path.join(DATA_DIR, "hero_builds.json"), "w", encoding="utf-8") as f:
        json.dump(output_builds, f, indent=2)

    print(f"SUCCESS! Built comprehensive clean builds for {len(output_builds)} heroes in hero_builds.json.")

if __name__ == "__main__":
    build_all_clean_hero_builds()
