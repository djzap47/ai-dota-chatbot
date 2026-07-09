import os
import requests

STRATZ_API_URL = "https://api.stratz.com/graphql"

def get_headers():
    token = os.getenv("STRATZ_API_KEY")
    if not token:
        raise ValueError("STRATZ_API_KEY is not set in the environment variables.")
    return {
        "Authorization": f"Bearer {token}",
        "User-Agent": "STRATZ_API",
        "Content-Type": "application/json"
    }

def fetch_hero_stats():
    query = """
    query {
      constants {
        heroes {
          id
          displayName
        }
      }
      heroStats {
        winDay(bracketIds: [IMMORTAL]) {
          heroId
          winCount
          matchCount
        }
      }
    }
    """
    
    response = requests.post(STRATZ_API_URL, json={'query': query}, headers=get_headers())
    
    if response.status_code != 200:
        raise Exception(f"STRATZ API returned {response.status_code}: {response.text}")
        
    data = response.json()
    
    if 'errors' in data:
        raise Exception(f"STRATZ API Error: {data['errors']}")

    heroes_data = data['data']['constants']['heroes']
    stats_data = data['data']['heroStats']['winDay']
    
    hero_map = {hero['id']: hero['displayName'] for hero in heroes_data}
    
    results = []
    aggregated = {}
    
    for stat in stats_data:
        hero_id = stat['heroId']
        if hero_id not in aggregated:
            aggregated[hero_id] = {'winCount': 0, 'matchCount': 0}
        aggregated[hero_id]['winCount'] += stat['winCount']
        aggregated[hero_id]['matchCount'] += stat['matchCount']

    for hero_id, counts in aggregated.items():
        name = hero_map.get(hero_id, f"Unknown Hero {hero_id}")
        match_count = counts['matchCount']
        win_count = counts['winCount']
        win_rate = (win_count / match_count * 100) if match_count > 0 else 0.0
        
        results.append({
            'hero_id': hero_id,
            'hero_name': name,
            'match_count': match_count,
            'win_count': win_count,
            'win_rate': round(win_rate, 2)
        })
        
    return results
