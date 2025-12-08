#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Convert all JSON data files to SQLite database.
Usage: ./to_sqlite.py [--db output.db]

Imports:
  - players-with-stats-*.json → players table
  - games-*.json → games table
  - team-stats-*.json → team_stats table
  - player-weekly-stats-*.json → player_weekly_stats table
  - matchup-odds-*.json → matchup_odds table
"""
import json
import sqlite3
import sys
import re
from pathlib import Path


def extract_year_from_filename(filename):
    """Extract year from filename like 'players-with-stats-2025.json'."""
    match = re.search(r'(\d{4})', str(filename))
    return int(match.group(1)) if match else None


def get_all_stat_keys(players):
    """Collect all unique stat keys across all players."""
    keys = set()
    for p in players:
        if "stats" in p:
            keys.update(p["stats"].keys())
    return sorted(keys)


# ============ Players Table ============

def create_players_table(conn, stat_keys):
    """Create players table with all stat columns."""
    columns = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "team TEXT NOT NULL",
        "team_code TEXT",
        "position TEXT NOT NULL",
        "number INTEGER",
        "year INTEGER",
    ]
    for key in stat_keys:
        columns.append(f"{key} REAL")

    conn.execute("DROP TABLE IF EXISTS players")
    conn.execute(f"CREATE TABLE players ({', '.join(columns)})")
    conn.commit()


def insert_players(conn, players, stat_keys, year):
    """Insert players into database."""
    base_cols = ["name", "team", "team_code", "position", "number", "year"]
    all_cols = base_cols + stat_keys
    placeholders = ", ".join(["?"] * len(all_cols))
    sql = f"INSERT INTO players ({', '.join(all_cols)}) VALUES ({placeholders})"

    rows = []
    for p in players:
        stats = p.get("stats", {})
        row = [p["name"], p["team"], p.get("team_code"), p["position"], p.get("number"), year]
        for key in stat_keys:
            row.append(stats.get(key))
        rows.append(row)

    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ============ Games Table ============

def create_games_table(conn):
    """Create games table for game scores."""
    conn.execute("DROP TABLE IF EXISTS games")
    conn.execute("""
        CREATE TABLE games (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            game_date TEXT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            home_score INTEGER,
            away_score INTEGER,
            total_points INTEGER,
            home_q1 INTEGER, home_q2 INTEGER, home_q3 INTEGER, home_q4 INTEGER, home_ot INTEGER,
            away_q1 INTEGER, away_q2 INTEGER, away_q3 INTEGER, away_q4 INTEGER, away_ot INTEGER,
            home_1h INTEGER, home_2h INTEGER,
            away_1h INTEGER, away_2h INTEGER,
            is_completed INTEGER DEFAULT 0
        )
    """)
    conn.commit()


def insert_games(conn, games):
    """Insert games into database."""
    cols = [
        "season", "week", "game_date", "home_team", "away_team",
        "home_score", "away_score", "total_points",
        "home_q1", "home_q2", "home_q3", "home_q4", "home_ot",
        "away_q1", "away_q2", "away_q3", "away_q4", "away_ot",
        "home_1h", "home_2h", "away_1h", "away_2h", "is_completed"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT INTO games ({', '.join(cols)}) VALUES ({placeholders})"

    rows = []
    for g in games:
        row = [
            g.get("season"), g.get("week"), g.get("game_date"),
            g.get("home_team"), g.get("away_team"),
            g.get("home_score"), g.get("away_score"), g.get("total_points"),
            g.get("home_q1"), g.get("home_q2"), g.get("home_q3"), g.get("home_q4"), g.get("home_ot"),
            g.get("away_q1"), g.get("away_q2"), g.get("away_q3"), g.get("away_q4"), g.get("away_ot"),
            g.get("home_1h"), g.get("home_2h"), g.get("away_1h"), g.get("away_2h"),
            1 if g.get("is_completed") else 0
        ]
        rows.append(row)

    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ============ Team Stats Table ============

def create_team_stats_table(conn):
    """Create team_stats table for aggregated team statistics."""
    conn.execute("DROP TABLE IF EXISTS team_stats")
    conn.execute("""
        CREATE TABLE team_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            team_code TEXT NOT NULL,
            season INTEGER NOT NULL,
            games_played INTEGER,
            wins INTEGER, losses INTEGER, ties INTEGER,
            win_pct REAL,
            total_points_scored INTEGER,
            total_points_allowed INTEGER,
            ppg_scored REAL,
            ppg_allowed REAL,
            point_differential REAL,
            home_games INTEGER, away_games INTEGER,
            home_ppg REAL, away_ppg REAL,
            home_ppg_allowed REAL, away_ppg_allowed REAL,
            home_record TEXT, away_record TEXT,
            q1_ppg REAL, q2_ppg REAL, q3_ppg REAL, q4_ppg REAL,
            first_half_ppg REAL, second_half_ppg REAL,
            q1_ppg_allowed REAL, q2_ppg_allowed REAL, q3_ppg_allowed REAL, q4_ppg_allowed REAL,
            first_half_ppg_allowed REAL, second_half_ppg_allowed REAL,
            last_5_ppg REAL, last_5_ppg_allowed REAL, last_5_record TEXT,
            UNIQUE(team_code, season)
        )
    """)
    conn.commit()


def insert_team_stats(conn, stats_list):
    """Insert team stats into database."""
    cols = [
        "team_code", "season", "games_played", "wins", "losses", "ties", "win_pct",
        "total_points_scored", "total_points_allowed", "ppg_scored", "ppg_allowed", "point_differential",
        "home_games", "away_games", "home_ppg", "away_ppg", "home_ppg_allowed", "away_ppg_allowed",
        "home_record", "away_record",
        "q1_ppg", "q2_ppg", "q3_ppg", "q4_ppg", "first_half_ppg", "second_half_ppg",
        "q1_ppg_allowed", "q2_ppg_allowed", "q3_ppg_allowed", "q4_ppg_allowed",
        "first_half_ppg_allowed", "second_half_ppg_allowed",
        "last_5_ppg", "last_5_ppg_allowed", "last_5_record"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT OR REPLACE INTO team_stats ({', '.join(cols)}) VALUES ({placeholders})"

    rows = []
    for t in stats_list:
        row = [t.get(c) for c in cols]
        rows.append(row)

    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ============ Player Weekly Stats Table ============

def create_player_weekly_stats_table(conn, stat_keys):
    """Create player_weekly_stats table for week-by-week stats."""
    columns = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "player_id TEXT NOT NULL",
        "player_name TEXT NOT NULL",
        "team TEXT NOT NULL",
        "position TEXT",
        "opponent TEXT",
        "season INTEGER NOT NULL",
        "week INTEGER NOT NULL",
    ]
    for key in stat_keys:
        columns.append(f"{key} REAL")

    conn.execute("DROP TABLE IF EXISTS player_weekly_stats")
    conn.execute(f"CREATE TABLE player_weekly_stats ({', '.join(columns)})")
    conn.commit()


def insert_player_weekly_stats(conn, stats_list, stat_keys):
    """Insert weekly stats into database."""
    base_cols = ["player_id", "player_name", "team", "position", "opponent", "season", "week"]
    all_cols = base_cols + stat_keys
    placeholders = ", ".join(["?"] * len(all_cols))
    sql = f"INSERT INTO player_weekly_stats ({', '.join(all_cols)}) VALUES ({placeholders})"

    rows = []
    for s in stats_list:
        stats = s.get("stats", {})
        row = [
            s.get("player_id"), s.get("player_name"), s.get("team"),
            s.get("position"), s.get("opponent"), s.get("season"), s.get("week")
        ]
        for key in stat_keys:
            row.append(stats.get(key))
        rows.append(row)

    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ============ Matchup Odds Table ============

def create_matchup_odds_table(conn):
    """Create matchup_odds table for betting odds."""
    conn.execute("DROP TABLE IF EXISTS matchup_odds")
    conn.execute("""
        CREATE TABLE matchup_odds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            season INTEGER NOT NULL,
            week INTEGER NOT NULL,
            game_date TEXT,
            home_team TEXT NOT NULL,
            away_team TEXT NOT NULL,
            is_completed INTEGER DEFAULT 0,
            home_win_prob REAL,
            away_win_prob REAL,
            home_moneyline INTEGER,
            away_moneyline INTEGER,
            spread REAL,
            spread_home_odds INTEGER,
            spread_away_odds INTEGER,
            over_under REAL,
            over_odds INTEGER,
            under_odds INTEGER,
            home_team_total REAL,
            away_team_total REAL,
            expected_diff REAL,
            actual_home_score INTEGER,
            actual_away_score INTEGER,
            actual_total INTEGER,
            actual_diff INTEGER,
            spread_result TEXT,
            total_result TEXT,
            computed_at TEXT,
            UNIQUE(season, week, home_team, away_team)
        )
    """)
    conn.commit()


def insert_matchup_odds(conn, odds_list):
    """Insert matchup odds into database."""
    cols = [
        "season", "week", "game_date", "home_team", "away_team", "is_completed",
        "home_win_prob", "away_win_prob", "home_moneyline", "away_moneyline",
        "spread", "spread_home_odds", "spread_away_odds",
        "over_under", "over_odds", "under_odds",
        "home_team_total", "away_team_total", "expected_diff",
        "actual_home_score", "actual_away_score", "actual_total", "actual_diff",
        "spread_result", "total_result", "computed_at"
    ]
    placeholders = ", ".join(["?"] * len(cols))
    sql = f"INSERT OR REPLACE INTO matchup_odds ({', '.join(cols)}) VALUES ({placeholders})"

    rows = []
    for o in odds_list:
        row = [
            o.get("season"), o.get("week"), o.get("game_date"),
            o.get("home_team"), o.get("away_team"),
            1 if o.get("is_completed") else 0,
            o.get("home_win_prob"), o.get("away_win_prob"),
            o.get("home_moneyline"), o.get("away_moneyline"),
            o.get("spread"), o.get("spread_home_odds"), o.get("spread_away_odds"),
            o.get("over_under"), o.get("over_odds"), o.get("under_odds"),
            o.get("home_team_total"), o.get("away_team_total"), o.get("expected_diff"),
            o.get("actual_home_score"), o.get("actual_away_score"),
            o.get("actual_total"), o.get("actual_diff"),
            o.get("spread_result"), o.get("total_result"), o.get("computed_at")
        ]
        rows.append(row)

    conn.executemany(sql, rows)
    conn.commit()
    return len(rows)


# ============ Main ============

def main():
    args = sys.argv[1:]
    db_path = "nfl.db"

    # Parse --db argument
    for i, arg in enumerate(args):
        if arg == "--db" and i + 1 < len(args):
            db_path = args[i + 1]

    print(f"Building {db_path}...")

    conn = sqlite3.connect(db_path)

    # ===== Players =====
    player_files = sorted(Path(".").glob("players-with-stats-*.json"))
    if player_files:
        all_players = []
        all_stat_keys = set()
        for pf in player_files:
            with open(pf, encoding="utf-8") as f:
                players = json.load(f)
            year = extract_year_from_filename(pf)
            for p in players:
                p["_year"] = year
            all_players.extend(players)
            all_stat_keys.update(get_all_stat_keys(players))

        stat_keys = sorted(all_stat_keys)
        create_players_table(conn, stat_keys)

        total = 0
        for pf in player_files:
            year = extract_year_from_filename(pf)
            players = [p for p in all_players if p.get("_year") == year]
            count = insert_players(conn, players, stat_keys, year)
            total += count
            print(f"  players: {count} for {year}")
        print(f"  → {total} total players")

    # ===== Games =====
    game_files = sorted(Path(".").glob("games-*.json"))
    if game_files:
        create_games_table(conn)
        total = 0
        for gf in game_files:
            with open(gf, encoding="utf-8") as f:
                games = json.load(f)
            count = insert_games(conn, games)
            total += count
            year = extract_year_from_filename(gf)
            print(f"  games: {count} for {year}")
        print(f"  → {total} total games")

    # ===== Team Stats =====
    team_stats_files = sorted(Path(".").glob("team-stats-*.json"))
    if team_stats_files:
        create_team_stats_table(conn)
        total = 0
        for tf in team_stats_files:
            with open(tf, encoding="utf-8") as f:
                stats = json.load(f)
            count = insert_team_stats(conn, stats)
            total += count
            year = extract_year_from_filename(tf)
            print(f"  team_stats: {count} for {year}")
        print(f"  → {total} total team stats")

    # ===== Player Weekly Stats =====
    weekly_files = sorted(Path(".").glob("player-weekly-stats-*.json"))
    if weekly_files:
        all_weekly = []
        all_weekly_keys = set()
        for wf in weekly_files:
            with open(wf, encoding="utf-8") as f:
                weekly = json.load(f)
            all_weekly.extend(weekly)
            for w in weekly:
                if "stats" in w:
                    all_weekly_keys.update(w["stats"].keys())

        weekly_keys = sorted(all_weekly_keys)
        create_player_weekly_stats_table(conn, weekly_keys)
        count = insert_player_weekly_stats(conn, all_weekly, weekly_keys)
        print(f"  player_weekly_stats: {count} entries")

    # ===== Matchup Odds =====
    odds_files = sorted(Path(".").glob("matchup-odds-*.json"))
    if odds_files:
        create_matchup_odds_table(conn)
        total = 0
        for of in odds_files:
            with open(of, encoding="utf-8") as f:
                odds = json.load(f)
            count = insert_matchup_odds(conn, odds)
            total += count
            year = extract_year_from_filename(of)
            print(f"  matchup_odds: {count} for {year}")
        print(f"  → {total} total matchup odds")

    # ===== Create Indexes =====
    print("\nCreating indexes...")
    indexes = [
        "CREATE INDEX IF NOT EXISTS idx_players_team ON players(team)",
        "CREATE INDEX IF NOT EXISTS idx_players_position ON players(position)",
        "CREATE INDEX IF NOT EXISTS idx_players_year ON players(year)",
        "CREATE INDEX IF NOT EXISTS idx_games_season ON games(season)",
        "CREATE INDEX IF NOT EXISTS idx_games_week ON games(week)",
        "CREATE INDEX IF NOT EXISTS idx_games_teams ON games(home_team, away_team)",
        "CREATE INDEX IF NOT EXISTS idx_team_stats_team ON team_stats(team_code)",
        "CREATE INDEX IF NOT EXISTS idx_weekly_player ON player_weekly_stats(player_id)",
        "CREATE INDEX IF NOT EXISTS idx_weekly_week ON player_weekly_stats(season, week)",
        "CREATE INDEX IF NOT EXISTS idx_odds_week ON matchup_odds(season, week)",
    ]
    for idx in indexes:
        conn.execute(idx)
    conn.commit()

    conn.close()
    print(f"\n✓ Created {db_path}")


if __name__ == "__main__":
    main()
