import requests
import pandas as pd
import time
import json

# --- CONFIGURATION ---
STAT_TYPE = 'goals'         # OPTIONS: 'goals', 'points', 'assists'
MILESTONE_STEP = 100        # Increment (e.g., 100 goals, 1000 points)
WITHIN_RANGE = 15           # Alert if within this range
MIN_CAREER_STAT = 80        # Filter out rookies
OUTPUT_FILE = "nhl_milestones.json"

# --- CRITICAL FIX: INCREASE DELAY ---
# Match NBA stability time
SLEEP_TIME = 1.0 # Pause for 1.0 seconds between each player check
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
            # NOTE: NHL API often does not require custom headers, but we add a short sleep
            time.sleep(0.1) 
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
    
    # Expected runtime for NHL: ~700 players * 1.0 sec = 700 seconds (approx 11.6 minutes total)
    print(f"Expected scan time: Approx. {len(player_list) * SLEEP_TIME / 60:.1f} minutes.")

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
                    time.sleep(SLEEP_TIME)
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
            
            # Polite Rate Limiting
            time.sleep(SLEEP_TIME)
            
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
