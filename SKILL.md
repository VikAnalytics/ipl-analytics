# Cricket Analytics AI - Supported Skills

This document defines the cricket analytics capabilities the Text-to-SQL engine is designed to handle over the `deliveries` table.

## Core Batting Skills

- **Strike Rate**
  - Formula: `(SUM(runs_batter) * 100.0) / COUNT(*)`
  - Filters by batter, season, team, venue, phase, or opponent.

- **Boundary Percentage**
  - Percentage of balls resulting in 4s or 6s.

- **Dot Ball Percentage (Batsman)**
  - Percentage of deliveries with `runs_batter = 0`.

- **Most Runs / Highest Average Runs**
  - Aggregations by batter, team, season, and venue.

## Core Bowling Skills

- **Economy Rate**
  - Formula: `SUM(runs_total) / (COUNT(*) / 6.0)`.

- **Wicket Counts**
  - Total wickets by bowler (with optional dismissal-type filtering when available).

- **Dot Ball Percentage (Bowler)**
  - Percentage of legal balls with zero runs conceded.

- **Best Bowling by Phase**
  - Economy/wickets split by Powerplay, Middle, Death overs.

## Match-Phase Skills

- **Powerplay Strike Rate**
  - Overs 1-6.

- **Middle Overs Control**
  - Overs 7-15.

- **Death Over Wickets**
  - Overs 16-20.
  - Typical query groups by bowler/team/season and ranks wickets.

- **Phase-wise Run Rate**
  - Run-rate comparison across match phases.

## Contextual Filtering Skills

- **By Season / Date Range**
- **By Venue**
- **By Team**
- **By Opponent**
- **Home vs Away style venue slices (when inferable)**
- **Head-to-head batter vs bowler summaries**

## Ranking and Trend Skills

- **Top/Bottom N rankings** using `ORDER BY ... LIMIT`.
- **Year-over-year trends** with season grouping.
- **Venue leaderboards** for batting and bowling metrics.

## Safety and Query Discipline Skills

- Generates only read-only SQL (`SELECT`/`WITH`).
- Avoids invented schema by grounding against exact table columns.
- Applies safe division via `NULLIF(..., 0)` where relevant.
