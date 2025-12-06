import requests
import pandas as pd
import time
import json
import random # Added for randomized sleep intervals

# --- CONFIGURATION ---
STAT_TYPE = 'goals'         # OPTIONS: 'goals', 'points', 'assists'
MILESTONE_STEP = 100        # Increment (e.g., 100 goals, 1000 points)
WITHIN_RANGE = 15           # Alert if within this range
MIN_CAREER_STAT = 80        # Filter out rookies
OUTPUT_FILE = "nhl_milestones.json"

# --- CRITICAL FIX: INCREASE DELAY & RANDOMIZE ---
# Increased to 1.2s baseline + random jitter (0.1 to 0.5s) to bypass rate limits
SLEEP_TIME = 1.2 
# ---------------------

TEAM_ABBREVIATIONS = [
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", 
    "WSH", "WPG"
]

def scan_nhl_active_players():
    print(f"--- NHL MILESTONE SCANNER (JSON MODE) ---")
    print(f"Target: Players within {WITHIN_RANGE} {STAT_TYPE} of a {MILESTONE_STEP} {STAT_TYPE} mark.")
    
    active_player_ids = set()
    candidates = []

    # 1. Build Roster List
    print("Fetching active rosters...")
    for team in TEAM_ABBREVIATIONS:
        try:
            url = f"https://api-web.nhle.com/v1/roster/{team}/current"
            # Increased sleep time for roster fetch, which happens in quick succession
            time.sleep(0.5) 
            r = requests.get(url)
            if r.status_code == 200:
                data = r.json()
                for group in ['forwards', 'defensemen', 'goalies']:
                    for player in data.get(group, []):
                        full_name = player['firstName']['default'] + " " + player['lastName']['default']
                        active_player_ids.add((player['id'], full_name))
        except Exception:
            pass
            
    print(f"Found {len(active_player_ids)} active players. Starting scan...")
    
    player_list = list(active_player_ids)
    
    # Expected runtime will increase slightly with the longer sleep time
    expected_time = len(player_list) * SLEEP_TIME / 60
    print(f"Expected scan time: Approx. {expected_time:.1f} minutes.")

    for i, (pid, name) in enumerate(player_list):
        if i % 50 == 0:
            print(f"  Scanning... {i}/{len(player_list)} ({name})")
            
        try:
            url = f"https://api-web.nhle.com/v1/player/{pid}/landing"
            r = requests.get(url)
            
            if r.status_code == 200:
                data = r.json()
                
                # Use official Career Totals
                career_totals = data.get('careerTotals', {}).get('regularSeason', {})
                
                career_val = career_totals.get(STAT_TYPE, 0)
                
                if career_val < MIN_CAREER_STAT:
                    # Add jitter for low-stat players too
                    time.sleep(SLEEP_TIME + random.uniform(0.1, 0.5))
                    continue

                next_milestone = ((int(career_val) // MILESTONE_STEP) + 1) * MILESTONE_STEP
                needed = next_milestone - career_val
                
                if needed <= WITHIN_RANGE:
                    print(f"  [!] MATCH: {name}")
                    
                    candidates.append({
                        "player_name": name,
                        "team": data.get('currentTeamAbbrev', 'N/A'),
                        "current_stat": int(career_val),
                        "target_milestone": next_milestone,
                        "needed": int(needed),
                        "stat_type": STAT_TYPE
                    })
            
            # Polite Rate Limiting with Jitter
            time.sleep(SLEEP_TIME + random.uniform(0.1, 0.5))
            
        except Exception as e:
            # If any specific player fails, log the error and take a long nap
            print(f"CRITICAL API FAILURE for {name}. Taking a 30 second nap...")
            time.sleep(30)
            continue


    # Save to JSON
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
    scan_nhl_active_players()
