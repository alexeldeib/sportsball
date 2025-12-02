# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

NFL roster quiz app with spaced repetition. Users guess player team/position from name or vice versa.

## Components

### Data Scripts
- **main.py** - Fetches NFL player rosters from Sleeper API → `players-2025.json`
- **fetch_stats.py** - Fetches player stats from Sleeper API → `players-with-stats-{year}.json`
- **to_sqlite.py** - Converts JSON to SQLite database → `nfl.db`

### Quiz Pages
- **index.html** - Landing page with links to all modes
- **practice.html** - Practice mode with spaced repetition
- **easy.html** - Multiple choice mode
- **game.html** - Daily challenge (same 10 questions for everyone each day)
- **trivia.html** - Trivia mode with SQL-powered validation
- **stats-quiz.html** - Name league stat leaders

### Reference Pages
- **team-study.html** - Depth charts by team and year
- **explorer.html** - SQL query interface using sql.js (WASM SQLite in browser)

## Commands

Refresh player data:
```bash
./main.py              # roster only → players-2025.json
./fetch_stats.py 2025  # roster + stats → players-with-stats-2025.json
./to_sqlite.py         # convert to SQLite → nfl.db
```

Serve locally (to allow index.html to fetch the JSON):
```bash
python -m http.server 8000
```

## Key Details

- `main.py` uses inline script metadata (PEP 723) for dependencies - run with `uv run` or make executable
- Only "Active" and "Rookie" status players are included from Sleeper API
- Quiz supports position input as abbreviations (QB, WR) or full names (Quarterback, Wide Receiver)
- Stats persistence uses localStorage keys: `nflQuizStats_v1`, `nflQuizGlobal_v1`
