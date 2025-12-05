import time
import pandas as pd
import json
from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats, commonplayerinfo

# --- CONFIGURATION ---
MILESTONE_STEP = 1000       # Look for 1k, 5k, 10k, 25k etc.
WITHIN_POINTS = 250         # Alert if they are this close
MIN_CAREER_PTS = 3000       # Skip rookies/bench players to speed up scan
OUTPUT_FILE = "nba_milestones.json"
# ---------------------

def get_team_abbrev(player_id):
    """Fetches the current team for a player (only called for candidates)."""
    try:
        info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        df = info.get_data_frames()[0]
        return df['TEAM_ABBREVIATION'].iloc[0]
    except:
        return "N/A"

def scan_nba_active_players():
    print(f"--- NBA MILESTONE SCANNER (JSON MODE) ---")
    print(f"Target: Players within {WITHIN_POINTS} pts of a {MILESTONE_STEP} pt mark.")
    
    # 1. Get all active players
    print("Fetching active player list...")
    active_players = players.get_active_players()
    print(f"Found {len(active_players)} active players. Starting scan...")
    print("(This takes a few minutes due to API rate limits)\n")

    candidates = []
    
    # 2. Loop through players
    for i, p in enumerate(active_players):
        pid = p['id']
        name = p['full_name']
        
        # Progress indicator every 20 players
        if i % 20 == 0:
            print(f"  Scanning... {i}/{len(active_players)}")

        try:
            # Fetch Career Stats
            career = playercareerstats.PlayerCareerStats(player_id=pid)
            df = career.get_data_frames()[0]
            
            # Sum points (safest way to get true total)
            total_points = df['PTS'].sum()
            
            # Optimization: Skip players who aren't close to min threshold
            if total_points < MIN_CAREER_PTS:
                time.sleep(0.3) # Short sleep
                continue

            # 3. Check Math
            next_milestone = ((int(total_points) // MILESTONE_STEP) + 1) * MILESTONE_STEP
            needed = next_milestone - total_points
            
            if needed <= WITHIN_POINTS:
                print(f"  [!] MATCH: {name} (Needs {int(needed)})")
                
                # Fetch team only for matches to save API calls
                team = get_team_abbrev(pid)
                
                candidates.append({
                    "player_name": name,
                    "team": team,
                    "current_stat": int(total_points),
                    "target_milestone": next_milestone,
                    "needed": int(needed),
                    "stat_type": "points"
                })

            # Polite Rate Limiting
            time.sleep(0.60)

        except Exception:
            pass

    # 4. Save to JSON
    if candidates:
        # Sort by proximity
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