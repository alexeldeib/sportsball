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

Advanced features:
- Scoring variance (std deviation)
- Consistency score
- EMA (exponential moving average)
- Changepoint detection
- Margin analysis
- Cover rate calculations
"""
import json
import math
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


def compute_std(values):
    """Compute standard deviation."""
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    variance = sum((x - avg) ** 2 for x in values) / len(values)
    return round(math.sqrt(variance), 2)


def compute_ema(values, alpha=0.3):
    """Compute exponential moving average with alpha decay.

    Higher alpha = more weight on recent values.
    Returns the final EMA value.
    """
    if not values:
        return 0.0
    ema = values[0]
    for v in values[1:]:
        ema = alpha * v + (1 - alpha) * ema
    return round(ema, 2)


def compute_ema_series(values, alpha=0.3):
    """Compute EMA series (returns list of all EMA values)."""
    if not values:
        return []
    result = [values[0]]
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return [round(x, 2) for x in result]


def detect_changepoint(values, window=3, threshold=5.0):
    """Detect if recent performance differs significantly from prior.

    Returns: (has_changepoint, direction, magnitude)
    direction: 'up', 'down', or None
    """
    if len(values) < window * 2:
        return (False, None, 0)

    recent = sum(values[-window:]) / window
    prior = sum(values[-window*2:-window]) / window
    diff = recent - prior

    if abs(diff) >= threshold:
        direction = 'up' if diff > 0 else 'down'
        return (True, direction, round(diff, 1))
    return (False, None, 0)


def compute_consistency(values):
    """Compute consistency score (0-100, higher = more consistent).

    Based on coefficient of variation inverted.
    """
    if len(values) < 2:
        return 100.0
    avg = sum(values) / len(values)
    if avg == 0:
        return 0.0
    std = compute_std(values)
    cv = std / avg  # coefficient of variation
    # Invert and scale: CV of 0 = 100, CV of 0.5 = 50, CV of 1+ = 0
    consistency = max(0, min(100, 100 * (1 - cv)))
    return round(consistency, 1)


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

    # === Advanced Analytics ===

    # Variance and consistency metrics
    stats["scoring_std_dev"] = compute_std(points_scored)
    stats["allowed_std_dev"] = compute_std(points_allowed)
    stats["scoring_consistency"] = compute_consistency(points_scored)

    # Margin analysis
    margins = [s - a for s, a in zip(points_scored, points_allowed)]
    stats["avg_margin"] = compute_avg(margins)
    stats["margin_std_dev"] = compute_std(margins)

    # Close games (decided by 7 or fewer points)
    close_games = [m for m in margins if abs(m) <= 7]
    stats["close_game_pct"] = round(len(close_games) / len(margins) * 100, 1) if margins else 0
    close_wins = len([m for m in close_games if m > 0])
    stats["close_game_record"] = f"{close_wins}-{len(close_games) - close_wins}"

    # Blowout rate (won/lost by 14+)
    blowout_wins = len([m for m in margins if m >= 14])
    blowout_losses = len([m for m in margins if m <= -14])
    stats["blowout_win_pct"] = round(blowout_wins / len(team_games) * 100, 1)
    stats["blowout_loss_pct"] = round(blowout_losses / len(team_games) * 100, 1)

    # Total points analysis (for O/U)
    total_points = [s + a for s, a in zip(points_scored, points_allowed)]
    stats["avg_total_points"] = compute_avg(total_points)
    stats["total_points_std_dev"] = compute_std(total_points)

    # EMA-based trends (more weight on recent games)
    sorted_games = sorted(team_games, key=lambda g: (g["week"], g["game_date"]))
    game_scored_ordered = []
    game_allowed_ordered = []
    for g in sorted_games:
        is_home = g["home_team"] == team_code
        if is_home:
            game_scored_ordered.append(g["home_score"])
            game_allowed_ordered.append(g["away_score"])
        else:
            game_scored_ordered.append(g["away_score"])
            game_allowed_ordered.append(g["home_score"])

    stats["ema_ppg"] = compute_ema(game_scored_ordered, alpha=0.3)
    stats["ema_ppg_allowed"] = compute_ema(game_allowed_ordered, alpha=0.3)
    stats["ema_differential"] = round(stats["ema_ppg"] - stats["ema_ppg_allowed"], 2)

    # Changepoint detection (significant shift in performance)
    has_cp, cp_dir, cp_mag = detect_changepoint(game_scored_ordered)
    stats["scoring_changepoint"] = has_cp
    stats["scoring_changepoint_direction"] = cp_dir
    stats["scoring_changepoint_magnitude"] = cp_mag

    # Trend indicators
    if len(game_scored_ordered) >= 4:
        first_half_avg = sum(game_scored_ordered[:len(game_scored_ordered)//2]) / (len(game_scored_ordered)//2)
        second_half_avg = sum(game_scored_ordered[len(game_scored_ordered)//2:]) / (len(game_scored_ordered) - len(game_scored_ordered)//2)
        stats["season_trend"] = round(second_half_avg - first_half_avg, 1)
        stats["season_trend_direction"] = "up" if stats["season_trend"] > 2 else "down" if stats["season_trend"] < -2 else "flat"
    else:
        stats["season_trend"] = 0
        stats["season_trend_direction"] = "flat"

    # Quarter differential strength (identifies fast starters vs closers)
    stats["q1_differential"] = round(stats["q1_ppg"] - stats["q1_ppg_allowed"], 1)
    stats["q4_differential"] = round(stats["q4_ppg"] - stats["q4_ppg_allowed"], 1)
    stats["first_half_differential"] = round(stats["first_half_ppg"] - stats["first_half_ppg_allowed"], 1)
    stats["second_half_differential"] = round(stats["second_half_ppg"] - stats["second_half_ppg_allowed"], 1)

    # Identify team profile
    if stats["first_half_differential"] > stats["second_half_differential"] + 2:
        stats["game_profile"] = "fast_starter"
    elif stats["second_half_differential"] > stats["first_half_differential"] + 2:
        stats["game_profile"] = "closer"
    else:
        stats["game_profile"] = "balanced"

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
