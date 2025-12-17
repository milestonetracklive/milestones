import os
import time
import json
import requests
import random

# --- CONFIG ---
MILESTONE_STEP = 1000
WITHIN_POINTS = 250 
OUTPUT_FILE = "nba_milestones.json"
# If running locally, you can paste your key here for a quick test:
# API_KEY = "YOUR_KEY_HERE" 
API_KEY = os.environ.get('SCRAPERAPI_KEY', '')

def get_proxy_url(url):
    if not API_KEY: 
        print("  [!] Warning: No API Key found. Running without proxy...")
        return url
    return f"http://api.scraperapi.com?api_key={API_KEY}&url={url}"

def scan_nba():
    print(f"--- NBA PROXY SCANNER ---")
    if not API_KEY:
        print("FATAL: SCRAPERAPI_KEY not found in environment variables.")
        return

    # To get the list of players, we use a lighter internal search first
    # This endpoint is less likely to be blocked than the stats one
    print("Fetching player list...")
    list_url = "https://stats.nba.com/stats/commonallplayers?IsOnlyCurrentSeason=1&LeagueID=00&Season=2023-24"
    
    headers = {
        "Host": "stats.nba.com",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.nba.com/"
    }

    try:
        res = requests.get(get_proxy_url(list_url), headers=headers, timeout=30)
        data = res.json()
        # Row layout: [PERSON_ID, DISPLAY_LAST_COMMA_FIRST, DISPLAY_FIRST_LAST, ...]
        all_players = data['resultSets'][0]['rowSet']
        print(f"Found {len(all_players)} active players.")
    except Exception as e:
        print(f"Failed to fetch player list: {e}")
        return

    candidates = []

    # To save credits and time, we'll only scan the first 300 (or adjust as needed)
    for i, p in enumerate(all_players):
        pid = p[0]
        name = p[2]
        
        if i % 10 == 0: print(f"  Checking {i}/{len(all_players)}: {name}...")

        try:
            # Stats endpoint
            url = f"https://stats.nba.com/stats/playercareerstats?LeagueID=00&PerMode=Totals&PlayerID={pid}"
            response = requests.get(get_proxy_url(url), headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"    [!] Blocked on {name} (Status {response.status_code})")
                continue
                
            stats_data = response.json()
            # Index 26 is Points in Career Totals
            rows = stats_data['resultSets'][0]['rowSet']
            total_pts = sum(row[26] for row in rows)

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
                    "team": p[10] if p[10] else "NBA" # Team Name is at index 10
                })
            
            # Anti-detection delay
            time.sleep(random.uniform(0.5, 1.2))

        except Exception:
            continue

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(candidates, f, indent=4)
    print(f"SUCCESS: Saved {len(candidates)} players to {OUTPUT_FILE}")

if __name__ == "__main__":
    scan_nba()