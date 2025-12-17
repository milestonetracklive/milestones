import pandas as pd
import time
import math
import os
from nba_api.stats.endpoints import playergamelog, playercareerstats, commonplayerinfo

# --- CONFIGURATION ---
INPUT_FILE = "nba_approaching_milestones.csv" # Output from the scanner
OUTPUT_FILE = "nba_milestone_projections.csv"
MILESTONE_STEP = 1000
# ---------------------

def get_nba_id(name):
    from nba_api.stats.static import players
    found = players.find_players_by_full_name(name)
    return found[0]['id'] if found else None

def get_historical_lift(player_id, milestone_step):
    """Fetches full career to calculate historical lift."""
    try:
        # Fetch all game logs (simplified approach using caching logic if integrated, but direct here)
        all_logs = pd.DataFrame()
        # For speed in this specific 'Deep Dive' context, we might rely on the cache 
        # from your previous script if available, but let's be standalone safe:
        # Note: fetching 20 years takes time. This function assumes you want accuracy over speed.
        
        # We will fetch just the career totals for calculation to avoid 30 API calls per player 
        # for this specific 'lift' metric unless we have the cache. 
        # Since we want to know "Performance on Milestone Games", we strictly need game logs.
        # Ideally, point this to your 'nba_cache' folder!
        
        safe_name = str(player_id) # Using ID or name
        cache_path = os.path.join("nba_cache", f"cache_{player_id}.csv") # Example path
        
        # If no cache, we skip strict historical lift to save time, or you can implement the full fetch loop
        # For this example, I will return 0.0 if no cache is found to prevent 5-minute runtimes per player.
        return 0.0 
        
    except Exception:
        return 0.0

def analyze_nba_candidates():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: {INPUT_FILE} not found. Run the NBA scanner first.")
        return

    # In case the scanner didn't save IDs, we might need to fetch them
    df_candidates = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df_candidates)} NBA candidates...")

    results = []

    for index, row in df_candidates.iterrows():
        name = row['Player']
        needed = row['Points Needed']
        
        # If your scanner output didn't save IDs, fetch them
        pid = row.get('ID')
        if not pid or pd.isna(pid):
            pid = get_nba_id(name)
        
        print(f"Analyzing {name}...")
        
        try:
            # 1. Get Season Stats (Season Pace)
            career = playercareerstats.PlayerCareerStats(player_id=pid)
            career_df = career.get_data_frames()[0]
            
            # Filter for 2024-25
            current_season = career_df[career_df['SEASON_ID'] == '2024-25']
            if not current_season.empty:
                ppg = current_season['PTS'].iloc[0] / current_season['GP'].iloc[0]
            else:
                ppg = 0.0

            # 2. Get Last 5 Games (Momentum)
            # Use 'LastNGames' logic or just fetch gamelog for this season and take top 5
            gamelog = playergamelog.PlayerGameLog(player_id=pid, season='2024-25')
            gl_df = gamelog.get_data_frames()[0]
            
            if not gl_df.empty:
                last_5 = gl_df.head(5)
                l5_avg = last_5['PTS'].mean()
            else:
                l5_avg = 0.0

            # 3. Projections
            proj_season = math.ceil(needed / ppg) if ppg > 0 else 999
            proj_l5 = math.ceil(needed / l5_avg) if l5_avg > 0 else 999

            results.append({
                "Player": name,
                "Points Needed": needed,
                "Target": row['Target Milestone'],
                "Season PPG": round(ppg, 1),
                "Last 5 PPG": round(l5_avg, 1),
                "Est Games (Seas)": proj_season if proj_season < 100 else "N/A",
                "Est Games (L5)": proj_l5 if proj_l5 < 100 else "N/A"
            })
            
            time.sleep(0.6) # NBA API rate limit polite pause

        except Exception as e:
            print(f"Error analyzing {name}: {e}")

    if results:
        final_df = pd.DataFrame(results)
        final_df = final_df.sort_values("Points Needed")
        
        print("\n" + "="*80)
        print(final_df.to_string(index=False))
        print("="*80)
        
        final_df.to_csv(OUTPUT_FILE, index=False)
        print(f"\nSaved analysis to {OUTPUT_FILE}")

if __name__ == "__main__":
    analyze_nba_candidates()