import pandas as pd
import os
import time
from nba_api.stats.endpoints import commonplayerinfo
from nba_api.stats.static import players

# --- CONFIGURATION ---
PLAYERS_FILE = 'players.txt'
CSV_DIRECTORY = '.'
# ---------------------

def get_player_id_by_name(player_name):
    """
    Searches for a player ID by full name.
    Returns the ID (str) if found, otherwise None.
    """
    # 1. Search for the player
    found_players = players.find_players_by_full_name(player_name)
    
    # 2. Handle results
    if not found_players:
        print(f"  [!] Error: Could not find any player named '{player_name}' in NBA API.")
        return None
    elif len(found_players) > 1:
        # If multiple, we usually take the first exact match, or just the first one.
        # Example: "Isaiah Thomas" (Legend) vs "Isaiah Thomas" (Current)
        # We'll default to the first one but warn the user.
        print(f"  [!] Warning: Multiple players found for '{player_name}'. Using ID: {found_players[0]['id']}")
        return str(found_players[0]['id'])
    else:
        return str(found_players[0]['id'])

def get_player_birthday(player_id):
    """Fetches birthdate for a specific player ID."""
    try:
        player_info = commonplayerinfo.CommonPlayerInfo(player_id=player_id)
        df_info = player_info.get_data_frames()[0]
        return df_info['BIRTHDATE'].iloc[0]
    except Exception as e:
        print(f"  [!] Error fetching info for ID {player_id}: {e}")
        return None

def process_players():
    if not os.path.exists(PLAYERS_FILE):
        raise FileNotFoundError(f"Could not find {PLAYERS_FILE}")

    with open(PLAYERS_FILE, 'r') as f:
        lines = f.readlines()

    print(f"Processing {len(lines)} players...")

    for line in lines:
        line = line.strip()
        if not line: continue

        # --- STEP 1: Determine Name and ID ---
        if ',' in line:
            # Format: "LeBron James, 2544"
            parts = line.split(',')
            name = parts[0].strip()
            pid = parts[1].strip()
        else:
            # Format: "LeBron James" (No ID provided)
            name = line
            print(f"Looking up ID for: {name}...")
            pid = get_player_id_by_name(name)
            
        if not pid:
            continue

        # --- STEP 2: Check for CSV ---
        # UPDATED: Handle "cache_gary_payton.csv" format
        slug = name.lower().replace(' ', '_')
        csv_filename = os.path.join(CSV_DIRECTORY, f"cache_{slug}.csv")
        
        # Fallback: check if standard ID filename exists just in case
        if not os.path.exists(csv_filename):
            id_filename = os.path.join(CSV_DIRECTORY, f"{pid}.csv")
            if os.path.exists(id_filename):
                csv_filename = id_filename
            else:
                print(f"  [!] Skipping {name} - No CSV file found. Expected: {csv_filename}")
                continue

        # --- STEP 3: Update Birthday ---
        try:
            df = pd.read_csv(csv_filename)
            
            if 'BIRTHDATE' in df.columns:
                # Optional: Check if it's empty and refill it, or just skip
                # print(f"  - Birthday already present for {name}.")
                continue

            birthday = get_player_birthday(pid)
            
            if birthday:
                df['BIRTHDATE'] = birthday
                df.to_csv(csv_filename, index=False)
                print(f"  [✓] Success: Added birthday ({birthday}) to {csv_filename}")
                # Sleep to avoid rate limits
                time.sleep(0.600)
            else:
                print(f"  [X] Failed to retrieve birthday for {name}")

        except Exception as e:
            print(f"  [!] Error processing CSV for {name}: {e}")

if __name__ == "__main__":
    process_players()