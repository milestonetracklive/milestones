import time
import os
import pandas as pd
from nba_api.stats.static import players
from nba_api.stats.endpoints import playergamelog

# --- CONFIGURATION ---
PLAYER_FILE = "players.txt"
MILESTONE_STEP = 500        # Check every 500 points
OUTPUT_FILE = "nba_milestone_results.csv"
START_YEAR = 1985           # Catch older players
CACHE_DIR = "nba_cache"     # Folder to store CSVs
# ---------------------

# Ensure the cache directory exists
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def load_player_list(filename):
    """
    Reads a list of players from a text file.
    Returns a default list if the file is not found.
    """
    if os.path.exists(filename):
        with open(filename, 'r') as f:
            player_list = [line.strip() for line in f if line.strip()]
        
        print(f"Loaded {len(player_list)} players from {filename}")
        return player_list
    else:
        print(f"[WARNING] {filename} not found.")
        return ["LeBron James", "Stephen Curry"]

def get_player_id(name):
    """Finds the unique ID for a player name."""
    nba_players = players.get_players()
    found_player = [p for p in nba_players if p['full_name'].lower() == name.lower()]
    
    if not found_player:
        # fuzzy match check could go here, but strict for now
        print(f"Error: Player {name} not found.")
        return None
    return found_player[0]['id']

def fetch_career_games(player_id, player_name):
    """
    Fetches all game logs for a player.
    Checks for a local CSV in the CACHE_DIR first to avoid re-downloading.
    """
    # Create a filename for this player (e.g., "nba_cache/cache_lebron_james.csv")
    safe_name = player_name.replace(" ", "_").lower()
    filename = f"cache_{safe_name}.csv"
    cache_file_path = os.path.join(CACHE_DIR, filename)

    # 1. Check if we already have the data locally
    if os.path.exists(cache_file_path):
        print(f"\nFound cached data for {player_name}. Loading from file...")
        try:
            df = pd.read_csv(cache_file_path)
            df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'])
            return df
        except Exception as e:
            print(f"Error reading cache for {player_name}: {e}. Will redownload.")

    # 2. If no local file, download it
    print(f"\nFetching data for {player_name} (ID: {player_id}) from API...")
    
    all_games = []
    # Loop from START_YEAR to present. 
    for year in range(START_YEAR, 2025):
        season_str = f"{year}-{str(year+1)[-2:]}" 
        try:
            # Politeness delay
            time.sleep(0.6) 
            gamelog = playergamelog.PlayerGameLog(player_id=player_id, season=season_str)
            df = gamelog.get_data_frames()[0]
            if not df.empty:
                all_games.append(df)
                print(f"  Loaded {season_str} season")
        except Exception as e:
            pass # Skip errors for seasons they didn't play

    if not all_games:
        return pd.DataFrame() 

    full_career = pd.concat(all_games)
    # Fix date parsing with mixed format support
    full_career['GAME_DATE'] = pd.to_datetime(full_career['GAME_DATE'], format='mixed')    
    full_career = full_career.sort_values(by='GAME_DATE', ascending=True)
    
    # 3. Save the downloaded data to the cache folder
    full_career.to_csv(cache_file_path, index=False)
    print(f"  > Saved data to {cache_file_path} for future runs.")
    
    return full_career

def analyze_milestones(df, player_name):
    """
    Calculates stats and returns a summary dictionary.
    """
    # Calculate cumulative points entering the game
    # cumsum() is total AFTER the game. We usually want total BEFORE to see if they are approaching.
    # However, keeping your original logic of identifying the specific game they crossed/hit it:
    df['CAREER_PTS'] = df['PTS'].cumsum()
    
    milestone_games_pts = []
    current_target = MILESTONE_STEP
    
    # Identify milestone games
    for index, row in df.iterrows():
        # Check if they crossed the milestone OR landed exactly on it
        if row['CAREER_PTS'] >= current_target:
            milestone_games_pts.append(row['PTS'])
            current_target = ((row['CAREER_PTS'] // MILESTONE_STEP) + 1) * MILESTONE_STEP

    # Calculate statistics
    career_avg = df['PTS'].mean()
    
    if milestone_games_pts:
        milestone_avg = sum(milestone_games_pts) / len(milestone_games_pts)
        diff = milestone_avg - career_avg
        pct_diff = (diff / career_avg) * 100 if career_avg > 0 else 0.0
    else:
        milestone_avg = 0
        diff = 0
        pct_diff = 0

    # Print a quick summary to the console
    print(f"  > {player_name}: Career Avg {career_avg:.1f} vs Milestone Avg {milestone_avg:.1f} ({pct_diff:+.1f}%)")

    return {
        "Player": player_name,
        "Milestone Step": MILESTONE_STEP,
        "Total Games": len(df),
        "Milestone Games": len(milestone_games_pts),
        "Career Average": round(career_avg, 2),
        "Milestone Average": round(milestone_avg, 2),
        "Difference": round(diff, 2),
        "Pct Diff": round(pct_diff, 2)
    }

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    all_player_results = []

    # LOAD PLAYERS FROM FILE
    target_players = load_player_list(PLAYER_FILE)

    for player_name in target_players:
        pid = get_player_id(player_name)
        if pid:
            df = fetch_career_games(pid, player_name)
            if not df.empty:
                result_row = analyze_milestones(df, player_name)
                all_player_results.append(result_row)
            else:
                print(f"  No games found for {player_name}")
    
    # Export to Spreadsheet (CSV) with Safe Save
    if all_player_results:
        results_df = pd.DataFrame(all_player_results)
        # Sort by Pct Diff to see who steps up the most
        results_df = results_df.sort_values(by="Pct Diff", ascending=False)
        
        while True:
            try:
                results_df.to_csv(OUTPUT_FILE, index=False)
                break 
            except PermissionError:
                print(f"\n[ERROR] Could not save to {OUTPUT_FILE} because it is open.")
                input("Please close the file in Excel and press ENTER to try again...")
        
        full_path = os.path.abspath(OUTPUT_FILE)
        print(f"\nSUCCESS! Results saved to:\n  {full_path}")

        print("\n--- SUMMARY TABLE ---")
        print(results_df[['Player', 'Career Average', 'Milestone Average', 'Difference', 'Pct Diff']].to_string(index=False))
    else:
        print("\nNo results to save.")