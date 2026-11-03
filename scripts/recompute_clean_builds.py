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
                "name": "Pos 3 Offlane",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Hand of Midas, Blink Dagger",
                "mid": "Black King Bar, Shiva's Guard, Aghanim's Scepter",
                "late": "Refresher Orb, Octarine Core, Overwhelming Blink, Heart of Tarrasque"
            },
            {
                "name": "Pos 2 Mid",
                "starting": "Tango, Iron Branch, Faerie Fire, Quelling Blade, Circlet",
                "early": "Bottle, Phase Boots, Blink Dagger",
                "mid": "Black King Bar, Shiva's Guard, Octarine Core",
                "late": "Refresher Orb, Overwhelming Blink, Scythe of Vyse, Aghanim's Scepter"
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
                "name": "Pos 1/3 Core",
                "starting": "Quelling Blade, Tango, Iron Branch, Magic Stick, Gauntlets of Strength",
                "early": "Phase Boots, Vanguard, Blade Mail",
                "mid": "Blink Dagger, Black King Bar, Aghanim's Scepter",
                "late": "Heart of Tarrasque, Shiva's Guard, Overwhelming Blink, Bloodstone"
            },
            {
                "name": "Pos 4 Support",
                "starting": "Tango, Blood Grenade, Observer Ward, Sentry Ward, Iron Branch, Magic Stick",
                "early": "Tranquil Boots, Magic Wand, Glimmer Cape",
                "mid": "Blink Dagger, Force Staff, Aghanim's Shard",
                "late": "Lotus Orb, Wind Waker, Aghanim's Scepter, Scythe of Vyse"
            }
        ]
    },
    # Magnus
    "97": {
        "hero_name": "Magnus",
        "builds": [
            {
                "name": "Pos 1 Carry",
                "starting": "Quelling Blade, Tango, Iron Branch, Gauntlets of Strength, Circlet",
                "early": "Power Treads, Echo Sabre or Harpoon, Mask of Madness",
                "mid": "Black King Bar, Blink Dagger, Aghanim's Scepter or Daedalus",
                "late": "Satanic, Refresher Orb, Swift Blink, Nullifier"
            },
            {
                "name": "Pos 3 Offlane",
                "starting": "Tango, Quelling Blade, Iron Branch, Gauntlets of Strength, Circlet",
                "early": "Power Treads, Bracer, Blink Dagger",
                "mid": "Harpoon or Force Staff, Black King Bar, Aghanim's Shard",
                "late": "Shiva's Guard, Refresher Orb, Overwhelming Blink, Octarine Core"
            },
            {
                "name": "Pos 2 Mid",
                "starting": "Tango, Iron Branch, Faerie Fire, Circlet, Quelling Blade",
                "early": "Bottle, Power Treads, Blink Dagger",
                "mid": "Harpoon, Black King Bar, Aghanim's Scepter",
                "late": "Refresher Orb, Shiva's Guard, Swift Blink, Scythe of Vyse"
            }
        ]
    },
    # Lina
    "25": {
        "hero_name": "Lina",
        "builds": [
            {
                "name": "Pos 1 Carry",
                "starting": "Tango, Iron Branch, Circlet, Slippers of Agility, Faerie Fire",
                "early": "Falcon Blade, Phase Boots, Maelstrom",
                "mid": "Black King Bar, Gleipnir, Daedalus, Hurricane Pike",
                "late": "Satanic, Butterfly, Swift Blink, Silver Edge"
            },
            {
                "name": "Pos 2 Mid",
                "starting": "Tango, Iron Branch, Faerie Fire, Circlet, Mantle of Intelligence",
                "early": "Bottle, Boots of Travel, Eul's Scepter of Divinity",
                "mid": "Black King Bar, Aghanim's Scepter, Scythe of Vyse",
                "late": "Octarine Core, Ethereal Blade, Refresher Orb, Swift Blink"
            },
            {
                "name": "Pos 4 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Sentry Ward, Faerie Fire",
                "early": "Arcane Boots, Magic Wand, Wind Lace",
                "mid": "Aether Lens, Eul's Scepter of Divinity, Force Staff",
                "late": "Glimmer Cape, Aghanim's Shard, Scythe of Vyse, Lotus Orb"
            }
        ]
    },
    # Windranger
    "21": {
        "hero_name": "Windranger",
        "builds": [
            {
                "name": "Pos 1/2 Core",
                "starting": "Tango, Iron Branch, Circlet, Slippers of Agility, Faerie Fire",
                "early": "Power Treads, Bottle or Falcon Blade, Maelstrom",
                "mid": "Black King Bar, Gleipnir, Linken's Sphere or Manta Style",
                "late": "Daedalus, Scythe of Vyse, Butterfly, Nullifier"
            },
            {
                "name": "Pos 4/5 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Sentry Ward, Faerie Fire",
                "early": "Tranquil Boots, Magic Wand, Solar Crest",
                "mid": "Force Staff, Glimmer Cape, Aghanim's Shard",
                "late": "Scythe of Vyse, Lotus Orb, Wind Waker, Aeon Disk"
            }
        ]
    },
    # Tiny
    "19": {
        "hero_name": "Tiny",
        "builds": [
            {
                "name": "Pos 1 Carry",
                "starting": "Quelling Blade, Tango, Iron Branch, Gauntlets of Strength, Circlet",
                "early": "Power Treads, Echo Sabre, Shadow Blade",
                "mid": "Black King Bar, Daedalus, Silver Edge, Assault Cuirass",
                "late": "Satanic, Swift Blink, Moon Shard, Nullifier"
            },
            {
                "name": "Pos 2 Mid",
                "starting": "Tango, Iron Branch, Faerie Fire, Circlet, Quelling Blade",
                "early": "Bottle, Power Treads, Blink Dagger",
                "mid": "Echo Sabre or Harpoon, Black King Bar, Daedalus",
                "late": "Assault Cuirass, Satanic, Overwhelming Blink, Refresher Orb"
            },
            {
                "name": "Pos 4 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Boots of Speed",
                "early": "Tranquil Boots, Magic Wand, Wind Lace",
                "mid": "Blink Dagger, Force Staff, Aghanim's Shard, Eul's Scepter",
                "late": "Lotus Orb, Solar Crest, Octarine Core, Wind Waker"
            }
        ]
    },
    # Gyrocopter
    "72": {
        "hero_name": "Gyrocopter",
        "builds": [
            {
                "name": "Pos 1 Carry",
                "starting": "Quelling Blade, Tango, Iron Branch, Circlet, Slippers of Agility",
                "early": "Power Treads, Falcon Blade, Sange and Yasha",
                "mid": "Black King Bar, Satanic, Butterfly, Aghanim's Scepter",
                "late": "Daedalus, Swift Blink, Eye of Skadi, Nullifier"
            },
            {
                "name": "Pos 4/5 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Faerie Fire, Sentry Ward",
                "early": "Tranquil Boots, Magic Wand, Drum of Endurance",
                "mid": "Force Staff, Glimmer Cape, Aghanim's Shard, Eul's Scepter",
                "late": "Boots of Bearing, Lotus Orb, Solar Crest, Scythe of Vyse"
            }
        ]
    },
    # Vengeful Spirit
    "20": {
        "hero_name": "Vengeful Spirit",
        "builds": [
            {
                "name": "Pos 1 Carry",
                "starting": "Quelling Blade, Tango, Iron Branch, Circlet, Slippers of Agility",
                "early": "Power Treads, Falcon Blade, Dragon Lance",
                "mid": "Manta Style, Aghanim's Scepter, Black King Bar",
                "late": "Butterfly, Daedalus, Hurricane Pike, Satanic"
            },
            {
                "name": "Pos 5 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Faerie Fire, Sentry Ward",
                "early": "Tranquil Boots, Magic Wand, Pavise or Solar Crest",
                "mid": "Force Staff, Glimmer Cape, Aghanim's Scepter",
                "late": "Lotus Orb, Wind Waker, Aeon Disk, Boots of Bearing"
            }
        ]
    },
    # Dragon Knight
    "49": {
        "hero_name": "Dragon Knight",
        "builds": [
            {
                "name": "Pos 2 Mid",
                "starting": "Quelling Blade, Tango, Iron Branch, Gauntlets of Strength, Circlet",
                "early": "Bottle, Power Treads, Soul Ring or Armlet",
                "mid": "Black King Bar, Blink Dagger, Manta Style or Maelstrom",
                "late": "Assault Cuirass, Eye of Skadi, Overwhelming Blink, Satanic"
            },
            {
                "name": "Pos 3 Offlane",
                "starting": "Quelling Blade, Tango, Iron Branch, Gauntlets of Strength, Circlet",
                "early": "Power Treads, Bracer, Blink Dagger",
                "mid": "Black King Bar, Harpoon, Aghanim's Scepter",
                "late": "Assault Cuirass, Overwhelming Blink, Shiva's Guard, Refresher Orb"
            }
        ]
    },
    # Snapfire
    "128": {
        "hero_name": "Snapfire",
        "builds": [
            {
                "name": "Pos 2 Mid",
                "starting": "Tango, Iron Branch, Faerie Fire, Circlet, Quelling Blade",
                "early": "Bottle, Power Treads, Dragon Lance",
                "mid": "Black King Bar, Daedalus, Hurricane Pike, Maelstrom or Gleipnir",
                "late": "Eye of Skadi, Satanic, Swift Blink, Scythe of Vyse"
            },
            {
                "name": "Pos 4/5 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Faerie Fire, Sentry Ward",
                "early": "Arcane or Tranquil Boots, Magic Wand, Pavise",
                "mid": "Solar Crest, Force Staff, Glimmer Cape, Aghanim's Shard",
                "late": "Lotus Orb, Guardian Greaves, Scythe of Vyse, Wind Waker"
            }
        ]
    },
    # Mirana
    "9": {
        "hero_name": "Mirana",
        "builds": [
            {
                "name": "Pos 2 Mid",
                "starting": "Tango, Iron Branch, Faerie Fire, Circlet, Slippers of Agility",
                "early": "Bottle, Power Treads, Maelstrom",
                "mid": "Manta Style, Black King Bar, Gleipnir",
                "late": "Eye of Skadi, Butterfly, Daedalus, Scythe of Vyse"
            },
            {
                "name": "Pos 4 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Faerie Fire, Sentry Ward",
                "early": "Tranquil or Arcane Boots, Magic Wand, Urn of Shadows",
                "mid": "Spirit Vessel, Eul's Scepter, Force Staff, Solar Crest",
                "late": "Lotus Orb, Glimmer Cape, Scythe of Vyse, Wind Waker"
            }
        ]
    },
    # Naga Siren
    "89": {
        "hero_name": "Naga Siren",
        "builds": [
            {
                "name": "Pos 1 Carry",
                "starting": "Quelling Blade, Tango, Iron Branch, Slippers of Agility, Circlet",
                "early": "Power Treads, Wraith Band, Diffusal Blade",
                "mid": "Manta Style, Heart of Tarrasque, Butterfly",
                "late": "Eye of Skadi, Disperser, Bloodthorn, Swift Blink"
            },
            {
                "name": "Pos 4 Support",
                "starting": "Tango, Blood Grenade, Iron Branch, Sentry Ward, Faerie Fire",
                "early": "Arcane Boots, Magic Wand, Solar Crest",
                "mid": "Aether Lens, Lotus Orb, Aghanim's Scepter",
                "late": "Guardian Greaves, Wind Waker, Octarine Core, Scythe of Vyse"
            }
        ]
    }
}

