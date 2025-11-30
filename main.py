#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
# ]
# ///
import json
import requests

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
VALID_STATUSES = {"Active", "Rookie"}  # Sleeper status values we care about


def fetch_sleeper_players():
    print("Fetching players from Sleeper...")
    resp = requests.get(SLEEPER_PLAYERS_URL, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    # Sleeper returns a dict: { "player_id": { ...player fields... }, ... }
    return data


def build_player_list(raw_players):
    players = []

    for player_id, p in raw_players.items():
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

        players.append(
            {
                "name": name,
                "team": TEAM_MAP[team_code],
                "team_code": team_code,
                "position": position,
            }
        )

    # Sort for determinism: by team, position, name
    players.sort(key=lambda x: (x["team"], x["position"], x["name"]))
    return players


def main():
    raw = fetch_sleeper_players()
    players = build_player_list(raw)

    output_file = "players-2025.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(players)} players to {output_file}")


if __name__ == "__main__":
    main()