import os
import time
import json
import requests
import random
import urllib.parse
import concurrent.futures
from datetime import datetime

# --- LOAD ENVIRONMENT VARIABLES ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- CONFIGURATION ---
STAT_TYPE = 'goals'         
MILESTONE_STEP = 100        
WITHIN_RANGE = 20           # Increased slightly to catch more players
MIN_CAREER_STAT = 80        
OUTPUT_FILE = "nhl_milestones.json"
MAX_WORKERS = 5 
API_KEY = os.environ.get('SCRAPERAPI_KEY', '')

TEAM_ABBREVIATIONS = [
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", 
    "WSH", "WPG"
]

def fetch_url(url, retries=1):
    """
    Attempts to fetch data using Proxy first, then Direct fallback.
    Includes simple retry logic for robustness.
    """
    for attempt in range(retries + 1):
        # 1. Try Proxy
        if API_KEY:
            try:
                encoded_url = urllib.parse.quote(url, safe='')
                proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={encoded_url}&keep_headers=true"
                r = requests.get(proxy_url, timeout=20)
                if r.status_code == 200: return r.json()
            except:
                pass

        # 2. Try Direct
        try:
            # Random sleep to avoid rate limits
            time.sleep(random.uniform(0.5, 1.5))
            r = requests.get(url, timeout=15)
            if r.status_code == 200: return r.json()
        except:
            pass
        
        # If we failed and have retries left, wait a bit before looping
        if attempt < retries:
            time.sleep(2)

    return None

def get_next_game_info(team_abbr):
    try:
        url = f"https://api-web.nhle.com/v1/club-schedule/{team_abbr}/week/now"
        data = fetch_url(url)
        if not data: return None
        
        games = data.get('games', [])
        for game in games:
            if game.get('gameState') in ['FUT', 'PRE']:
                is_home = (game.get('homeTeam', {}).get('abbrev') == team_abbr)
                opponent = game.get('awayTeam', {}).get('abbrev') if is_home else game.get('homeTeam', {}).get('abbrev')
                
                utc_str = game.get('startTimeUTC', '')
                try:
                    dt = datetime.strptime(utc_str, "%Y-%m-%dT%H:%M:%SZ")
                    friendly_date = dt.strftime("%a, %b %d @ %I:%M %p")
                except:
                    friendly_date = "Upcoming"

                return {
                    "opponent": opponent,
                    "date": friendly_date,
                    "is_home": is_home
                }
    except Exception:
        return None
    return None

def process_player(player_tuple):
    pid, name = player_tuple
    
    url = f"https://api-web.nhle.com/v1/player/{pid}/landing"
    data = fetch_url(url)
    
    if not data: return None
        
    try:
        career_totals = data.get('careerTotals', {}).get('regularSeason', {})
        career_val = career_totals.get(STAT_TYPE, 0)
        
        if career_val < MIN_CAREER_STAT: return None

        next_m = ((int(career_val) // MILESTONE_STEP) + 1) * MILESTONE_STEP
        needed = next_m - career_val
        
        if needed <= WITHIN_RANGE:
            img_url = data.get('headshot', '')
            if not img_url:
                img_url = f"https://cms.nhl.bamgrid.com/images/headshots/current/168x168/{pid}.jpg"
            
            # Stats
            last_5_games = data.get('last5Games', [])
            total_recent = sum(g.get(STAT_TYPE, 0) for g in last_5_games)
            last_5_avg = round(total_recent / 5, 1)
            
            season_totals = data.get('featuredStats', {}).get('regularSeason', {}).get('subSeason', {})
            games_played = season_totals.get('gamesPlayed', 1)
            season_goals = season_totals.get('goals', 0)
            season_avg = round(season_goals / games_played, 2) if games_played > 0 else 0

            team_abbr = data.get('currentTeamAbbrev', 'NHL')

            next_game = get_next_game_info(team_abbr)

            return {
                "player_name": name,
                "player_id": pid,
                "team": team_abbr,
                "current_stat": int(career_val),
                "target_milestone": next_m,
                "needed": int(needed),
                "image_url": img_url,
                "stat_type": STAT_TYPE,
                "season_avg": season_avg,
                "last_5_avg": last_5_avg,
                "next_game": next_game
            }
    except Exception:
        return None
        
    return None

def scan_nhl():
    print(f"--- NHL DUAL-MODE SCANNER ---")
    active_player_ids = set()
    candidates = []

    print("Fetching active rosters...")
    
    # Iterate through teams with explicit error reporting
    for i, team in enumerate(TEAM_ABBREVIATIONS):
        print(f"  [{i+1}/{len(TEAM_ABBREVIATIONS)}] Fetching {team}...", end='\r')
        
        url = f"https://api-web.nhle.com/v1/roster/{team}/current"
        
        # We use retries=2 here to be robust against roster failures
        data = fetch_url(url, retries=2)
        
        if data:
            for group in ['forwards', 'defensemen', 'goalies']:
                for player in data.get(group, []):
                    full_name = f"{player['firstName']['default']} {player['lastName']['default']}"
                    active_player_ids.add((player['id'], full_name))
        else:
            # CRITICAL: Now we know if a team failed
            print(f"\n  [X] FAILED to load roster for {team} (Skipping players from this team)")

    print(f"\nFound {len(active_player_ids)} active players.")
    player_list = list(active_player_ids)
    print(f"Scanning {len(player_list)} players...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_player = {executor.submit(process_player, p): p for p in player_list}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_player):
            completed += 1
            if completed % 25 == 0: print(f"  Progress: {completed}/{len(player_list)}...", end='\r')
            
            result = future.result()
            if result:
                print(f"\n    [!] ALERT: {result['player_name']} needs {result['needed']}")
                candidates.append(result)

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(candidates, f, indent=4)
    print(f"\nSaved {len(candidates)} NHL candidates.")

if __name__ == "__main__":
    scan_nhl()