import requests
import time
from scripts.sync_opendota_meta_and_pros import DotaItemGraph

items_data_path = os.path.join(DATA_DIR, "items.json")
with open(items_data_path, "r", encoding="utf-8") as f:
    items_data = json.load(f)

graph = DotaItemGraph(items_data)

raw_pop_path = os.path.join(DATA_DIR, "raw_popularity.json")
raw_pop_cache = {}
if os.path.exists(raw_pop_path):
    with open(raw_pop_path, "r", encoding="utf-8") as f:
        try:
            raw_pop_cache = json.load(f)
        except Exception:
            raw_pop_cache = {}

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DotaBot/2.0"
}

def fetch_hero_popularity(hid_str: str) -> Dict[str, Any]:
    if hid_str in raw_pop_cache and raw_pop_cache[hid_str]:
        return raw_pop_cache[hid_str]
    for attempt in range(5):
        try:
            res = requests.get(f"https://api.opendota.com/api/heroes/{hid_str}/itemPopularity", headers=headers, timeout=12)
            if res.status_code == 200:
                data = res.json()
                raw_pop_cache[hid_str] = data
                return data
            elif res.status_code == 429:
                time.sleep(2.5 * (attempt + 1))
        except Exception:
            time.sleep(1.0)
    return {}

def build_all_clean_hero_builds():
    output_builds = {}
    print(f"Generating clean multi-variant builds for all {len(heroes_data)} heroes...")

    for i, (hid_str, hero) in enumerate(heroes_data.items(), 1):
        hname = hero.get("localized_name")
        if hid_str in CURATED_BUILDS:
            output_builds[hid_str] = CURATED_BUILDS[hid_str]
            print(f"[{i}/{len(heroes_data)}] {hname} -> Using Curated Multi-Build")
            continue

        pop = fetch_hero_popularity(hid_str)
        if pop:
            b = graph.resolve_hero_build(pop)
            output_builds[hid_str] = {
                "hero_name": hname,
                "builds": [{
                    "name": "Standard",
                    "starting": b.get("starting", "Tango, Iron Branch, Magic Stick"),
                    "early": b.get("early", "Power Treads, Magic Wand"),
                    "mid": b.get("mid", "Black King Bar, Blink Dagger"),
                    "late": b.get("late", "Scythe of Vyse, Refresher Orb")
                }]
            }
            print(f"[{i}/{len(heroes_data)}] {hname} -> Real Build: {b.get('early')} | Mid: {b.get('mid')}")
        time.sleep(0.15)

    with open(raw_pop_path, "w", encoding="utf-8") as f:
        json.dump(raw_pop_cache, f, indent=2)

    with open(os.path.join(DATA_DIR, "hero_builds.json"), "w", encoding="utf-8") as f:
        json.dump(output_builds, f, indent=2)

    print(f"\nSUCCESS! Built comprehensive clean builds for {len(output_builds)} heroes in hero_builds.json.")

if __name__ == "__main__":
    build_all_clean_hero_builds()
