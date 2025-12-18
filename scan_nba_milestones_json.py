import os
import time
import json
import requests
import random
import urllib.parse 
import concurrent.futures
from nba_api.stats.static import players 
from nba_api.stats.endpoints import playergamelog

# --- LOAD ENVIRONMENT VARIABLES ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# --- CONFIG ---
MILESTONE_STEP = 1000
WITHIN_POINTS = 250 
OUTPUT_FILE = "nba_milestones.json"
MAX_WORKERS = 5  
API_KEY = os.environ.get('SCRAPERAPI_KEY', '')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
    "Connection": "keep-alive"
}

def fetch_url(url):
    """
    Attempts to fetch data using Proxy first, then Direct connection as fallback.
    """
    # 1. Try with Proxy (if Key exists)
    if API_KEY:
        try:
            encoded_url = urllib.parse.quote(url, safe='')
            proxy_url = f"http://api.scraperapi.com?api_key={API_KEY}&url={encoded_url}&keep_headers=true"
            response = requests.get(proxy_url, headers=HEADERS, timeout=30)
            
            if response.status_code == 200:
                try:
                    return response.json()
                except json.JSONDecodeError:
                    pass 
        except Exception:
            pass

    # 2. Direct Connection Fallback
    try:
        time.sleep(random.uniform(1.0, 2.0)) 
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    
    return None

def get_advanced_stats(pid):
    """
    Fetches game log to calculate Season Avg and Last 5 Avg.
    Only called for Candidates, so we don't need the proxy here usually.
    """
    try:
        # We use the library here because it handles the complex headers/endpoints for logs well
        time.sleep(0.5)
        log = playergamelog.PlayerGameLog(player_id=pid, season='2024-25')
        df = log.get_data_frames()[0]
        
        if df.empty:
            return 0, 0, []

        # Calculate Stats
        total_pts = df['PTS'].sum()
        games_played = len(df)
        season_avg = round(total_pts / games_played, 1) if games_played > 0 else 0
        
        # Last 5
        last_5_df = df.head(5)
        last_5_pts = last_5_df['PTS'].sum()
        last_5_avg = round(last_5_pts / len(last_5_df), 1) if not last_5_df.empty else 0
        
        # Recent Game Scores for the UI chart
        recent_scores = last_5_df['PTS'].tolist()

        return season_avg, last_5_avg, recent_scores
    except Exception as e:
        print(f"    [!] Stats Error for {pid}: {e}")
        return 0, 0, []

def process_player(p):
    pid = p['id']
    name = p['full_name']
    
    # Stats endpoint
    url = f"https://stats.nba.com/stats/playercareerstats?LeagueID=00&PerMode=Totals&PlayerID={pid}"
    
    data = fetch_url(url)
    
    if not data: return None

    try:
        result_sets = data.get('resultSets', [])
        if not result_sets: return None
        rows = result_sets[0]['rowSet']
        if not rows: return None
            
        total_pts = sum(row[26] for row in rows) # Index 26 is PTS
        if total_pts == 0: return None

        next_m = ((int(total_pts) // MILESTONE_STEP) + 1) * MILESTONE_STEP
        needed = next_m - total_pts

        if needed <= WITHIN_POINTS:
            img_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"
            
            # --- NEW: Get Advanced Stats for Popup ---
            season_avg, last_5_avg, recent_scores = get_advanced_stats(pid)

            return {
                "player_name": name,
                "player_id": pid,
                "current_stat": int(total_pts),
                "target_milestone": next_m,
                "needed": int(needed),
                "image_url": img_url,
                "team": "NBA",
                # New Fields
                "season_avg": season_avg,
                "last_5_avg": last_5_avg,
                "recent_scores": recent_scores
            }
    except Exception:
        return None
    
    return None

def scan_nba():
    print(f"--- NBA DUAL-MODE SCANNER ---")
    
    if API_KEY:
        print(f"[OK] API Key detected: {API_KEY[:4]}...{API_KEY[-4:]}")

    print("Loading active player list...")
    try:
        all_players = players.get_active_players()
        print(f"Found {len(all_players)} active players.")
    except Exception:
        return

    candidates = []
    completed_count = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_player = {executor.submit(process_player, p): p for p in all_players}
        
        for future in concurrent.futures.as_completed(future_to_player):
            completed_count += 1
            if completed_count % 10 == 0:
                print(f"  Progress: {completed_count}/{len(all_players)} checked...", end='\r')

            try:
                result = future.result()
                if result:
                    print(f"\n    [!] ALERT: {result['player_name']} needs {result['needed']}")
                    candidates.append(result)
            except Exception:
                pass

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(candidates, f, indent=4)
    print(f"\nSUCCESS: Saved {len(candidates)} players to {OUTPUT_FILE}")

if __name__ == "__main__":
    scan_nba()