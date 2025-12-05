import requests
import pandas as pd
import time

# --- CONFIGURATION ---
STAT_TYPE = 'goals'         # OPTIONS: 'goals', 'points', 'assists'
MILESTONE_STEP = 100        # Increment (e.g., 100 goals, 1000 points)
WITHIN_RANGE = 15           # Alert if within this range
MIN_CAREER_STAT = 80        # Filter out rookies
OUTPUT_FILE = "nhl_approaching_milestones.csv"
# ---------------------

TEAM_ABBREVIATIONS = [
    "ANA", "BOS", "BUF", "CGY", "CAR", "CHI", "COL", "CBJ", "DAL", "DET",
    "EDM", "FLA", "LAK", "MIN", "MTL", "NSH", "NJD", "NYI", "NYR", "OTT",
    "PHI", "PIT", "SJS", "SEA", "STL", "TBL", "TOR", "UTA", "VAN", "VGK", 
    "WSH", "WPG"
]

def scan_nhl_active_players():
    print(f"--- NHL MILESTONE SCANNER ---")
    print(f"Target: Players within {WITHIN_RANGE} {STAT_TYPE} of a {MILESTONE_STEP} {STAT_TYPE} mark.")
    
    active_player_ids = set()
    candidates = []

    # 1. Build Roster List
    print("Fetching active rosters...")
    for team in TEAM_ABBREVIATIONS:
        try:
            url = f"https://api-web.nhle.com/v1/roster/{team}/current"
            r = requests.get(url)
            if r.status_code == 200:
                data = r.json()
                for group in ['forwards', 'defensemen', 'goalies']:
                    for player in data.get(group, []):
                        full_name = player['firstName']['default'] + " " + player['lastName']['default']
                        active_player_ids.add((player['id'], full_name))
            else:
                print(f"  [!] Warning: Failed to fetch roster for {team} (Status: {r.status_code})")
        except Exception as e:
            print(f"  [!] Error fetching {team}: {e}")
            
    print(f"Found {len(active_player_ids)} active players. Fetching career stats...")
    
    player_list = list(active_player_ids)
    
    for i, (pid, name) in enumerate(player_list):
        if i % 50 == 0:
            print(f"  Scanning... {i}/{len(player_list)}")
            
        try:
            url = f"https://api-web.nhle.com/v1/player/{pid}/landing"
            r = requests.get(url)
            
            if r.status_code == 200:
                data = r.json()
                
                # --- FIX: Use official Career Totals first ---
                # This avoids errors in manual summing of seasons
                career_totals = data.get('careerTotals', {}).get('regularSeason', {})
                
                if career_totals and STAT_TYPE in career_totals:
                    career_val = career_totals.get(STAT_TYPE, 0)
                    check_points = career_totals.get('points', 0)
                else:
                    # Fallback to manual sum if career object is missing
                    season_totals = data.get('seasonTotals', [])
                    career_val = 0
                    check_points = 0
                    for season in season_totals:
                        if season.get('leagueAbbrev') == 'NHL' and season.get('gameTypeId') == 2:
                            career_val += season.get(STAT_TYPE, 0)
                            check_points += season.get('points', 0)
                
                if career_val < MIN_CAREER_STAT:
                    continue

                # Check Math
                next_milestone = ((int(career_val) // MILESTONE_STEP) + 1) * MILESTONE_STEP
                needed = next_milestone - career_val
                
                if needed <= WITHIN_RANGE:
                    print(f"  [!] {name}: {int(career_val)} {STAT_TYPE} (Needs {int(needed)})")
                    
                    candidates.append({
                        "Player": name,
                        "ID": pid,
                        "Team": data.get('currentTeamAbbrev', 'N/A'),
                        f"Current {STAT_TYPE.title()}": int(career_val),
                        "Target Milestone": next_milestone,
                        f"{STAT_TYPE.title()} Needed": int(needed),
                        "Verification (Total Pts)": int(check_points)
                    })
            
            time.sleep(0.05)
            
        except Exception:
            pass

    # Output Results
    print("\n" + "="*80)
    print(f"RESULTS: Players Approaching {MILESTONE_STEP}-{STAT_TYPE.title()} Milestones")
    print("="*80)
    
    if candidates:
        df_results = pd.DataFrame(candidates)
        sort_col = f"{STAT_TYPE.title()} Needed"
        df_results = df_results.sort_values(sort_col)
        
        # Display key columns
        cols = ["Player", sort_col, f"Current {STAT_TYPE.title()}", "Target Milestone", "Verification (Total Pts)"]
        print(df_results[cols].to_string(index=False))
        
        df_results.to_csv(OUTPUT_FILE, index=False)
        print(f"\nSaved list to '{OUTPUT_FILE}'")
    else:
        print("No players found within range.")

if __name__ == "__main__":
    scan_nhl_active_players()