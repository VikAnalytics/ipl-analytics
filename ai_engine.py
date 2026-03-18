from __future__ import annotations

import re

import google.generativeai as genai


def _format_schema(schema: dict[str, list[str]]) -> str:
    lines: list[str] = []
    for table, columns in schema.items():
        lines.append(f"Table: {table} ({len(columns)} columns)")
        for col in columns:
            lines.append(f"  - {col}")
        lines.append("")
    return "\n".join(lines).strip()


def _clean_sql(raw_text: str) -> str:
    sql = raw_text.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip().rstrip(";")
    return sql


def build_prompt(user_question: str, schema: dict[str, list[str]]) -> str:
    schema_text = _format_schema(schema)
    return f"""
You are a senior PostgreSQL query generator for cricket analytics.

Database: Supabase (PostgreSQL). Schema below — use only columns that exist.

{schema_text}

Key join relationships:
- deliveries.match_id → matches.match_id  (season, venue, city, outcome_winner, team1, team2)
- deliveries.innings_id → innings.innings_id  (team, target_runs)
- deliveries.batter / bowler → players.player_name  (nationality, batting_style, bowling_style)

Important column notes:
- over_number is 1-indexed: 1–6 = powerplay, 7–15 = middle, 16–20 = death
- phase column is pre-computed: values are 'powerplay', 'middle', 'death' — prefer this over filtering over_number
- is_wicket is a BOOLEAN (true/false), not a string
- wicket_player_out is the dismissed player (not player_out)
- runs_batter = runs scored by batter; runs_total = total off the ball (batter + extras)
- season is a VARCHAR like '2024' or '2020/21' (for UAE bubble season)
- legal_balls_bowled and balls_remaining are pre-computed per delivery
- matches.outcome_winner is the winning team (NULL for no-result/tie)

Cricket formulas:
- Strike Rate: (SUM(runs_batter) * 100.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides = 0 AND extras_noballs = 0), 0)
- Economy Rate: (SUM(runs_total) * 6.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides = 0 AND extras_noballs = 0), 0)
- Use FILTER (WHERE ...) syntax for conditional aggregates — this is PostgreSQL, not SQLite.

Rules:
1) Return ONLY valid PostgreSQL SQL. No markdown, no code fences, no explanation.
2) Use only columns that exist in the schema. Never invent column names.
3) Generate a single SELECT query (CTEs allowed via WITH).
4) Use NULLIF for all division to avoid divide-by-zero.
5) Join deliveries → matches for season, venue, or team-level questions.
6) Include sensible ORDER BY and LIMIT when user asks for top/best/worst rankings.
7) When filtering player names, use Cricsheet short names (e.g. V Kohli, RG Sharma) — they are stored in deliveries.batter and deliveries.bowler.
8) If the question is ambiguous, produce the most reasonable cricket-analytics interpretation.
9) Do NOT use SQLite-specific syntax (no PRAGMA, no strftime — use PostgreSQL equivalents like EXTRACT or TO_CHAR).
10) Do NOT include is_super_over = false filter unless asked — most questions refer to regulation play only; add this filter when appropriate.

User question:
{user_question}
""".strip()


def generate_sql(
    user_question: str,
    schema: dict[str, list[str]],
    api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> str:
    if not api_key:
        raise ValueError("Gemini API key is missing.")
    if not schema:
        raise ValueError("No schema available for SQL generation.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)
    prompt = build_prompt(user_question=user_question, schema=schema)
    response = model.generate_content(prompt)
    sql = _clean_sql(response.text or "")

    normalized = sql.lower().strip()
    if not normalized.startswith(("select", "with")):
        raise ValueError("Model did not return a valid SELECT SQL statement.")

    return sql
