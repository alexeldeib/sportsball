#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = ["httpx"]
# ///
"""
Fetch detailed team statistics from ESPN API.

Usage: ./fetch_espn_team_stats.py [year]
  year defaults to 2025

Outputs: espn-team-stats-{year}.json

Fetches:
- Passing: completion %, yards/attempt, TD%, INT%, sacks
- Rushing: yards/attempt, TDs
- Turnovers: giveaways, takeaways, differential
- Efficiency: 3rd down %, red zone %, time of possession
"""
import json
import sys
import time
from datetime import datetime

import httpx

# ESPN team IDs
TEAM_IDS = {
    "ARI": 22, "ATL": 1, "BAL": 33, "BUF": 2, "CAR": 29, "CHI": 3,
    "CIN": 4, "CLE": 5, "DAL": 6, "DEN": 7, "DET": 8, "GB": 9,
    "HOU": 34, "IND": 11, "JAX": 30, "KC": 12, "LV": 13, "LAC": 24,
    "LAR": 14, "MIA": 15, "MIN": 16, "NE": 17, "NO": 18, "NYG": 19,
    "NYJ": 20, "PHI": 21, "PIT": 23, "SF": 25, "SEA": 26, "TB": 27,
    "TEN": 10, "WAS": 28,
}


def fetch_team_stats(team_code: str, team_id: int, year: int) -> dict | None:
    """Fetch detailed stats for a single team."""
    url = f"https://site.api.espn.com/apis/site/v2/sports/football/nfl/teams/{team_id}/statistics?season={year}"

    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"  Error fetching {team_code}: {e}")
        return None

    # Parse the stats
    stats = {
        "team_code": team_code,
        "season": year,
        "fetched_at": datetime.now().isoformat(),
    }

    categories = data.get("results", {}).get("stats", {}).get("categories", [])

    for cat in categories:
        cat_name = cat.get("name", "").lower()

        for stat in cat.get("stats", []):
            stat_name = stat.get("name", "")
            value = stat.get("value")
            per_game = stat.get("perGameValue")
            rank = stat.get("rank")

            if value is not None:
                # Store key stats
                if stat_name in [
                    # Passing
                    "completionPct", "netPassingYards", "passingAttempts",
                    "passingTouchdowns", "interceptions", "QBRating", "sacks",
                    "yardsPerPassAttempt", "netYardsPerPassAttempt",
                    # Rushing
                    "rushingYards", "rushingAttempts", "rushingTouchdowns",
                    "yardsPerRushAttempt",
                    # Receiving/Total
                    "totalYards", "yardsPerPlay",
                    # Turnovers
                    "totalGiveaways", "totalTakeaways", "turnoverDifferential",
                    "fumblesLost", "interceptions",
                    # Efficiency
                    "thirdDownConvPct", "fourthDownConvPct",
                    "redZoneScoringPct", "avgTimeOfPossession",
                    # Scoring
                    "totalPoints", "totalPointsPerGame",
                ]:
                    stats[stat_name] = value
                    if per_game is not None:
                        stats[f"{stat_name}_per_game"] = per_game
                    if rank is not None:
                        stats[f"{stat_name}_rank"] = rank

    # Compute derived stats
    total_plays = (stats.get("passingAttempts", 0) +
                   stats.get("rushingAttempts", 0) +
                   stats.get("sacks", 0))
    if total_plays > 0:
        stats["yardsPerPlay"] = stats.get("totalYards", 0) / total_plays

    stats["turnoverDifferential"] = (
        stats.get("totalTakeaways", 0) - stats.get("totalGiveaways", 0)
    )

    return stats


