import requests
import pandas as pd
import os
import time
import math

# --- CONFIGURATION ---
PLAYERS_FILE = 'nhl_players.txt'
CACHE_DIR = 'nhl_cache'
OUTPUT_FILE = "nhl_milestone_summary.csv"
MILESTONE_INTERVAL = 100  # Check for every 100 goals
APPROACH_RANGE = 2        # "Approaching" means starting within 2 goals
# ---------------------

if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

def get_player_id(name):
    """Searches for a player ID using the NHL search API."""
    url = "https://search.d3.nhle.com/api/v1/search/player"
    params = {"culture": "en-us", "limit": 20, "q": name}
    try:
        r = requests.get(url, params=params)
        results = r.json()
        for player in results:
            if player['name'].lower() == name.lower():
                return player['playerId']
        if results:
            return results[0]['playerId']
    except Exception as e:
        print(f"Error searching for {name}: {e}")
    return None

def fetch_career_logs(player_id, player_name):
    """
    Fetches game logs for every season in a player's career.
    Checks for a local CSV first to avoid re-downloading.
    """
    # 1. Check Cache
    slug = player_name.lower().replace(' ', '_')
    csv_path = os.path.join(CACHE_DIR, f"{slug}.csv")
    
    if os.path.exists(csv_path):
        print(f"Found cached data for {player_name}...")
        df = pd.read_csv(csv_path)
        df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'])
        return df

    # 2. Fetch from API if not cached
    landing_url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
    r = requests.get(landing_url)
    if r.status_code != 200:
        return None
    
    data = r.json()
    raw_seasons = data.get('seasonTotals', [])
    
    valid_season_ids = set()
    for season in raw_seasons:
        league = season.get('leagueAbbrev')
        season_id = str(season['season'])
        if league == 'NHL':
            valid_season_ids.add(season_id)

    sorted_seasons = sorted(list(valid_season_ids))
    print(f"Fetching logs for {player_name} ({len(sorted_seasons)} NHL seasons)...")
    
    all_logs = []
    
    for season_id in sorted_seasons:
        log_url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/{season_id}/2"
        lr = requests.get(log_url)
        
        if lr.status_code == 200:
            log_data = lr.json()
            games = log_data.get('gameLog', [])
            for g in games:
                row = {
                    'GAME_DATE': g.get('gameDate'),
                    'GOALS': g.get('goals', 0),
                    'ASSISTS': g.get('assists', 0),
                    'POINTS': g.get('points', 0),
                    'OPPONENT': g.get('opponentAbbrev')
                }
                all_logs.append(row)
        
        time.sleep(0.2) 

    if not all_logs:
        return pd.DataFrame()

    df = pd.DataFrame(all_logs)
    df['GAME_DATE'] = pd.to_datetime(df['GAME_DATE'])
    df = df.sort_values('GAME_DATE', ascending=True).reset_index(drop=True)
    
    # 3. Save to Cache
    df.to_csv(csv_path, index=False)
    return df

def analyze_milestones(df, player_name):
    """
    Calculates stats and returns a summary dictionary.
    """
    try:
        # Calculate Career Goals ENTERING the game
        df['CAREER_GOALS_START'] = df['GOALS'].cumsum().shift(1).fillna(0)
        
        # Logic: (Start % 100) >= (100 - Approach)
        milestone_mask = (df['CAREER_GOALS_START'] % MILESTONE_INTERVAL) >= (MILESTONE_INTERVAL - APPROACH_RANGE)
        
        milestone_games = df[milestone_mask]
        
        num_games = len(milestone_games)
        career_avg = df['GOALS'].mean()
        
        if num_games > 0:
            milestone_avg = milestone_games['GOALS'].mean()
            diff = milestone_avg - career_avg
            pct_diff = (diff / career_avg) * 100 if career_avg > 0 else 0.0
        else:
            milestone_avg = 0
            diff = 0
            pct_diff = 0

        print(f"  > {player_name}: Career {career_avg:.2f} vs Milestone {milestone_avg:.2f} ({pct_diff:+.1f}%)")

        return {
            'Player': player_name,
            'Milestone Games': num_games,
            'Milestone Avg': round(milestone_avg, 3),
            'Career Avg': round(career_avg, 3),
            'Diff': round(diff, 3),
            'Pct Diff': round(pct_diff, 2)
        }

    except Exception as e:
        print(f"Error analyzing {player_name}: {e}")
        return None

# --- MAIN EXECUTION ---
if __name__ == "__main__":
    if not os.path.exists(PLAYERS_FILE):
        with open(PLAYERS_FILE, 'w') as f:
            f.write("Alexander Ovechkin\nSidney Crosby\n")
        print(f"Created {PLAYERS_FILE}. Please add players and run again.")
        exit()

    print(f"Reading {PLAYERS_FILE}...")
    
    results = []
    
    with open(PLAYERS_FILE, 'r') as f:
        players = [line.strip() for line in f if line.strip()]

    for name in players:
        pid = get_player_id(name)
        if pid:
            df = fetch_career_logs(pid, name)
            if not df.empty:
                result_row = analyze_milestones(df, name)
                if result_row:
                    results.append(result_row)
            else:
                print(f"  No games found for {name}")
        else:
            print(f"  Player ID not found for {name}")

    # Export to CSV with Safe Save
    if results:
        summary_df = pd.DataFrame(results)
        summary_df = summary_df.sort_values('Pct Diff', ascending=False)
        
        while True:
            try:
                summary_df.to_csv(OUTPUT_FILE, index=False)
                break 
            except PermissionError:
                print(f"\n[ERROR] Could not save to {OUTPUT_FILE} because it is open.")
                input("Please close the file in Excel and press ENTER to try again...")
        
        full_path = os.path.abspath(OUTPUT_FILE)
        print(f"\nSUCCESS! Results saved to:\n  {full_path}")

        print("\n" + "="*80)
        print(f"SUMMARY (Sorted by % Increase)")
        print("="*80)
        print(summary_df.to_string(index=False))
    else:
        print("\nNo results to save.")