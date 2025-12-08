#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Backtest betting model predictions against actual game results.

Usage: ./backtest_model.py [year]
  year defaults to 2024 (most recent complete season)

Reads: matchup-odds-{year}.json, games-{year}.json
Outputs: backtest-results-{year}.json

Metrics computed:
- Moneyline accuracy (pick winner)
- Spread cover accuracy
- Over/Under hit rate
- Calibration (are 60% predictions hitting 60%?)
- ROI simulation (flat betting)
- Value bet performance (edge > 5%)
"""
import json
import sys
from collections import defaultdict
from pathlib import Path


def load_data(year):
    """Load matchup odds and games for a season."""
    odds_file = Path(f"matchup-odds-{year}.json")
    games_file = Path(f"games-{year}.json")

    if not odds_file.exists():
        print(f"Error: {odds_file} not found")
        sys.exit(1)
    if not games_file.exists():
        print(f"Error: {games_file} not found")
        sys.exit(1)

    with open(odds_file, encoding="utf-8") as f:
        odds = json.load(f)

    with open(games_file, encoding="utf-8") as f:
        games = json.load(f)

    # Index games by (week, home_team)
    games_by_key = {}
    for g in games:
        if g.get("is_completed"):
            key = (g["week"], g["home_team"])
            games_by_key[key] = g

    return odds, games_by_key


def analyze_predictions(odds, games):
    """Analyze model predictions vs actual results."""
    results = {
        "total_games": 0,
        "moneyline": {"correct": 0, "wrong": 0, "push": 0},
        "spread": {"covered": 0, "not_covered": 0, "push": 0},
        "total": {"over": 0, "under": 0, "push": 0},
        "calibration_buckets": defaultdict(lambda: {"predicted": 0, "actual_wins": 0}),
        "value_bets": {"count": 0, "wins": 0, "edge_sum": 0},
        "roi": {"flat_ml": 0, "flat_spread": 0, "flat_total": 0, "units_wagered": 0},
        "by_week": {},
        "edge_performance": [],
    }

    for pred in odds:
        key = (pred["week"], pred["home_team"])
        game = games.get(key)

        if not game or not pred.get("is_completed"):
            continue

        results["total_games"] += 1

        home_score = game["home_score"]
        away_score = game["away_score"]
        actual_diff = home_score - away_score
        actual_total = home_score + away_score

        home_won = home_score > away_score
        home_win_prob = pred.get("home_win_prob", 0.5)
        predicted_home_win = home_win_prob > 0.5

        # Moneyline
        if home_score == away_score:
            results["moneyline"]["push"] += 1
        elif predicted_home_win == home_won:
            results["moneyline"]["correct"] += 1
        else:
            results["moneyline"]["wrong"] += 1

        # Spread
        spread = pred.get("spread", 0)
        home_margin_vs_spread = actual_diff + spread  # positive = covered

        if abs(home_margin_vs_spread) < 0.5:
            results["spread"]["push"] += 1
        elif home_margin_vs_spread > 0:
            results["spread"]["covered"] += 1
        else:
            results["spread"]["not_covered"] += 1

        # Over/Under
        ou_line = pred.get("over_under", 45)
        if abs(actual_total - ou_line) < 0.5:
            results["total"]["push"] += 1
        elif actual_total > ou_line:
            results["total"]["over"] += 1
        else:
            results["total"]["under"] += 1

        # Calibration buckets (group by predicted probability)
        bucket = int(home_win_prob * 10) * 10  # 0, 10, 20, ..., 90
        results["calibration_buckets"][bucket]["predicted"] += 1
        if home_won:
            results["calibration_buckets"][bucket]["actual_wins"] += 1

        # Value bet tracking (edge > 5%)
        # Calculate implied probability from moneyline
        home_ml = pred.get("home_moneyline", -110)
        if home_ml < 0:
            implied_prob = abs(home_ml) / (abs(home_ml) + 100)
        else:
            implied_prob = 100 / (home_ml + 100)

        edge = home_win_prob - implied_prob

        if abs(edge) > 0.05:
            results["value_bets"]["count"] += 1
            results["value_bets"]["edge_sum"] += abs(edge)

            # Did value bet win?
            bet_on_home = edge > 0
            if (bet_on_home and home_won) or (not bet_on_home and not home_won and home_score != away_score):
                results["value_bets"]["wins"] += 1

            results["edge_performance"].append({
                "week": pred["week"],
                "matchup": f"{pred['away_team']} @ {pred['home_team']}",
                "edge": round(edge * 100, 1),
                "bet_side": "home" if bet_on_home else "away",
                "won": (bet_on_home and home_won) or (not bet_on_home and not home_won and home_score != away_score),
                "predicted_prob": round(home_win_prob * 100, 1),
                "actual_margin": actual_diff,
            })

        # ROI simulation (flat $100 bets)
        results["roi"]["units_wagered"] += 1

        # Moneyline ROI
        if home_score != away_score:
            if predicted_home_win:
                if home_won:
                    # Win at home odds
                    if home_ml < 0:
                        results["roi"]["flat_ml"] += 100 * (100 / abs(home_ml))
                    else:
                        results["roi"]["flat_ml"] += home_ml
                else:
                    results["roi"]["flat_ml"] -= 100
            else:
                away_ml = pred.get("away_moneyline", 110)
                if not home_won:
                    if away_ml < 0:
                        results["roi"]["flat_ml"] += 100 * (100 / abs(away_ml))
                    else:
                        results["roi"]["flat_ml"] += away_ml
                else:
                    results["roi"]["flat_ml"] -= 100

        # Track by week
        week = pred["week"]
        if week not in results["by_week"]:
            results["by_week"][week] = {"games": 0, "ml_correct": 0, "spread_covered": 0}

        results["by_week"][week]["games"] += 1
        if predicted_home_win == home_won and home_score != away_score:
            results["by_week"][week]["ml_correct"] += 1
        if home_margin_vs_spread > 0:
            results["by_week"][week]["spread_covered"] += 1

    return results


def compute_summary(results):
    """Compute summary statistics."""
    total = results["total_games"]
    if total == 0:
        return {}

    ml = results["moneyline"]
    ml_decided = ml["correct"] + ml["wrong"]
    ml_accuracy = ml["correct"] / ml_decided if ml_decided > 0 else 0

    spread = results["spread"]
    spread_decided = spread["covered"] + spread["not_covered"]
    spread_accuracy = spread["covered"] / spread_decided if spread_decided > 0 else 0

    ou = results["total"]
    ou_decided = ou["over"] + ou["under"]

    # Calibration analysis
    calibration = []
    for bucket in sorted(results["calibration_buckets"].keys()):
        data = results["calibration_buckets"][bucket]
        if data["predicted"] > 0:
            actual_rate = data["actual_wins"] / data["predicted"]
            expected_rate = (bucket + 5) / 100  # midpoint of bucket
            calibration.append({
                "bucket": f"{bucket}-{bucket+10}%",
                "games": data["predicted"],
                "actual_win_rate": round(actual_rate * 100, 1),
                "expected_rate": round(expected_rate * 100, 1),
                "calibration_error": round((actual_rate - expected_rate) * 100, 1),
            })

    # Value bet summary
    vb = results["value_bets"]
    vb_win_rate = vb["wins"] / vb["count"] if vb["count"] > 0 else 0
    avg_edge = vb["edge_sum"] / vb["count"] if vb["count"] > 0 else 0

    # Top value bets by edge
    edge_sorted = sorted(results["edge_performance"], key=lambda x: abs(x["edge"]), reverse=True)[:10]

    summary = {
        "total_games": total,
        "moneyline_accuracy": round(ml_accuracy * 100, 1),
        "moneyline_record": f"{ml['correct']}-{ml['wrong']}",
        "spread_accuracy": round(spread_accuracy * 100, 1),
        "spread_record": f"{spread['covered']}-{spread['not_covered']}-{spread['push']}",
        "over_rate": round(ou["over"] / ou_decided * 100, 1) if ou_decided > 0 else 0,
        "under_rate": round(ou["under"] / ou_decided * 100, 1) if ou_decided > 0 else 0,
        "calibration": calibration,
        "value_bets": {
            "count": vb["count"],
            "win_rate": round(vb_win_rate * 100, 1),
            "avg_edge": round(avg_edge * 100, 1),
            "expected_if_calibrated": round((0.5 + avg_edge) * 100, 1) if avg_edge > 0 else 50,
        },
        "roi": {
            "units_wagered": results["roi"]["units_wagered"],
            "moneyline_profit": round(results["roi"]["flat_ml"], 2),
            "moneyline_roi": round(results["roi"]["flat_ml"] / (results["roi"]["units_wagered"] * 100) * 100, 1) if results["roi"]["units_wagered"] > 0 else 0,
        },
        "top_value_bets": edge_sorted,
        "weekly_breakdown": results["by_week"],
    }

    return summary


def print_report(summary, year):
    """Print formatted backtest report."""
    print(f"\n{'='*60}")
    print(f"  BACKTEST RESULTS - {year} SEASON")
    print(f"{'='*60}")

    print(f"\nTotal Games Analyzed: {summary['total_games']}")

    print(f"\n--- Prediction Accuracy ---")
    print(f"  Moneyline:  {summary['moneyline_accuracy']}% ({summary['moneyline_record']})")
    print(f"  Spread:     {summary['spread_accuracy']}% ({summary['spread_record']})")
    print(f"  Over Rate:  {summary['over_rate']}%")
    print(f"  Under Rate: {summary['under_rate']}%")

    print(f"\n--- ROI (Flat $100 Bets) ---")
    roi = summary["roi"]
    profit = roi["moneyline_profit"]
    profit_sign = "+" if profit >= 0 else ""
    print(f"  Moneyline:  {profit_sign}${profit:.2f} ({roi['moneyline_roi']:+.1f}% ROI)")

    print(f"\n--- Value Bets (Edge > 5%) ---")
    vb = summary["value_bets"]
    print(f"  Found:      {vb['count']} bets")
    print(f"  Win Rate:   {vb['win_rate']}%")
    print(f"  Avg Edge:   {vb['avg_edge']}%")

    print(f"\n--- Calibration ---")
    for cal in summary["calibration"]:
        if cal["games"] >= 5:  # Only show buckets with enough data
            print(f"  {cal['bucket']:>10}: {cal['actual_win_rate']:>5.1f}% actual (expected {cal['expected_rate']:.0f}%), n={cal['games']}")

    if summary["top_value_bets"]:
        print(f"\n--- Top Value Bets ---")
        for bet in summary["top_value_bets"][:5]:
            result = "W" if bet["won"] else "L"
            print(f"  Wk{bet['week']:>2} {bet['matchup']:<15} {bet['bet_side']:>4} {bet['edge']:+.1f}% edge [{result}]")

    print(f"\n{'='*60}\n")


def main():
    year = sys.argv[1] if len(sys.argv) > 1 else "2024"

    print(f"Backtesting model for {year} season...")

    odds, games = load_data(year)
    results = analyze_predictions(odds, games)
    summary = compute_summary(results)

    if summary:
        print_report(summary, year)

        # Save results
        output = {
            "season": int(year),
            "summary": summary,
            "raw_results": {
                "total_games": results["total_games"],
                "moneyline": results["moneyline"],
                "spread": results["spread"],
                "total": results["total"],
            },
        }

        output_file = f"backtest-results-{year}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)
        print(f"Saved detailed results to {output_file}")
    else:
        print("No completed games with predictions found.")


if __name__ == "__main__":
    main()
