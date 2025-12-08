#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Compute head-to-head statistics between all NFL team pairs.
Reads games-{year}.json files and outputs head-to-head.json

Usage: ./compute_head_to_head.py
"""
import json
from collections import defaultdict
from pathlib import Path


def load_all_games():
    """Load games from all available season files."""
    all_games = []

    for year in range(2020, 2026):
        filepath = Path(f"games-{year}.json")
        if filepath.exists():
            with open(filepath, encoding="utf-8") as f:
                games = json.load(f)
                # Only include completed games with scores
                completed = [g for g in games if g.get("is_completed") and g.get("home_score") is not None]
                all_games.extend(completed)
                print(f"  Loaded {len(completed)} completed games from {filepath}")

    print(f"Total: {len(all_games)} completed games")
    return all_games


def compute_h2h_stats(games):
    """Compute head-to-head statistics for all team pairs."""
    # Key: tuple(sorted([team1, team2])) -> list of game results
    matchups = defaultdict(list)

    for game in games:
        home = game["home_team"]
        away = game["away_team"]
        home_score = game["home_score"]
        away_score = game["away_score"]

        # Normalize key so team order is consistent
        key = tuple(sorted([home, away]))

        matchups[key].append({
            "home_team": home,
            "away_team": away,
            "home_score": home_score,
            "away_score": away_score,
            "total_points": home_score + away_score,
            "season": game.get("season"),
            "week": game.get("week"),
            "game_date": game.get("game_date"),
        })

    # Compute stats for each pair
    h2h_stats = []

    for (team1, team2), games_list in matchups.items():
        # Sort by date descending for last meeting
        games_list.sort(key=lambda g: (g["season"], g["week"]), reverse=True)

        team1_wins = 0
        team2_wins = 0
        team1_points = 0
        team2_points = 0
        total_points_sum = 0

        for g in games_list:
            if g["home_team"] == team1:
                team1_pts = g["home_score"]
                team2_pts = g["away_score"]
            else:
                team1_pts = g["away_score"]
                team2_pts = g["home_score"]

            team1_points += team1_pts
            team2_points += team2_pts
            total_points_sum += g["total_points"]

            if team1_pts > team2_pts:
                team1_wins += 1
            else:
                team2_wins += 1

        n = len(games_list)
        last_game = games_list[0]

        # Determine last meeting winner
        if last_game["home_team"] == team1:
            last_winner = team1 if last_game["home_score"] > last_game["away_score"] else team2
            last_score = f"{last_game['home_score']}-{last_game['away_score']}"
        else:
            last_winner = team1 if last_game["away_score"] > last_game["home_score"] else team2
            last_score = f"{last_game['away_score']}-{last_game['home_score']}"

        h2h_stats.append({
            "team1": team1,
            "team2": team2,
            "total_games": n,
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "team1_ppg": round(team1_points / n, 1),
            "team2_ppg": round(team2_points / n, 1),
            "avg_total_points": round(total_points_sum / n, 1),
            "last_meeting_season": last_game["season"],
            "last_meeting_week": last_game["week"],
            "last_meeting_date": last_game["game_date"],
            "last_meeting_winner": last_winner,
            "last_meeting_score": last_score,
        })

    # Sort by team1, team2 for consistent output
    h2h_stats.sort(key=lambda x: (x["team1"], x["team2"]))

    return h2h_stats


def main():
    print("Computing head-to-head statistics...")

    games = load_all_games()
    h2h_stats = compute_h2h_stats(games)

    print(f"\nComputed H2H stats for {len(h2h_stats)} team pairs")

    # Save to JSON
    output_file = "head-to-head.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(h2h_stats, f, indent=2)

    print(f"Saved to {output_file}")

    # Show some interesting stats
    print("\n--- Sample H2H matchups ---")

    # Find most games played
    most_games = max(h2h_stats, key=lambda x: x["total_games"])
    print(f"Most games: {most_games['team1']} vs {most_games['team2']} ({most_games['total_games']} games)")

    # Find highest scoring rivalry
    highest_scoring = max(h2h_stats, key=lambda x: x["avg_total_points"])
    print(f"Highest scoring: {highest_scoring['team1']} vs {highest_scoring['team2']} ({highest_scoring['avg_total_points']} PPG)")

    # Find most lopsided
    most_lopsided = max(h2h_stats, key=lambda x: abs(x["team1_wins"] - x["team2_wins"]))
    dominant = most_lopsided["team1"] if most_lopsided["team1_wins"] > most_lopsided["team2_wins"] else most_lopsided["team2"]
    record = f"{max(most_lopsided['team1_wins'], most_lopsided['team2_wins'])}-{min(most_lopsided['team1_wins'], most_lopsided['team2_wins'])}"
    print(f"Most lopsided: {dominant} vs opponent ({record})")


if __name__ == "__main__":
    main()
