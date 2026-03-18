from __future__ import annotations

# ── Gemini ─────────────────────────────────────────────────────────────────────
GEMINI_MODEL = "gemini-2.5-flash"

# ── Database ───────────────────────────────────────────────────────────────────
# Tables exposed to Gemini in the NL-to-SQL prompt (ordered by relevance)
PROMPT_TABLES = ["deliveries", "matches", "players", "innings"]

# ── Prompt template ────────────────────────────────────────────────────────────
SYSTEM_PROMPT_HEADER = "You are a senior PostgreSQL query generator for cricket analytics."

COLUMN_NOTES = """
Important column notes:
- over_number is 1-indexed: 1–6 = powerplay, 7–15 = middle, 16–20 = death
- phase column is pre-computed: values are 'powerplay', 'middle', 'death' — prefer this over filtering over_number
- is_wicket is a BOOLEAN (true/false), not a string
- wicket_player_out is the dismissed player (not player_out)
- runs_batter = runs scored by batter; runs_total = total off the ball (batter + extras)
- season is a VARCHAR like '2024' or '2020/21' (for UAE bubble season)
- legal_balls_bowled and balls_remaining are pre-computed per delivery
- matches.outcome_winner is the winning team (NULL for no-result/tie)
""".strip()

CRICKET_FORMULAS = """
Cricket formulas:
- Strike Rate: (SUM(runs_batter) * 100.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides = 0 AND extras_noballs = 0), 0)
- Economy Rate: (SUM(runs_total) * 6.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides = 0 AND extras_noballs = 0), 0)
- Use FILTER (WHERE ...) syntax for conditional aggregates — this is PostgreSQL, not SQLite.
""".strip()

JOIN_GUIDE = """
Key join relationships:
- deliveries.match_id → matches.match_id  (season, venue, city, outcome_winner, team1, team2)
- deliveries.innings_id → innings.innings_id  (team, target_runs)
- deliveries.batter / bowler → players.player_name  (nationality, batting_style, bowling_style)
""".strip()

QUERY_RULES = """
Rules:
1) Return ONLY valid PostgreSQL SQL. No markdown, no code fences, no explanation.
2) Use only columns that exist in the schema. Never invent column names.
3) Generate a single SELECT query (CTEs allowed via WITH).
4) Use NULLIF for all division to avoid divide-by-zero.
5) Join deliveries → matches for season, venue, or team-level questions.
6) Include sensible ORDER BY and LIMIT when user asks for top/best/worst rankings.
7) When filtering player names, use Cricsheet short names (e.g. V Kohli, RG Sharma).
8) If the question is ambiguous, produce the most reasonable cricket-analytics interpretation.
9) Do NOT use SQLite-specific syntax (no PRAGMA, no strftime — use PostgreSQL equivalents like EXTRACT or TO_CHAR).
10) Do NOT include is_super_over = false filter unless explicitly asked.
""".strip()