def fetch_all_injuries() -> dict:
    """Fetch all NFL injuries from the global endpoint."""
    url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/injuries"

    try:
        response = httpx.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        print(f"  Error fetching injuries: {e}")
        return {}

    # Map team display name to team code
    TEAM_NAME_TO_CODE = {
        "Arizona Cardinals": "ARI", "Atlanta Falcons": "ATL", "Baltimore Ravens": "BAL",
        "Buffalo Bills": "BUF", "Carolina Panthers": "CAR", "Chicago Bears": "CHI",
        "Cincinnati Bengals": "CIN", "Cleveland Browns": "CLE", "Dallas Cowboys": "DAL",
        "Denver Broncos": "DEN", "Detroit Lions": "DET", "Green Bay Packers": "GB",
        "Houston Texans": "HOU", "Indianapolis Colts": "IND", "Jacksonville Jaguars": "JAX",
        "Kansas City Chiefs": "KC", "Las Vegas Raiders": "LV", "Los Angeles Chargers": "LAC",
        "Los Angeles Rams": "LAR", "Miami Dolphins": "MIA", "Minnesota Vikings": "MIN",
        "New England Patriots": "NE", "New Orleans Saints": "NO", "New York Giants": "NYG",
        "New York Jets": "NYJ", "Philadelphia Eagles": "PHI", "Pittsburgh Steelers": "PIT",
        "San Francisco 49ers": "SF", "Seattle Seahawks": "SEA", "Tampa Bay Buccaneers": "TB",
        "Tennessee Titans": "TEN", "Washington Commanders": "WAS",
    }

    all_injuries = {}
    for team_data in data.get("injuries", []):
        team_name = team_data.get("displayName", "")
        team_code = TEAM_NAME_TO_CODE.get(team_name)
        if not team_code:
            continue

        injuries = []
        for item in team_data.get("injuries", []):
            athlete = item.get("athlete", {})
            position = athlete.get("position", {})

            injuries.append({
                "player_name": athlete.get("displayName"),
                "position": position.get("abbreviation") if isinstance(position, dict) else position,
                "status": item.get("status"),
                "short_comment": item.get("shortComment"),
                "type": item.get("type", {}).get("description") if isinstance(item.get("type"), dict) else item.get("type"),
            })

        if injuries:
            all_injuries[team_code] = injuries

    return all_injuries


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025

    print(f"Fetching ESPN team stats for {year}...")

    all_stats = []

    for team_code, team_id in TEAM_IDS.items():
        print(f"  {team_code}...", end=" ", flush=True)

        stats = fetch_team_stats(team_code, team_id, year)
        if stats:
            all_stats.append(stats)
            print(f"OK ({stats.get('totalPoints', 0)} pts)")
        else:
            print("FAILED")

        time.sleep(0.3)  # Rate limiting

    # Fetch all injuries from global endpoint
    print("\nFetching injuries from global endpoint...")
    all_injuries = fetch_all_injuries()

    # Save stats
    output_file = f"espn-team-stats-{year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\nSaved {len(all_stats)} team stats to {output_file}")

    # Save injuries
    injuries_file = f"injuries-{year}.json"
    with open(injuries_file, "w", encoding="utf-8") as f:
        json.dump(all_injuries, f, indent=2)

    # Count total injuries
    total_injuries = sum(len(v) for v in all_injuries.values())
    print(f"Saved {total_injuries} injuries across {len(all_injuries)} teams to {injuries_file}")

    # Print some interesting stats
    print("\n=== Top 5 by Yards Per Play ===")
    sorted_by_ypp = sorted(all_stats, key=lambda x: x.get("yardsPerPlay", 0), reverse=True)
    for t in sorted_by_ypp[:5]:
        print(f"  {t['team_code']}: {t.get('yardsPerPlay', 0):.2f} YPP")

    print("\n=== Top 5 by Turnover Differential ===")
    sorted_by_to = sorted(all_stats, key=lambda x: x.get("turnoverDifferential", 0), reverse=True)
    for t in sorted_by_to[:5]:
        print(f"  {t['team_code']}: {t.get('turnoverDifferential', 0):+.0f}")


if __name__ == "__main__":
    main()
