import time
import pandas as pd
import json
import random 
from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats, commonplayerinfo
from nba_api.stats.library.http import NBAStatsHTTP

# --- CONFIGURATION ---
MILESTONE_STEP = 1000       
WITHIN_POINTS = 250         
MIN_CAREER_PTS = 3000       
OUTPUT_FILE = "nba_milestones.json"
# ---------------------

# Trick the API into thinking we are a browser 
NBAStatsHTTP.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
})

def api_call_with_retry(endpoint_class, **kwargs):
    """Executes API call with exponential backoff for robustness."""
    max_retries = 3
    delay = 2  # Start with 2 seconds delay
    
    for attempt in range(max_retries):
        try:
            time.sleep(random.uniform(0.1, 0.5)) # Jitter before the attempt
            endpoint = endpoint_class(**kwargs)
            return endpoint.get_data_frames()
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"    [!] API Timeout/Error (Attempt {attempt + 1}). Retrying in {delay}s...")
                time.sleep(delay)
                delay *= 2  # Exponential backoff: 2s, 4s, 8s
            else:
                raise e # Raise the last error

def get_team_abbrev(player_id):
    """Fetches the current team for a player (only called for candidates)."""
    try:
        # We now rely on the internal API call retry logic, so no external sleep needed here
        info_data = api_call_with_retry(commonplayerinfo.CommonPlayerInfo, player_id=player_id)
        if info_data:
            return info_data[0]['TEAM_ABBREVIATION'].iloc[0]
        return "N/A"
    except:
        return "N/A"

def scan_nba_active_players():
    print(f"--- NBA MILESTONE SCANNER (JSON MODE) ---")
    print(f"Target: Players within {WITHIN_POINTS} pts of a {MILESTONE_STEP} pt mark.")
    
    # 1. Get all active players
    print("Fetching active player list...")
    active_players = players.get_active_players()
    print(f"Found {len(active_players)} active players. Starting scan...")
    
    player_list = active_players
    
    # Estimate run time based on max 3 retries (3 attempts * 500 players * ~2s base delay)
    # This estimate is complex, so let's provide a rough benchmark
    print(f"Estimated time: This will be highly variable but should be under 20 minutes.")

    candidates = []
    
    # 2. Loop through players
    for i, p in enumerate(player_list):
        pid = p['id']
        name = p['full_name']
        
        if i % 20 == 0:
            print(f"\n  Scanning... {i}/{len(player_list)} ({name})")

        try:
            # Fetch Career Stats using resilient call
            career_data = api_call_with_retry(playercareerstats.PlayerCareerStats, player_id=pid)
            df = career_data[0]
            
            total_points = df['PTS'].sum()
            
            if total_points < MIN_CAREER_PTS:
                continue

            # 3. Check Math
            next_milestone = ((int(total_points) // MILESTONE_STEP) + 1) * MILESTONE_STEP
            needed = next_milestone - total_points
            
            if needed <= WITHIN_POINTS:
                print(f"  [!] MATCH: {name} (Needs {int(needed)})")
                
                # Fetch team only for matches
                team = get_team_abbrev(pid)
                
                candidates.append({
                    "player_name": name,
                    "team": team,
                    "current_stat": int(total_points),
                    "target_milestone": next_milestone,
                    "needed": int(needed),
                    "stat_type": "points"
                })

        except Exception as e:
            # If all retries fail, skip the player entirely and move on quickly
            print(f"  [X] Failed all retries for {name}. Skipping.")
            continue


    # 4. Save to JSON
    if candidates:
        candidates.sort(key=lambda x: x['needed'])
        
        with open(OUTPUT_FILE, 'w') as f:
            json.dump(candidates, f, indent=4)
        print(f"\n[SUCCESS] Saved {len(candidates)} players to '{OUTPUT_FILE}'")
    else:
        print("No players found within range.")
        with open(OUTPUT_FILE, 'w') as f:
            json.dump([], f)

if __name__ == "__main__":
    scan_nba_active_players()
