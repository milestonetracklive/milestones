import time
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats

# --- CONFIGURATION ---
MILESTONE_STEP = 1000       # Look for 1k, 5k, 10k, 25k etc.
WITHIN_POINTS = 200         # Alert if they are this close
MIN_CAREER_PTS = 3000       # Skip rookies/bench players to speed up scan
# ---------------------

def scan_nba_active_players():
    print(f"--- NBA MILESTONE SCANNER ---")
    print(f"Target: Players within {WITHIN_POINTS} pts of a {MILESTONE_STEP} pt mark.")
    print("Fetching active player list...")

    # 1. Get all active players
    active_players = players.get_active_players()
    print(f"Found {len(active_players)} active players. Starting scan...")
    print("(This takes 2-3 minutes due to API rate limits)\n")

    candidates = []
    
    # 2. Loop through players
    for i, p in enumerate(active_players):
        pid = p['id']
        name = p['full_name']
        
        # Simple progress indicator
        if i % 10 == 0:
            print(f"  Scanning... {i}/{len(active_players)} ({name})")

        try:
            # Fetch Career Stats
            career = playercareerstats.PlayerCareerStats(player_id=pid)
            df = career.get_data_frames()[0]
            
            # Sum up points (Regular Season is usually row 0, but summing is safer)
            # The API returns specific rows for teams, so we sum the 'PTS' column
            total_points = df['PTS'].sum()
            
            # Optimization: Skip players who are just starting out
            if total_points < MIN_CAREER_PTS:
                time.sleep(0.35) # Short sleep
                continue

            # 3. Check Math
            next_milestone = ((int(total_points) // MILESTONE_STEP) + 1) * MILESTONE_STEP
            needed = next_milestone - total_points
            
            if needed <= WITHIN_POINTS:
                print(f"  [!] MATCH: {name} is {int(needed)} pts away from {next_milestone}!")
                candidates.append({
                    "Player": name,
                    "Current Points": int(total_points),
                    "Target Milestone": next_milestone,
                    "Points Needed": int(needed)
                })

            # Polite Rate Limiting (Crucial for 500+ requests)
            time.sleep(0.60)

        except Exception as e:
            # print(f"Error scanning {name}: {e}")
            pass

    # 4. Output Results
    print("\n" + "="*60)
    print(f"RESULTS: Players Approaching {MILESTONE_STEP}k Milestones")
    print("="*60)
    
    if candidates:
        df_results = pd.DataFrame(candidates)
        df_results = df_results.sort_values("Points Needed")
        print(df_results.to_string(index=False))
        
        # Save to file
        df_results.to_csv("nba_approaching_milestones.csv", index=False)
        print("\nSaved list to 'nba_approaching_milestones.csv'")
    else:
        print("No players found within range.")

if __name__ == "__main__":
    scan_nba_active_players()