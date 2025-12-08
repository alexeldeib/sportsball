#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Compute advanced team statistics for improved predictions.

Usage: ./compute_advanced_stats.py [year]
  year defaults to 2025

Computes:
- Strength of Schedule (SOS): average opponent win %
- Simple Rating System (SRS): PPD + SOS
- Team-specific home field advantage
- Merges with ESPN efficiency stats

Outputs: advanced-team-stats-{year}.json
"""
import json
import sqlite3
import sys
from collections import defaultdict
from datetime import datetime

DB_PATH = "nfl.db"


def get_team_records(conn, season: int) -> dict:
    """Get win-loss records for each team."""
    cursor = conn.cursor()

    # Get completed games
    cursor.execute("""
        SELECT home_team, away_team, home_score, away_score
        FROM games
        WHERE season = ? AND is_completed = 1
    """, (season,))

    records = defaultdict(lambda: {"wins": 0, "losses": 0, "ties": 0,
                                   "pf": 0, "pa": 0, "opponents": []})

    for home, away, home_score, away_score in cursor.fetchall():
        if home_score is None or away_score is None:
            continue

        # Home team
        records[home]["pf"] += home_score
        records[home]["pa"] += away_score
        records[home]["opponents"].append(away)

        # Away team
        records[away]["pf"] += away_score
        records[away]["pa"] += home_score
        records[away]["opponents"].append(home)

        if home_score > away_score:
            records[home]["wins"] += 1
            records[away]["losses"] += 1
        elif away_score > home_score:
            records[away]["wins"] += 1
            records[home]["losses"] += 1
        else:
            records[home]["ties"] += 1
            records[away]["ties"] += 1

    return dict(records)


def compute_win_pct(record: dict) -> float:
    """Compute win percentage (ties count as 0.5)."""
    total = record["wins"] + record["losses"] + record["ties"]
    if total == 0:
        return 0.5
    return (record["wins"] + 0.5 * record["ties"]) / total


def compute_sos(records: dict) -> dict:
    """Compute Strength of Schedule for each team."""
    # First pass: get each team's win %
    win_pcts = {team: compute_win_pct(rec) for team, rec in records.items()}

    # Second pass: SOS = average opponent win %
    sos = {}
    for team, rec in records.items():
        if not rec["opponents"]:
            sos[team] = 0.5
            continue
        opp_win_pcts = [win_pcts.get(opp, 0.5) for opp in rec["opponents"]]
        sos[team] = sum(opp_win_pcts) / len(opp_win_pcts)

    return sos


def compute_srs(records: dict, sos: dict, iterations: int = 20) -> dict:
    """
    Compute Simple Rating System iteratively.

    SRS = Point Differential per Game + SOS_adjusted

    This uses an iterative approach where SOS is adjusted based on
    opponent SRS values.
    """
    teams = list(records.keys())

    # Initialize with point differential per game
    ppd = {}
    for team, rec in records.items():
        games = rec["wins"] + rec["losses"] + rec["ties"]
        if games > 0:
            ppd[team] = (rec["pf"] - rec["pa"]) / games
        else:
            ppd[team] = 0

    # SRS starts at PPD
    srs = ppd.copy()

    # Iterate to convergence
    for _ in range(iterations):
        new_srs = {}
        for team in teams:
            rec = records[team]
            if not rec["opponents"]:
                new_srs[team] = ppd[team]
                continue

            # Average opponent SRS
            opp_srs = sum(srs.get(opp, 0) for opp in rec["opponents"]) / len(rec["opponents"])
            new_srs[team] = ppd[team] + opp_srs

        srs = new_srs

    return srs


def compute_home_field_advantage(conn, min_games: int = 20) -> dict:
    """
    Compute team-specific home field advantage from historical games.

    Returns HFA in points (positive = plays better at home).
    """
    cursor = conn.cursor()

    # Get home vs away performance for each team (all seasons)
    cursor.execute("""
        SELECT
            home_team,
            AVG(home_score - away_score) as home_margin,
            COUNT(*) as home_games
        FROM games
        WHERE is_completed = 1 AND home_score IS NOT NULL
        GROUP BY home_team
    """)

    home_margins = {}
    for team, margin, games in cursor.fetchall():
        if games >= min_games:
            home_margins[team] = {"margin": margin, "games": games}

    # Get each team's away margin
    cursor.execute("""
        SELECT
            away_team,
            AVG(away_score - home_score) as away_margin,
            COUNT(*) as away_games
        FROM games
        WHERE is_completed = 1 AND away_score IS NOT NULL
        GROUP BY away_team
    """)

    away_margins = {}
    for team, margin, games in cursor.fetchall():
        if games >= min_games:
            away_margins[team] = {"margin": margin, "games": games}

    # HFA = how much better at home vs away
    # A positive value means team is better at home
    hfa = {}
    for team in home_margins:
        if team in away_margins:
            home_perf = home_margins[team]["margin"]
            away_perf = away_margins[team]["margin"]
            # Home margin - away margin gives HFA
            hfa[team] = (home_perf - away_perf) / 2

    return hfa


def load_espn_stats(year: int) -> dict:
    """Load ESPN stats if available."""
    try:
        with open(f"espn-team-stats-{year}.json") as f:
            data = json.load(f)
            return {team["team_code"]: team for team in data}
    except FileNotFoundError:
        return {}


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2025

    print(f"Computing advanced stats for {year}...")

    conn = sqlite3.connect(DB_PATH)

    # Get team records
    print("  Calculating team records...")
    records = get_team_records(conn, year)

    if not records:
        print(f"  No games found for {year}!")
        return

    # Compute SOS
    print("  Computing Strength of Schedule...")
    sos = compute_sos(records)

    # Compute SRS
    print("  Computing Simple Rating System...")
    srs = compute_srs(records, sos)

    # Compute team-specific HFA
    print("  Computing Home Field Advantage...")
    hfa = compute_home_field_advantage(conn)

    # Load ESPN stats
    print("  Loading ESPN efficiency stats...")
    espn_stats = load_espn_stats(year)

    # Merge all stats
    print("  Merging stats...")
    all_stats = []

    for team, rec in records.items():
        games = rec["wins"] + rec["losses"] + rec["ties"]
        win_pct = compute_win_pct(rec)
        ppd = (rec["pf"] - rec["pa"]) / games if games > 0 else 0

        team_stats = {
            "team_code": team,
            "season": year,
            "wins": rec["wins"],
            "losses": rec["losses"],
            "ties": rec["ties"],
            "games_played": games,
            "win_pct": round(win_pct, 3),
            "points_for": rec["pf"],
            "points_against": rec["pa"],
            "ppd": round(ppd, 2),  # Point differential per game
            "sos": round(sos.get(team, 0.5), 3),
            "srs": round(srs.get(team, 0), 2),
            "hfa": round(hfa.get(team, 2.5), 2),  # Default 2.5 if not enough data
            "computed_at": datetime.now().isoformat(),
        }

        # Add ESPN efficiency stats if available
        if team in espn_stats:
            espn = espn_stats[team]
            team_stats.update({
                "yards_per_play": round(espn.get("yardsPerPlay", 0), 3),
                "yards_per_pass_attempt": round(espn.get("yardsPerPassAttempt", 0), 3),
                "yards_per_rush_attempt": round(espn.get("yardsPerRushAttempt", 0), 3),
                "completion_pct": round(espn.get("completionPct", 0), 1),
                "turnover_diff": espn.get("turnoverDifferential", 0),
                "third_down_pct": round(espn.get("thirdDownConvPct", 0), 1),
                "red_zone_pct": round(espn.get("redZoneScoringPct", 0), 1) if espn.get("redZoneScoringPct") else None,
                "qb_rating": round(espn.get("QBRating", 0), 1),
                "sacks_taken": espn.get("sacks", 0),
            })

        all_stats.append(team_stats)

    conn.close()

    # Sort by SRS
    all_stats.sort(key=lambda x: x["srs"], reverse=True)

    # Save output
    output_file = f"advanced-team-stats-{year}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_stats, f, indent=2)
    print(f"\nSaved {len(all_stats)} teams to {output_file}")

    # Print power rankings
    print("\n=== Power Rankings (by SRS) ===")
    for i, t in enumerate(all_stats[:10], 1):
        sos_str = f"+{t['sos']:.3f}" if t['sos'] > 0.5 else f"{t['sos']:.3f}"
        print(f"  {i:2}. {t['team_code']:3} SRS:{t['srs']:+6.1f} "
              f"({t['wins']}-{t['losses']}) SOS:{sos_str}")

    # Print HFA leaders
    print("\n=== Home Field Advantage ===")
    hfa_sorted = sorted(all_stats, key=lambda x: x.get("hfa", 0), reverse=True)
    print("  Best home teams:")
    for t in hfa_sorted[:5]:
        print(f"    {t['team_code']}: +{t['hfa']:.1f} pts at home")
    print("  Worst home teams:")
    for t in hfa_sorted[-5:]:
        print(f"    {t['team_code']}: +{t['hfa']:.1f} pts at home")

    # Print efficiency leaders if ESPN data available
    if any(t.get("yards_per_play") for t in all_stats):
        print("\n=== Efficiency Leaders ===")
        ypp_sorted = sorted(all_stats, key=lambda x: x.get("yards_per_play", 0), reverse=True)
        print("  Yards per play:")
        for t in ypp_sorted[:5]:
            print(f"    {t['team_code']}: {t.get('yards_per_play', 0):.2f}")


if __name__ == "__main__":
    main()
