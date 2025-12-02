# GitHub Copilot Instructions

## Project Overview

NFL Knowledge Hub - Quiz, study, and explore NFL stats. A web app for learning NFL rosters, stats, and trivia.

## Tech Stack

- **Frontend**: Vanilla HTML/CSS/JavaScript
- **Database**: SQLite via sql.js (WASM)
- **Data Source**: Sleeper API
- **Hosting**: Static files

## Issue Tracking with bd

**CRITICAL**: This project uses **bd** for ALL task tracking. Do NOT create markdown TODO lists.

### Essential Commands

```bash
# Find work
bd ready --json                    # Unblocked issues

# Create and manage
bd create "Title" -t bug|feature|task -p 0-4 --json
bd update <id> --status in_progress --json
bd close <id> --reason "Done" --json

# Sync
bd sync  # Force immediate export/commit/push
```

### Workflow

1. **Check ready work**: `bd ready --json`
2. **Claim task**: `bd update <id> --status in_progress`
3. **Work on it**: Implement, test, document
4. **Complete**: `bd close <id> --reason "Done" --json`
5. **Sync**: `bd sync`

## Project Structure

```
sportsball/
├── index.html           # Landing page
├── practice.html        # Spaced repetition practice
├── easy.html            # Multiple choice mode
├── game.html            # Daily challenge
├── trivia.html          # SQL-powered trivia
├── stats-quiz.html      # Stat leaders quiz
├── position-leaders.html # Position leaderboards
├── team-study.html      # Depth charts by team
├── explorer.html        # SQL query interface
├── main.py              # Fetch rosters from Sleeper API
├── fetch_stats.py       # Fetch player stats
├── to_sqlite.py         # Convert JSON to SQLite
└── nfl.db               # SQLite database
```

## Important Rules

- ✅ Use bd for ALL task tracking
- ✅ Use parameterized SQL queries (prepared statements)
- ✅ Keep styling consistent with existing pages
- ❌ Do NOT create markdown TODO lists
