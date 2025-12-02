# Visual Lineup Viewer - Implementation Plan

**Issue**: sportsball-a3u

## Overview

Create an interactive visual lineup viewer that displays team formations on a football field layout, showing player names, jersey numbers, and positions.

## Data Requirements

### Current State
- Database has: name, team, position, stats (snaps, games started)
- Missing: jersey numbers

### Data Pipeline Update
1. **Update `fetch_stats.py`**: Add `number` field extraction from Sleeper API
2. **Update `to_sqlite.py`**: Add `number` column to players table
3. **Re-run pipeline**: `./fetch_stats.py 2025 && ./to_sqlite.py`

## UI Design

### Layout Concept
```
┌─────────────────────────────────────────────┐
│  [Year ▼]  [Team 1 ▼]  vs  [Team 2 ▼]      │
├─────────────────────────────────────────────┤
│                                             │
│  ┌─────────── OFFENSE ───────────┐          │
│  │         WR          WR        │          │
│  │              QB               │          │
│  │     OL  OL  C  OL  OL         │          │
│  │         TE     RB             │          │
│  └───────────────────────────────┘          │
│                                             │
│  ════════════ LINE OF SCRIMMAGE ══════════  │
│                                             │
│  ┌─────────── DEFENSE ───────────┐          │
│  │     DE  DT  DT  DE            │          │
│  │       LB    LB    LB          │          │
│  │    CB              CB         │          │
│  │         S      S              │          │
│  └───────────────────────────────┘          │
│                                             │
└─────────────────────────────────────────────┘
```

### Player Card Design
```
┌───────────┐
│    15     │  ← Jersey number (large)
│  MAHOMES  │  ← Last name
│    QB     │  ← Position
└───────────┘
```

### Formation Templates

**Offense (11 personnel)**:
- 1 QB, 1 RB, 1 TE, 3 WR, 5 OL

**Defense (4-3)**:
- 4 DL (2 DE, 2 DT), 3 LB, 2 CB, 2 S

**Defense (3-4)**:
- 3 DL (2 DE, 1 NT), 4 LB (2 OLB, 2 ILB), 2 CB, 2 S

## Implementation Steps

### Phase 1: Data Update
1. Modify `fetch_stats.py` to extract `number` field
2. Modify `to_sqlite.py` to add `number INTEGER` column
3. Re-generate database

### Phase 2: Core Page Structure
1. Create `lineup-viewer.html`
2. Add year/team selectors (single team mode first)
3. Load sql.js and database
4. Query starters by position using snap counts

### Phase 3: Visual Layout
1. CSS Grid-based field layout
2. Position players in correct spots
3. Player cards with name, number, position
4. Field background styling (green with yard lines)

### Phase 4: Matchup Mode
1. Add second team selector
2. Show Team 1 offense vs Team 2 defense (or vice versa)
3. Toggle between offense/defense views

### Phase 5: Polish
1. Add to index.html navigation
2. Update footer links across pages
3. Mobile responsive layout
4. Hover states showing additional player stats

## Starter Detection Logic

```javascript
// Get starters by position group
function getStarters(players, positionGroup, count) {
  return players
    .filter(p => positionGroup.includes(p.position))
    .sort((a, b) => {
      // Primary: games started
      const gsA = a.gs || 0, gsB = b.gs || 0;
      if (gsA !== gsB) return gsB - gsA;
      // Secondary: snap count
      const snapsA = (a.off_snp || 0) + (a.def_snp || 0);
      const snapsB = (b.off_snp || 0) + (b.def_snp || 0);
      return snapsB - snapsA;
    })
    .slice(0, count);
}
```

## Position Groupings

```javascript
const OFFENSE_POSITIONS = {
  QB: ['QB'],
  RB: ['RB', 'FB'],
  WR: ['WR'],
  TE: ['TE'],
  OL: ['OL', 'OT', 'G', 'C', 'T']
};

const DEFENSE_POSITIONS = {
  DL: ['DL', 'DE', 'DT', 'NT'],
  EDGE: ['EDGE'],
  LB: ['LB', 'OLB', 'ILB', 'MLB'],
  CB: ['CB'],
  S: ['S', 'SS', 'FS', 'DB']
};
```

## Files to Create/Modify

| File | Action |
|------|--------|
| `fetch_stats.py` | Add `number` field |
| `to_sqlite.py` | Add `number` column |
| `lineup-viewer.html` | New page |
| `index.html` | Add navigation link |
| `*.html` (footers) | Add footer links |

## Estimated Complexity

- Data pipeline: Small change
- Core viewer: Medium (new page, SQL queries)
- Visual layout: Medium (CSS positioning)
- Matchup mode: Small (additional selector + toggle)
- Total: ~400-500 lines of HTML/CSS/JS
