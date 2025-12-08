#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "requests",
# ]
# ///
"""
Fetch NFL game scores and schedules from ESPN API.
Usage: ./fetch_games.py [year]       # Fetch single year
       ./fetch_games.py --all        # Fetch 2020-2025 (all historical)
  year defaults to 2024
"""
import json
import sys
import time
import requests

ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"

# Map ESPN team abbreviations to our standard codes
# ESPN uses slightly different codes for some teams
ESPN_TEAM_MAP = {
    "ARI": "ARI",
    "ATL": "ATL",
    "BAL": "BAL",
    "BUF": "BUF",
    "CAR": "CAR",
    "CHI": "CHI",
    "CIN": "CIN",
    "CLE": "CLE",
    "DAL": "DAL",
    "DEN": "DEN",
    "DET": "DET",
    "GB": "GB",
    "HOU": "HOU",
    "IND": "IND",
    "JAX": "JAX",
    "KC": "KC",
    "LV": "LV",
    "OAK": "LV",   # Oakland Raiders -> Las Vegas (historical)
    "LAC": "LAC",
    "LAR": "LAR",
    "LA": "LAR",   # Sometimes ESPN uses just "LA" for Rams
    "MIA": "MIA",
    "MIN": "MIN",
    "NE": "NE",
    "NO": "NO",
    "NYG": "NYG",
    "NYJ": "NYJ",
    "PHI": "PHI",
    "PIT": "PIT",
    "SF": "SF",
    "SEA": "SEA",
    "TB": "TB",
    "TEN": "TEN",
    "WSH": "WAS",  # ESPN uses WSH, we use WAS
    "WAS": "WAS",  # Sometimes ESPN uses WAS directly
}


def fetch_json(url, desc):
    """Fetch JSON from URL with error handling."""
    print(f"  Fetching {desc}...")
    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    return resp.json()


def normalize_team(abbrev):
    """Normalize ESPN team abbreviation to our standard codes."""
    return ESPN_TEAM_MAP.get(abbrev, abbrev)


def extract_linescores(competitor):
    """Extract quarterly scores from competitor linescores."""
    linescores = competitor.get("linescores", [])
    quarters = {"q1": 0, "q2": 0, "q3": 0, "q4": 0, "ot": 0}

    for ls in linescores:
        period = ls.get("period", 0)
        value = int(ls.get("value", 0))

        if period == 1:
            quarters["q1"] = value
        elif period == 2:
            quarters["q2"] = value
        elif period == 3:
            quarters["q3"] = value
        elif period == 4:
            quarters["q4"] = value
        elif period >= 5:
            # Overtime periods
            quarters["ot"] += value

    return quarters


def parse_game(event):
    """Parse a single game event into our format."""
    competition = event.get("competitions", [{}])[0]
    competitors = competition.get("competitors", [])

    if len(competitors) < 2:
        return None

    # ESPN: home team has homeAway="home", away has homeAway="away"
    home_comp = None
    away_comp = None

    for comp in competitors:
        if comp.get("homeAway") == "home":
            home_comp = comp
        else:
            away_comp = comp

    if not home_comp or not away_comp:
        return None

    # Extract team info
    home_team = normalize_team(home_comp.get("team", {}).get("abbreviation", ""))
    away_team = normalize_team(away_comp.get("team", {}).get("abbreviation", ""))

    if not home_team or not away_team:
        return None

    # Check if game is completed
    status = event.get("status", {})
    is_completed = status.get("type", {}).get("completed", False)

    # Extract scores (only if game has started/completed)
    home_score = None
    away_score = None
    home_quarters = {}
    away_quarters = {}

    if is_completed or status.get("type", {}).get("state") == "in":
        try:
            home_score = int(home_comp.get("score", 0))
            away_score = int(away_comp.get("score", 0))
        except (ValueError, TypeError):
            pass

        home_quarters = extract_linescores(home_comp)
        away_quarters = extract_linescores(away_comp)

    # Extract date
    game_date = event.get("date", "")[:10]  # Just YYYY-MM-DD

    game = {
        "home_team": home_team,
        "away_team": away_team,
        "game_date": game_date,
        "is_completed": is_completed,
    }

    if home_score is not None:
        game["home_score"] = home_score
        game["away_score"] = away_score
        game["total_points"] = home_score + away_score

        # Add quarterly breakdown
        game["home_q1"] = home_quarters.get("q1", 0)
        game["home_q2"] = home_quarters.get("q2", 0)
        game["home_q3"] = home_quarters.get("q3", 0)
        game["home_q4"] = home_quarters.get("q4", 0)
        game["home_ot"] = home_quarters.get("ot", 0)

        game["away_q1"] = away_quarters.get("q1", 0)
        game["away_q2"] = away_quarters.get("q2", 0)
        game["away_q3"] = away_quarters.get("q3", 0)
        game["away_q4"] = away_quarters.get("q4", 0)
        game["away_ot"] = away_quarters.get("ot", 0)

        # Compute half totals
        game["home_1h"] = game["home_q1"] + game["home_q2"]
        game["home_2h"] = game["home_q3"] + game["home_q4"] + game["home_ot"]
        game["away_1h"] = game["away_q1"] + game["away_q2"]
        game["away_2h"] = game["away_q3"] + game["away_q4"] + game["away_ot"]

    return game


def fetch_week(year, week):
    """Fetch all games for a specific week."""
    url = f"{ESPN_SCOREBOARD_URL}?dates={year}&seasontype=2&week={week}"

    try:
        data = fetch_json(url, f"week {week}")
    except requests.RequestException as e:
        print(f"    Error fetching week {week}: {e}")
        return []

    events = data.get("events", [])
    games = []

    for event in events:
        game = parse_game(event)
        if game:
            game["week"] = week
            game["season"] = int(year)
            games.append(game)

    return games


def fetch_season(year, rate_limit=0.5):
    """Fetch all games for a single season."""
    print(f"Fetching {year} NFL game data from ESPN...")

    all_games = []

    # 2020 had 17 weeks, 2021+ has 18 weeks
    max_week = 17 if int(year) == 2020 else 18

    for week in range(1, max_week + 1):
        games = fetch_week(year, week)
        all_games.extend(games)
        print(f"    Week {week}: {len(games)} games")
        if rate_limit > 0:
            time.sleep(rate_limit)

    # Sort by week, then date
    all_games.sort(key=lambda g: (g["week"], g["game_date"]))

    output_file = f"games-{year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_games, f, indent=2)

    # Summary stats
    completed = sum(1 for g in all_games if g.get("is_completed"))
    print(f"  Saved {len(all_games)} games to {output_file}")
    print(f"    - {completed} completed games with scores")

    return len(all_games)


def main():
    args = sys.argv[1:]

    if "--all" in args:
        # Fetch all historical seasons 2020-2025
        print("Fetching all seasons (2020-2025)...")
        total = 0
        for year in range(2020, 2026):
            print(f"\n{'='*40}")
            count = fetch_season(str(year), rate_limit=0.3)
            total += count
        print(f"\n{'='*40}")
        print(f"Total: {total} games across 6 seasons")
    else:
        # Single year mode
        year = args[0] if args else "2024"
        fetch_season(year, rate_limit=0)


if __name__ == "__main__":
    main()
