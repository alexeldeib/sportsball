#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Construct betting odds from team statistics.
Usage: ./build_odds.py [year] [--week N]
  year defaults to 2024
  --week N: only generate odds for week N (default: all upcoming weeks)

Reads: team-stats-{year}.json, games-{year}.json
Outputs: matchup-odds-{year}.json
"""
import json
import math
import sys
from datetime import datetime

HOME_FIELD_ADVANTAGE = 2.5  # Points
NFL_STD_DEV = 13.5  # Standard deviation of NFL game margins
LOGISTIC_K = 0.145  # Calibration constant for win probability
VIG_PERCENT = 0.0476  # Standard juice (~4.76% = -110/-110)


def prob_to_american_odds(prob):
    """Convert win probability to American odds format."""
    if prob <= 0:
        return 10000  # Max underdog
    if prob >= 1:
        return -10000  # Max favorite

    if prob >= 0.5:
        # Favorite: negative odds
        return round(-100 * prob / (1 - prob))
    else:
        # Underdog: positive odds
        return round(100 * (1 - prob) / prob)


def apply_vig(fair_prob, vig=VIG_PERCENT):
    """Apply vigorish to probability and convert to odds."""
    # Inflate probability to account for vig
    adjusted = fair_prob * (1 + vig)
    adjusted = min(adjusted, 0.99)  # Cap at 99%
    return prob_to_american_odds(adjusted)


def calculate_power_rating(team_stats):
    """Calculate team power rating from stats."""
    if not team_stats:
        return 0.0

    ppg = team_stats.get("ppg_scored", 21.0)
    ppg_allowed = team_stats.get("ppg_allowed", 21.0)

    # Base power rating is point differential
    base = ppg - ppg_allowed

    # Weight recent form slightly more
    last_5_ppg = team_stats.get("last_5_ppg", ppg)
    last_5_allowed = team_stats.get("last_5_ppg_allowed", ppg_allowed)
    recent_diff = last_5_ppg - last_5_allowed

    # Blend: 70% season, 30% recent
    power = 0.7 * base + 0.3 * recent_diff

    return power


def calculate_matchup_odds(home_stats, away_stats):
    """Calculate full odds for a matchup."""
    home_power = calculate_power_rating(home_stats)
    away_power = calculate_power_rating(away_stats)

    # Expected point differential (home perspective)
    expected_diff = (home_power - away_power) + HOME_FIELD_ADVANTAGE

    # Win probability using logistic function
    home_win_prob = 1 / (1 + math.exp(-LOGISTIC_K * expected_diff))

    # Moneyline odds with vig
    home_ml = apply_vig(home_win_prob)
    away_ml = apply_vig(1 - home_win_prob)

    # Spread (round to nearest 0.5) - negative means home favored
    spread = -round(expected_diff * 2) / 2

    # Over/Under calculation
    home_ppg = home_stats.get("ppg_scored", 21.0) if home_stats else 21.0
    away_ppg = away_stats.get("ppg_scored", 21.0) if away_stats else 21.0
    home_allowed = home_stats.get("ppg_allowed", 21.0) if home_stats else 21.0
    away_allowed = away_stats.get("ppg_allowed", 21.0) if away_stats else 21.0

    # Method: average of both offense vs defense matchups
    method1 = home_ppg + away_allowed  # Home offense vs away defense
    method2 = away_ppg + home_allowed  # Away offense vs home defense
    total = (method1 + method2) / 2

    # Round to nearest 0.5
    total = round(total * 2) / 2

    # Team totals
    home_total = round(((home_ppg + away_allowed) / 2 + 1.25) * 2) / 2  # +1.25 home boost
    away_total = round(((away_ppg + home_allowed) / 2 - 1.25) * 2) / 2  # -1.25 away penalty

    return {
        "home_win_prob": round(home_win_prob, 3),
        "away_win_prob": round(1 - home_win_prob, 3),
        "home_moneyline": home_ml,
        "away_moneyline": away_ml,
        "spread": spread,  # Negative = home favored
        "spread_home_odds": -110,
        "spread_away_odds": -110,
        "over_under": total,
        "over_odds": -110,
        "under_odds": -110,
        "home_team_total": home_total,
        "away_team_total": away_total,
        "expected_diff": round(expected_diff, 1),
    }


def main():
    # Parse arguments
    year = "2024"
    target_week = None

    args = sys.argv[1:]
    i = 0
    while i < len(args):
        if args[i] == "--week" and i + 1 < len(args):
            target_week = int(args[i + 1])
            i += 2
        elif not args[i].startswith("-"):
            year = args[i]
            i += 1
        else:
            i += 1

    games_file = f"games-{year}.json"
    stats_file = f"team-stats-{year}.json"

    print(f"Building odds from {stats_file} and {games_file}...")

    # Load data
    try:
        with open(games_file, "r", encoding="utf-8") as f:
            games = json.load(f)
    except FileNotFoundError:
        print(f"Error: {games_file} not found. Run fetch_games.py first.")
        sys.exit(1)

    try:
        with open(stats_file, "r", encoding="utf-8") as f:
            team_stats_list = json.load(f)
    except FileNotFoundError:
        print(f"Error: {stats_file} not found. Run compute_team_stats.py first.")
        sys.exit(1)

    # Convert team stats to dict
    team_stats = {t["team_code"]: t for t in team_stats_list}

    # Find games to generate odds for
    if target_week:
        target_games = [g for g in games if g["week"] == target_week]
    else:
        # All games (both completed and upcoming for reference)
        target_games = games

    if not target_games:
        print(f"No games found for week {target_week}" if target_week else "No games found")
        sys.exit(1)

    # Generate odds for each matchup
    matchup_odds = []
    computed_at = datetime.now().isoformat()

    for game in target_games:
        home_team = game["home_team"]
        away_team = game["away_team"]

        home_stats = team_stats.get(home_team)
        away_stats = team_stats.get(away_team)

        odds = calculate_matchup_odds(home_stats, away_stats)

        matchup = {
            "season": int(year),
            "week": game["week"],
            "game_date": game.get("game_date"),
            "home_team": home_team,
            "away_team": away_team,
            "is_completed": game.get("is_completed", False),
            **odds,
            "computed_at": computed_at,
        }

        # If game is completed, add actual results for comparison
        if game.get("is_completed"):
            matchup["actual_home_score"] = game.get("home_score")
            matchup["actual_away_score"] = game.get("away_score")
            matchup["actual_total"] = game.get("total_points")
            actual_diff = game.get("home_score", 0) - game.get("away_score", 0)
            matchup["actual_diff"] = actual_diff

            # Did home team cover the spread?
            # spread is negative when home favored (e.g., -5 means home must win by 5+)
            # actual_diff + spread > 0 means home covered
            margin = actual_diff + odds["spread"]
            matchup["spread_result"] = "push" if margin == 0 else (
                "cover" if margin > 0 else "miss"
            )
            matchup["total_result"] = "push" if game.get("total_points") == odds["over_under"] else (
                "over" if game.get("total_points", 0) > odds["over_under"] else "under"
            )

        matchup_odds.append(matchup)

    # Sort by week, then date
    matchup_odds.sort(key=lambda m: (m["week"], m.get("game_date", "")))

    output_file = f"matchup-odds-{year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(matchup_odds, f, indent=2)

    # Summary
    completed = sum(1 for m in matchup_odds if m.get("is_completed"))
    upcoming = len(matchup_odds) - completed

    print(f"Saved {len(matchup_odds)} matchup odds to {output_file}")
    print(f"  - {completed} completed games (with results)")
    print(f"  - {upcoming} upcoming games")

    # Show sample
    if matchup_odds:
        # Find an upcoming game or last completed
        sample = next((m for m in reversed(matchup_odds) if not m.get("is_completed")), matchup_odds[-1])
        print(f"\nSample: Week {sample['week']} - {sample['away_team']} @ {sample['home_team']}")
        print(f"  Moneyline: {sample['home_team']} {sample['home_moneyline']:+d} / {sample['away_team']} {sample['away_moneyline']:+d}")
        print(f"  Spread: {sample['home_team']} {sample['spread']:+.1f}")
        print(f"  O/U: {sample['over_under']}")


if __name__ == "__main__":
    main()
