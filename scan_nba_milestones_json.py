import os
import time
import json
import requests
import random
from nba_api.stats.static import players # Use the local player database

# --- CONFIG ---
MILESTONE_STEP = 1000
WITHIN_POINTS = 250 
OUTPUT_FILE = "nba_milestones.json"
API_KEY = os.environ.get('SCRAPERAPI_KEY', '')

def get_proxy_url(url):
    if not API_KEY: 
        return url
    return f"http://api.scraperapi.com?api_key={API_KEY}&url={url}"

def scan_nba():
    print(f"--- NBA PROXY SCANNER ---")
    if not API_KEY:
        print("FATAL: SCRAPERAPI_KEY not found in environment variables.")
        return

    # STEP 1: Get Player List LOCALLY
    # This doesn't use the network, so it can't be blocked!
    print("Loading active player list from local database...")
    all_players = players.get_active_players()
    print(f"Found {len(all_players)} active players.")

    headers = {
        "Host": "stats.nba.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nba.com/",
        "Origin": "https://www.nba.com"
    }

    candidates = []

    # STEP 2: Scan for stats
    for i, p in enumerate(all_players):
        pid = p['id']
        name = p['full_name']
        
        if i % 20 == 0: print(f"  Checking {i}/{len(all_players)}: {name}...")

        try:
            # Stats endpoint
            url = f"https://stats.nba.com/stats/playercareerstats?LeagueID=00&PerMode=Totals&PlayerID={pid}"
            response = requests.get(get_proxy_url(url), headers=headers, timeout=30)
            
            if response.status_code != 200:
                continue
                
            # Safely attempt to parse JSON
            try:
                stats_data = response.json()
            except Exception:
                # If it's not JSON, the proxy might be returning an error page
                continue

            # RowSet[0] is SeasonTotalsRegularSeason
            rows = stats_data['resultSets'][0]['rowSet']
            total_pts = sum(row[26] for row in rows) # Index 26 is PTS

            if total_pts == 0: continue

            next_m = ((int(total_pts) // MILESTONE_STEP) + 1) * MILESTONE_STEP
            needed = next_m - total_pts

            if needed <= WITHIN_POINTS:
                print(f"    [!] ALERT: {name} needs {int(needed)}")
                img_url = f"https://cdn.nba.com/headshots/nba/latest/1040x760/{pid}.png"
                
                candidates.append({
                    "player_name": name,
                    "player_id": pid,
                    "current_stat": int(total_pts),
                    "target_milestone": next_m,
                    "needed": int(needed),
                    "image_url": img_url,
                    "team": "NBA" 
                })
            
            # Anti-detection delay
            time.sleep(random.uniform(0.6, 1.2))

        except Exception:
            continue

    # Save results
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(candidates, f, indent=4)
    print(f"SUCCESS: Saved {len(candidates)} players to {OUTPUT_FILE}")

if __name__ == "__main__":
    scan_nba()