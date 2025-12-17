import pandas as pd
import requests
import time
import math
import os

# --- CONFIGURATION ---
INPUT_FILE = "nhl_approaching_milestones.csv" # Output from the scanner
OUTPUT_FILE = "nhl_milestone_projections.csv"
MILESTONE_STEP = 100
# ---------------------

def get_player_id(name):
    """Searches for a player ID using the NHL search API (Fallback)."""
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

def get_historical_lift(player_id, milestone_step):
    """Calculates if player performs better near milestones historically."""
    try:
        landing_url = f"https://api-web.nhle.com/v1/player/{player_id}/landing"
        r = requests.get(landing_url)
        if r.status_code != 200: return 0.0
        
        data = r.json()
        raw_seasons = data.get('seasonTotals', [])
        valid_seasons = sorted(list(set(str(s['season']) for s in raw_seasons if s.get('leagueAbbrev') == 'NHL')))
        
        all_logs = []
        for season_id in valid_seasons:
            log_url = f"https://api-web.nhle.com/v1/player/{player_id}/game-log/{season_id}/2"
            lr = requests.get(log_url)
            if lr.status_code == 200:
                games = lr.json().get('gameLog', [])
                for g in games:
                    all_logs.append({'GOALS': g.get('goals', 0)})
            time.sleep(0.1)

        if not all_logs: return 0.0

        df = pd.DataFrame(all_logs)
        # Calculate career total ENTERING the game
        df['CAREER_START'] = df['GOALS'].cumsum().shift(1).fillna(0)
        
        # Check performance within 2 goals of a milestone
        mask = (df['CAREER_START'] % milestone_step) >= (milestone_step - 2)
        
        milestone_avg = df[mask]['GOALS'].mean() if len(df[mask]) > 0 else 0
        career_avg = df['GOALS'].mean()
        
        if career_avg > 0:
            return ((milestone_avg - career_avg) / career_avg) * 100
        return 0.0
    except Exception:
        return 0.0

def analyze_candidates():
    if not os.path.exists(INPUT_FILE):
        print(f"Error: Could not find {INPUT_FILE}. Run the scanner script first.")
        return

    df_candidates = pd.read_csv(INPUT_FILE)
    print(f"Loaded {len(df_candidates)} candidates for deep analysis...")
    print("-" * 60)

    results = []

    for index, row in df_candidates.iterrows():
        name = row['Player']
        needed = row['Goals Needed']
        
        # --- FIX: Robust ID Check ---
        # If 'ID' column is missing or empty, look it up manually
        if 'ID' in row and pd.notna(row['ID']):
            pid = int(row['ID'])
        else:
            print(f"  [i] ID missing for {name}, looking it up...")
            pid = get_player_id(name)
            
        if not pid:
            print(f"Skipping {name} (No ID found)")
            continue
        
        print(f"Analyzing {name}...")

        try:
            # Get Current Stats (Season & Last 5)
            url = f"https://api-web.nhle.com/v1/player/{pid}/landing"
            r = requests.get(url)
            data = r.json()
            
            # 1. Season Stats
            current_season_goals = 0
            current_season_games = 0
            for season in data.get('seasonTotals', []):
                if str(season['season']) == "20242025" and season['leagueAbbrev'] == 'NHL':
                    current_season_goals = season.get('goals', 0)
                    current_season_games = season.get('gamesPlayed', 0)
            
            season_gpg = current_season_goals / current_season_games if current_season_games > 0 else 0
            
            # 2. Last 5 Games
            last_5 = data.get('last5Games', [])
            l5_goals = sum([g.get('goals', 0) for g in last_5])
            l5_gpg = l5_goals / len(last_5) if last_5 else 0.0
            
            # 3. Projections
            proj_season = math.ceil(needed / season_gpg) if season_gpg > 0 else 999
            proj_l5 = math.ceil(needed / l5_gpg) if l5_gpg > 0 else 999
            
            # 4. Historical Lift
            hist_lift = get_historical_lift(pid, MILESTONE_STEP)
            
            results.append({
                "Player": name,
                "Team": row['Team'],
                "Needs": needed,
                "Target": row['Target Milestone'],
                "Season Avg": round(season_gpg, 2),
                "Last 5 Avg": round(l5_gpg, 2),
                "Est Games (Season Pace)": proj_season if proj_season < 100 else "N/A",
                "Est Games (Hot/Cold Pace)": proj_l5 if proj_l5 < 100 else "N/A",
                "Hist. Lift %": f"{hist_lift:+.1f}%"
            })
            
        except Exception as e:
            print(f"Error on {name}: {e}")

    if results:
        final_df = pd.DataFrame(results)
        final_df = final_df.sort_values("Needs")
        
        print("\n" + "="*100)
        print(final_df.to_string(index=False))
        print("="*100)
        
        final_df.to_csv(OUTPUT_FILE, index=False)
        print(f"\nAnalysis saved to {OUTPUT_FILE}")

if __name__ == "__main__":
    analyze_candidates()