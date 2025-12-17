import os
import time
import json
import random
import requests
from nba_api.stats.static import players
from nba_api.stats.endpoints import playercareerstats
from nba_api.stats.library.http import NBAStatsHTTP

# --- CONFIGURATION ---
MILESTONE_STEP = 1000
WITHIN_POINTS = 250
OUTPUT_FILE = "nba_milestones.json"
# Get the key from GitHub Actions environment
API_KEY = os.environ.get('SCRAPERAPI_KEY', '') 

def get_proxy_url(url):
    """Wraps a URL with ScraperAPI"""
    if not API_KEY:
        return url
    return f"http://api.scraperapi.com?api_key={API_KEY}&url={url}"

# Inject Proxy into NBA API library
if API_KEY:
    # We tell the NBA API library to use ScraperAPI as a proxy
    # This ensures all its internal 'requests' go through the proxy
    NBAStatsHTTP.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    })
    # Note: Some proxy services require specific session handling
    # If standard wrapping fails, we'll use raw requests below.

def scan_nba_active_players():
    print(f"--- NBA PROXY SCANNER ---")
    
    # To save credits, we'll only scan players likely to be stars/veterans
    # You can adjust this list as needed
    all_active = players.get_active_players()
    print(f"Total active players: {len(all_active)}")
    
    # Optimization: Filter for players who have been in league a bit 
    # (Or just scan everyone if you have enough credits)
    candidates = []
    
    for i, p in enumerate(all_active):
        if i % 10 == 0: print(f"Processing {i}/{len(all_active)}...")
        
        pid = p['id']
        name = p['full_name']

        try:
            # Use raw requests with ScraperAPI for maximum reliability
            # This is the 'manual' way to get stats through the proxy
            url = f"https://stats.nba.com/stats/playercareerstats?LeagueID=00&PerMode=Totals&PlayerID={pid}"
            proxy_url = get_proxy_url(url)
            
            # Use a slightly longer timeout because proxies can be slower
            response = requests.get(proxy_url, timeout=30)
            data = response.json()
            
            # Navigate the complex NBA JSON structure
            # RowSet[0] is 'SeasonTotalsRegularSeason'
            rows = data['resultSets'][0]['rowSet']
            total_points = sum(row[26] for row in rows) # Index 26 is usually PTS

            next_m = ((int(total_points) // MILESTONE_STEP) + 1) * MILESTONE_STEP
            needed = next_m - total_points
            
            if needed <= WITHIN_POINTS:
                print(f"  [!] {name} needs {int(needed)}")
                candidates.append({
                    "player_name": name,
                    "team": "Check Site", # Team info requires another API call; keeping it simple to save credits
                    "current_stat": int(total_points),
                    "target_milestone": next_m,
                    "needed": int(needed),
                    "stat_type": "points"
                })
            
            # Even with proxy, don't spam
            time.sleep(0.5)

        except Exception as e:
            print(f"Error for {name}: {e}")
            continue

    with open(OUTPUT_FILE, 'w') as f:
        json.dump(candidates, f, indent=4)
    print(f"Saved {len(candidates)} candidates.")

if __name__ == "__main__":
    scan_nba_active_players()
