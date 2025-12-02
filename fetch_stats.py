#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
# ]
# ///
"""
Fetch NFL player stats from Sleeper API and merge with roster data.
Usage: ./fetch_stats.py [year]
  year defaults to 2024
"""
import json
import sys
import requests

PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"

# Map Sleeper team codes to full NFL team names
TEAM_MAP = {
    "ARI": "Arizona Cardinals",
    "ATL": "Atlanta Falcons",
    "BAL": "Baltimore Ravens",
    "BUF": "Buffalo Bills",
    "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears",
    "CIN": "Cincinnati Bengals",
    "CLE": "Cleveland Browns",
    "DAL": "Dallas Cowboys",
    "DEN": "Denver Broncos",
    "DET": "Detroit Lions",
    "GB":  "Green Bay Packers",
    "HOU": "Houston Texans",
    "IND": "Indianapolis Colts",
    "JAX": "Jacksonville Jaguars",
    "KC":  "Kansas City Chiefs",
    "LV":  "Las Vegas Raiders",
    "LAC": "Los Angeles Chargers",
    "LAR": "Los Angeles Rams",
    "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings",
    "NE":  "New England Patriots",
    "NO":  "New Orleans Saints",
    "NYG": "New York Giants",
    "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles",
    "PIT": "Pittsburgh Steelers",
    "SF":  "San Francisco 49ers",
    "SEA": "Seattle Seahawks",
    "TB":  "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans",
    "WAS": "Washington Commanders",
}

VALID_TEAM_CODES = set(TEAM_MAP.keys())
VALID_STATUSES = {"Active", "Rookie"}

# Common fields for all positions
COMMON_FIELDS = ["gp", "gs", "off_snp", "def_snp", "st_snp"]

# Key stats to include by position
STAT_FIELDS = {
    "QB": ["pass_yd", "pass_td", "pass_int", "rush_yd", "rush_td"],
    "RB": ["rush_yd", "rush_td", "rec", "rec_yd", "rec_td"],
    "WR": ["rec", "rec_yd", "rec_td", "rush_yd"],
    "TE": ["rec", "rec_yd", "rec_td"],
    "K":  ["fgm", "fga", "xpm", "xpa"],
    "DEF": ["idp_tkl", "idp_sack", "idp_int", "idp_ff"],
    "OL": [],  # O-line just gets common fields
}

# Positions that use DEF stats
DEF_POSITIONS = {"LB", "DL", "DE", "DT", "CB", "S", "DB", "EDGE", "ILB", "OLB", "MLB", "NT", "FS", "SS"}
OL_POSITIONS = {"OL", "OT", "G", "C", "T"}


def fetch_json(url, desc):
    print(f"Fetching {desc}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def get_stat_fields(position):
    """Get relevant stat fields for a position."""
    fields = COMMON_FIELDS.copy()
    if position in STAT_FIELDS:
        fields.extend(STAT_FIELDS[position])
    elif position in DEF_POSITIONS:
        fields.extend(STAT_FIELDS["DEF"])
    elif position in OL_POSITIONS:
        fields.extend(STAT_FIELDS["OL"])
    return fields


def extract_stats(player_stats, position):
    """Extract relevant stats for a position."""
    if not player_stats:
        return {}

    fields = get_stat_fields(position)
    stats = {}
    for field in fields:
        val = player_stats.get(field)
        if val is not None and val != 0:
            # Round floats to 1 decimal
            stats[field] = round(val, 1) if isinstance(val, float) else val
    return stats


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2024"
    stats_url = f"https://api.sleeper.app/stats/nfl/{year}?season_type=regular"

    # Fetch all players
    players_raw = fetch_json(PLAYERS_URL, "players")

    # Fetch season stats (no week = full season)
    stats_list = fetch_json(stats_url, f"{year} season stats")

    # Convert stats list to dict keyed by player_id
    stats_by_player = {}
    for item in stats_list:
        pid = item.get("player_id")
        if pid:
            stats_by_player[pid] = item.get("stats", {})

    print(f"  Found stats for {len(stats_by_player)} players")

    players = []

    for player_id, p in players_raw.items():
        position = p.get("position")
        team_code = p.get("team")
        status = p.get("status")

        # Filter by position, team, and status
        if not position:
            continue
        if team_code not in VALID_TEAM_CODES:
            continue
        if status not in VALID_STATUSES:
            continue

        first = (p.get("first_name") or "").strip()
        last = (p.get("last_name") or "").strip()
        name = (first + " " + last).strip()
        if not name:
            continue

        # Get stats for this player
        player_stats = stats_by_player.get(player_id, {})
        stats = extract_stats(player_stats, position)

        player_data = {
            "name": name,
            "team": TEAM_MAP[team_code],
            "team_code": team_code,
            "position": position,
            "number": p.get("number"),  # Jersey number
        }

        # Add stats if any exist
        if stats:
            player_data["stats"] = stats

        players.append(player_data)

    # Sort by team, position, name
    players.sort(key=lambda x: (x["team"], x["position"], x["name"]))

    output_file = f"players-with-stats-{year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

    # Count players with stats
    with_stats = sum(1 for p in players if "stats" in p)
    print(f"Saved {len(players)} players to {output_file}")
    print(f"  - {with_stats} players have stats")
    print(f"  - {len(players) - with_stats} players have no stats (rookies, backups, etc.)")


if __name__ == "__main__":
    main()
