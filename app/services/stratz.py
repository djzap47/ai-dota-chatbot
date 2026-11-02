import requests
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from app.config import settings
from app.models import Hero, HeroStat
from app.database import SessionLocal

STRATZ_API_URL = "https://api.stratz.com/graphql"

def get_headers() -> dict:
    token = settings.STRATZ_API_KEY
    if not token:
        raise ValueError("STRATZ_API_KEY is not set in the environment variables.")
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "STRATZ_API",
        "Content-Type": "application/json"
    }

def fetch_hero_stats() -> dict:
    """
    Fetch hero definitions (including official Valve roles) and 
    the latest single-day Immortal statistics from STRATZ GraphQL API.
    """
    query = """
    query {
      constants {
        heroes {
          id
          displayName
          roles {
            roleId
          }
        }
      }
      heroStats {
        winDay(bracketIds: [IMMORTAL]) {
          heroId
          day
          winCount
          matchCount
        }
      }
    }
    """

    response = requests.post(STRATZ_API_URL, json={'query': query}, headers=get_headers(), timeout=30)
    
    if response.status_code != 200:
        raise Exception(f"STRATZ API returned {response.status_code}: {response.text}")
        
    data = response.json()
    
    if 'errors' in data:
        raise Exception(f"STRATZ API Error: {data['errors']}")

    heroes_data = data['data']['constants']['heroes']
    stats_data = data['data']['heroStats']['winDay']
    
    # Map hero metadata: {hero_id: {'name': displayName, 'roles': 'CARRY, ESCAPE, ...'}}
    hero_meta = {}
    for hero in heroes_data:
        h_id = hero['id']
        name = hero['displayName']
        roles_list = [r['roleId'] for r in (hero.get('roles') or []) if r and 'roleId' in r]
        roles_str = ", ".join(roles_list)
        hero_meta[h_id] = {
            'name': name,
            'roles': roles_str
        }
    
    # Identify ONLY the most recent recorded day to prevent accumulating multi-day counts
    latest_day = max((stat['day'] for stat in stats_data if 'day' in stat), default=None)
    
    stats_map = {}
    for stat in stats_data:
        # Take ONLY records from the latest recorded day
        if latest_day is not None and stat.get('day') != latest_day:
            continue
            
        hero_id = stat['heroId']
        if hero_id in stats_map:
            continue
            
        match_count = stat.get('matchCount', 0)
        win_count = stat.get('winCount', 0)
        win_rate = round((win_count / match_count * 100), 2) if match_count > 0 else 0.0
        
        stats_map[hero_id] = {
            'match_count': match_count,
            'win_count': win_count,
            'win_rate': win_rate
        }
        
    return {
        'heroes': hero_meta,
        'stats': stats_map,
        'latest_day': latest_day
    }


def sync_hero_stats(db: Session) -> int:
    """
    Fetch latest data from STRATZ and upsert into Supabase.
    Guarantees exactly ONE up-to-date stat record per hero.
    """
    data = fetch_hero_stats()
    hero_meta = data['heroes']
    stats_map = data['stats']
    
    updated_count = 0
    
    for hero_id, meta in hero_meta.items():
        # 1. Upsert Hero with official roles
        hero = db.query(Hero).filter(Hero.id == hero_id).first()
        if hero:
            hero.name = meta['name']
            hero.roles = meta['roles']
        else:
            hero = Hero(id=hero_id, name=meta['name'], roles=meta['roles'])
            db.add(hero)
            
        # 2. Upsert HeroStat for the latest day
        if hero_id in stats_map:
            stat_data = stats_map[hero_id]
            stat = db.query(HeroStat).filter(HeroStat.hero_id == hero_id).first()
            if stat:
                stat.hero_name = meta['name']
                stat.match_count = stat_data['match_count']
                stat.win_count = stat_data['win_count']
                stat.win_rate = stat_data['win_rate']
                stat.recorded_at = func.now()
            else:
                stat = HeroStat(
                    hero_id=hero_id,
                    hero_name=meta['name'],
                    match_count=stat_data['match_count'],
                    win_count=stat_data['win_count'],
                    win_rate=stat_data['win_rate']
                )
                db.add(stat)
            updated_count += 1
            
    db.commit()
    return updated_count


def run_scraper_task() -> int:
    """Entrypoint that manages its own database session (for cron jobs or CLI)."""
    db = SessionLocal()
    try:
        return sync_hero_stats(db)
    finally:
        db.close()
