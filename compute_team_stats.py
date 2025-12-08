#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Compute aggregated team statistics from game data.
Usage: ./compute_team_stats.py [year]
  year defaults to 2024

Reads: games-{year}.json
Outputs: team-stats-{year}.json
"""
import json
import sys
from collections import defaultdict

# All NFL team codes
TEAM_CODES = [
    "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
    "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
    "LV", "LAC", "LAR", "MIA", "MIN", "NE", "NO", "NYG",
    "NYJ", "PHI", "PIT", "SF", "SEA", "TB", "TEN", "WAS",
]


def compute_avg(values):
    """Compute average, return 0 if empty."""
    return round(sum(values) / len(values), 1) if values else 0.0


def compute_team_stats(games, team_code):
    """Compute all stats for a single team."""
    # Filter to completed games only
    team_games = [
        g for g in games
        if g.get("is_completed") and (g["home_team"] == team_code or g["away_team"] == team_code)
    ]

    if not team_games:
        return None

    # Separate home and away games
    home_games = [g for g in team_games if g["home_team"] == team_code]
    away_games = [g for g in team_games if g["away_team"] == team_code]

    # Calculate points scored and allowed
    points_scored = []
    points_allowed = []
    home_scored = []
    home_allowed = []
    away_scored = []
    away_allowed = []

    # Quarterly scoring
    q1_scored, q2_scored, q3_scored, q4_scored = [], [], [], []
    q1_allowed, q2_allowed, q3_allowed, q4_allowed = [], [], [], []
    first_half_scored, second_half_scored = [], []
    first_half_allowed, second_half_allowed = [], []

    wins, losses, ties = 0, 0, 0
    home_wins, home_losses = 0, 0
    away_wins, away_losses = 0, 0

    for g in team_games:
        is_home = g["home_team"] == team_code

        if is_home:
            scored = g["home_score"]
            allowed = g["away_score"]
            # Quarterly
            q1_s, q2_s, q3_s, q4_s = g["home_q1"], g["home_q2"], g["home_q3"], g["home_q4"]
            q1_a, q2_a, q3_a, q4_a = g["away_q1"], g["away_q2"], g["away_q3"], g["away_q4"]
            h1_s, h2_s = g["home_1h"], g["home_2h"]
            h1_a, h2_a = g["away_1h"], g["away_2h"]
        else:
            scored = g["away_score"]
            allowed = g["home_score"]
            q1_s, q2_s, q3_s, q4_s = g["away_q1"], g["away_q2"], g["away_q3"], g["away_q4"]
            q1_a, q2_a, q3_a, q4_a = g["home_q1"], g["home_q2"], g["home_q3"], g["home_q4"]
            h1_s, h2_s = g["away_1h"], g["away_2h"]
            h1_a, h2_a = g["home_1h"], g["home_2h"]

        points_scored.append(scored)
        points_allowed.append(allowed)

        # Home/away splits
        if is_home:
            home_scored.append(scored)
            home_allowed.append(allowed)
        else:
            away_scored.append(scored)
            away_allowed.append(allowed)

        # Quarter stats
        q1_scored.append(q1_s)
        q2_scored.append(q2_s)
        q3_scored.append(q3_s)
        q4_scored.append(q4_s)
        q1_allowed.append(q1_a)
        q2_allowed.append(q2_a)
        q3_allowed.append(q3_a)
        q4_allowed.append(q4_a)

        # Half stats
        first_half_scored.append(h1_s)
        second_half_scored.append(h2_s)
        first_half_allowed.append(h1_a)
        second_half_allowed.append(h2_a)

        # Win/loss
        if scored > allowed:
            wins += 1
            if is_home:
                home_wins += 1
            else:
                away_wins += 1
        elif scored < allowed:
            losses += 1
            if is_home:
                home_losses += 1
            else:
                away_losses += 1
        else:
            ties += 1

    # Recent form (last 5 games)
    recent_games = sorted(team_games, key=lambda g: (g["week"], g["game_date"]))[-5:]
    recent_scored = []
    recent_allowed = []
    recent_wins = 0

    for g in recent_games:
        is_home = g["home_team"] == team_code
        if is_home:
            scored = g["home_score"]
            allowed = g["away_score"]
        else:
            scored = g["away_score"]
            allowed = g["home_score"]
        recent_scored.append(scored)
        recent_allowed.append(allowed)
        if scored > allowed:
            recent_wins += 1

    stats = {
        "team_code": team_code,
        "games_played": len(team_games),
        "wins": wins,
        "losses": losses,
        "ties": ties,
        "win_pct": round(wins / len(team_games), 3) if team_games else 0,

        # Points per game
        "total_points_scored": sum(points_scored),
        "total_points_allowed": sum(points_allowed),
        "ppg_scored": compute_avg(points_scored),
        "ppg_allowed": compute_avg(points_allowed),
        "point_differential": round(compute_avg(points_scored) - compute_avg(points_allowed), 1),

        # Home/away splits
        "home_games": len(home_games),
        "away_games": len(away_games),
        "home_ppg": compute_avg(home_scored),
        "away_ppg": compute_avg(away_scored),
        "home_ppg_allowed": compute_avg(home_allowed),
        "away_ppg_allowed": compute_avg(away_allowed),
        "home_record": f"{home_wins}-{home_losses}",
        "away_record": f"{away_wins}-{away_losses}",

        # Quarter trends (scoring)
        "q1_ppg": compute_avg(q1_scored),
        "q2_ppg": compute_avg(q2_scored),
        "q3_ppg": compute_avg(q3_scored),
        "q4_ppg": compute_avg(q4_scored),
        "first_half_ppg": compute_avg(first_half_scored),
        "second_half_ppg": compute_avg(second_half_scored),

        # Quarter trends (allowed)
        "q1_ppg_allowed": compute_avg(q1_allowed),
        "q2_ppg_allowed": compute_avg(q2_allowed),
        "q3_ppg_allowed": compute_avg(q3_allowed),
        "q4_ppg_allowed": compute_avg(q4_allowed),
        "first_half_ppg_allowed": compute_avg(first_half_allowed),
        "second_half_ppg_allowed": compute_avg(second_half_allowed),

        # Recent form (last 5)
        "last_5_ppg": compute_avg(recent_scored),
        "last_5_ppg_allowed": compute_avg(recent_allowed),
        "last_5_record": f"{recent_wins}-{len(recent_games) - recent_wins}",
    }

    return stats


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2024"
    input_file = f"games-{year}.json"

    print(f"Computing team stats from {input_file}...")

    try:
        with open(input_file, "r", encoding="utf-8") as f:
            games = json.load(f)
    except FileNotFoundError:
        print(f"Error: {input_file} not found. Run fetch_games.py first.")
        sys.exit(1)

    # Compute stats for each team
    team_stats = []
    for team_code in TEAM_CODES:
        stats = compute_team_stats(games, team_code)
        if stats:
            stats["season"] = int(year)
            team_stats.append(stats)

    # Sort by point differential (best teams first)
    team_stats.sort(key=lambda t: -t["point_differential"])

    output_file = f"team-stats-{year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(team_stats, f, indent=2)

    print(f"Saved stats for {len(team_stats)} teams to {output_file}")

    # Print top 5 teams by point differential
    print("\nTop 5 teams by point differential:")
    for i, t in enumerate(team_stats[:5], 1):
        print(f"  {i}. {t['team_code']}: +{t['point_differential']} ({t['wins']}-{t['losses']})")


if __name__ == "__main__":
    main()
