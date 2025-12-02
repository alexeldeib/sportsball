#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Convert players JSON files to SQLite database with flattened stats columns.
Usage: ./to_sqlite.py [json_file ...] [--db output.db]

Examples:
  ./to_sqlite.py                                    # converts all players*.json files
  ./to_sqlite.py players-with-stats-2025.json      # converts specific file
  ./to_sqlite.py --db nfl.db                       # specify output database
"""
import json
import sqlite3
import sys
from pathlib import Path


def get_all_stat_keys(players):
    """Collect all unique stat keys across all players."""
    keys = set()
    for p in players:
        if "stats" in p:
            keys.update(p["stats"].keys())
    return sorted(keys)


def create_table(conn, stat_keys):
    """Create players table with all stat columns."""
    # Base columns
    columns = [
        "id INTEGER PRIMARY KEY AUTOINCREMENT",
        "name TEXT NOT NULL",
        "team TEXT NOT NULL",
        "team_code TEXT",
        "position TEXT NOT NULL",
        "number INTEGER",  # Jersey number
        "year INTEGER",
    ]

    # Add stat columns (all REAL for numeric stats)
    for key in stat_keys:
        columns.append(f"{key} REAL")

    sql = f"CREATE TABLE IF NOT EXISTS players ({', '.join(columns)})"
    conn.execute("DROP TABLE IF EXISTS players")
    conn.execute(sql)
    conn.commit()


def insert_players(conn, players, stat_keys, year):
    """Insert players into database."""
    # Build column list
    base_cols = ["name", "team", "team_code", "position", "number", "year"]
    all_cols = base_cols + stat_keys

    placeholders = ", ".join(["?"] * len(all_cols))
    sql = f"INSERT INTO players ({', '.join(all_cols)}) VALUES ({placeholders})"

    rows = []
    for p in players:
        stats = p.get("stats", {})
        row = [
            p["name"],
            p["team"],
            p.get("team_code"),
            p["position"],
            p.get("number"),  # Jersey number
            year,
        ]
        # Add stat values (None if not present)
        for key in stat_keys:
            row.append(stats.get(key))
        rows.append(row)

    conn.executemany(sql, rows)
    conn.commit()


def extract_year_from_filename(filename):
    """Extract year from filename like 'players-with-stats-2025.json'."""
    import re
    match = re.search(r'(\d{4})', filename)
    return int(match.group(1)) if match else None


def main():
    args = sys.argv[1:]

    # Parse arguments
    db_path = "nfl.db"
    json_files = []

    i = 0
    while i < len(args):
        if args[i] == "--db" and i + 1 < len(args):
            db_path = args[i + 1]
            i += 2
        elif args[i].endswith(".json"):
            json_files.append(args[i])
            i += 1
        else:
            i += 1

    # Default: find all player JSON files with stats
    if not json_files:
        json_files = sorted(Path(".").glob("players-with-stats-*.json"))
        json_files = [str(f) for f in json_files]

    if not json_files:
        print("No JSON files found")
        sys.exit(1)

    print(f"Processing: {', '.join(json_files)}")

    # Load all players and collect all stat keys
    all_players = []
    all_stat_keys = set()

    for jf in json_files:
        with open(jf, encoding="utf-8") as f:
            players = json.load(f)
        year = extract_year_from_filename(jf)
        for p in players:
            p["_year"] = year
        all_players.extend(players)
        all_stat_keys.update(get_all_stat_keys(players))

    stat_keys = sorted(all_stat_keys)
    print(f"Found {len(all_players)} players, {len(stat_keys)} stat columns")

    # Create database
    conn = sqlite3.connect(db_path)
    create_table(conn, stat_keys)

    # Insert by year
    for jf in json_files:
        year = extract_year_from_filename(jf)
        players = [p for p in all_players if p.get("_year") == year]
        insert_players(conn, players, stat_keys, year)
        print(f"  Inserted {len(players)} players for {year}")

    # Create useful indexes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_team ON players(team)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_position ON players(position)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_year ON players(year)")
    conn.commit()

    # Print sample queries
    print(f"\nCreated {db_path}")
    print("\nSample queries:")
    print("  sqlite3 nfl.db \"SELECT name, team, pass_yd, pass_td FROM players WHERE position='QB' AND year=2025 ORDER BY pass_yd DESC LIMIT 10\"")
    print("  sqlite3 nfl.db \"SELECT name, team, rush_yd, rush_td FROM players WHERE position='RB' AND year=2025 ORDER BY rush_yd DESC LIMIT 10\"")
    print("  sqlite3 nfl.db \"SELECT name, team, rec, rec_yd, rec_td FROM players WHERE position='WR' AND year=2025 ORDER BY rec_yd DESC LIMIT 10\"")
    print("  sqlite3 nfl.db \"SELECT team, SUM(pass_td) as total_pass_td FROM players WHERE year=2025 GROUP BY team ORDER BY total_pass_td DESC\"")

    conn.close()


if __name__ == "__main__":
    main()
