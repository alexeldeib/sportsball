#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
# ]
# ///
"""
Fetch weekly NFL player stats from Sleeper API.
Usage: ./fetch_weekly_stats.py [year]
  year defaults to 2024

Outputs: player-weekly-stats-{year}.json
"""
import json
import sys
import requests

SLEEPER_STATS_URL = "https://api.sleeper.app/stats/nfl"
SLEEPER_PLAYERS_URL = "https://api.sleeper.app/v1/players/nfl"

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

# Key stats to track weekly
WEEKLY_STATS = [
    # Passing
    "pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int",
    # Rushing
    "rush_att", "rush_yd", "rush_td",
    # Receiving
    "rec", "rec_yd", "rec_td", "rec_tgt",
    # Defense
    "idp_tkl", "idp_sack", "idp_int", "idp_ff",
    # Kicking
    "fgm", "fga", "xpm", "xpa",
    # Fantasy points (useful for context)
    "pts_ppr",
    # Games
    "gp",
]


def fetch_json(url, desc):
    """Fetch JSON from URL with error handling."""
    print(f"  {desc}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def extract_weekly_stats(stats_obj):
    """Extract relevant weekly stats."""
    if not stats_obj:
        return {}

    extracted = {}
    for stat in WEEKLY_STATS:
        val = stats_obj.get(stat)
        if val is not None and val != 0:
            extracted[stat] = round(val, 1) if isinstance(val, float) else val

    return extracted


def fetch_week(year, week):
    """Fetch stats for a specific week."""
    url = f"{SLEEPER_STATS_URL}/{year}/{week}?season_type=regular"

    try:
        data = fetch_json(url, f"Week {week}")
    except requests.RequestException as e:
        print(f"    Error: {e}")
        return []

    weekly_stats = []

    for item in data:
        player_id = item.get("player_id")
        player_info = item.get("player", {})
        stats_obj = item.get("stats", {})

        if not player_id or not player_info:
            continue

        # Get player details
        team_code = player_info.get("team")
        position = player_info.get("position")

        if not team_code or team_code not in VALID_TEAM_CODES:
            continue

        # Build name
        first = (player_info.get("first_name") or "").strip()
        last = (player_info.get("last_name") or "").strip()
        name = f"{first} {last}".strip()

        if not name:
            continue

        # Extract stats
        stats = extract_weekly_stats(stats_obj)

        if not stats:
            continue

        weekly_stats.append({
            "player_id": player_id,
            "player_name": name,
            "team": team_code,
            "position": position,
            "opponent": item.get("opponent"),
            "season": int(year),
            "week": week,
            "stats": stats,
        })

    return weekly_stats


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2024"

    print(f"Fetching {year} weekly player stats from Sleeper...")

    all_stats = []

    # Regular season: weeks 1-18
    for week in range(1, 19):
        week_stats = fetch_week(year, week)
        all_stats.extend(week_stats)
        print(f"    Week {week}: {len(week_stats)} players with stats")

    # Sort by week, then player name
    all_stats.sort(key=lambda s: (s["week"], s["player_name"]))

    output_file = f"player-weekly-stats-{year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2)

    # Summary
    unique_players = len(set(s["player_id"] for s in all_stats))
    print(f"\nSaved {len(all_stats)} weekly stat entries to {output_file}")
    print(f"  - {unique_players} unique players")
    print(f"  - Average {len(all_stats) // 18:.0f} players per week")


if __name__ == "__main__":
    main()
