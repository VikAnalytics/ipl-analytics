from __future__ import annotations

import re
from typing import Sequence

import google.generativeai as genai

TABLE_NAME = "deliveries"


def _format_schema(columns: Sequence[str]) -> str:
    return "\n".join(f"- {column}" for column in columns)


def _clean_sql(raw_text: str) -> str:
    sql = raw_text.strip()
    sql = re.sub(r"^```(?:sql)?\s*", "", sql, flags=re.IGNORECASE)
    sql = re.sub(r"\s*```$", "", sql)
    sql = sql.strip().rstrip(";")
    return sql


def build_prompt(user_question: str, columns: Sequence[str]) -> str:
    schema = _format_schema(columns)
    return f"""
You are a senior SQLite query generator for cricket analytics.

Database details:
- Engine: SQLite
- Table name: {TABLE_NAME}
- Exact columns available ({len(columns)} total):
{schema}

Rules:
1) Return ONLY valid SQLite SQL. No markdown, no code fences, no explanation.
2) Use only the columns listed above. Never invent column names.
3) Generate a single SELECT query (CTEs allowed via WITH).
4) Prefer defensive SQL with NULLIF for division where appropriate.
5) If the question asks for strike rate, use:
   (SUM(runs_batter) * 100.0) / NULLIF(COUNT(*), 0)
6) If the question asks for economy rate, use:
   (SUM(runs_total) * 1.0) / NULLIF(COUNT(*) / 6.0, 0)
7) For over-phase logic:
   - Powerplay: over 1-6
   - Middle overs: over 7-15
   - Death overs: over 16-20
8) Include sensible ORDER BY and LIMIT when user asks for top/best/worst rankings.
9) If the question is ambiguous, produce the most reasonable cricket-analytics interpretation.
10) When filtering player names, use short canonical values exactly as stored in dataset
    (for example: V Kohli, RG Sharma). Do not expand to full names unless full name exists.

User question:
{user_question}
""".strip()


def generate_sql(
    user_question: str,
    columns: Sequence[str],
    api_key: str,
    model_name: str = "gemini-2.5-flash",
) -> str:
    if not api_key:
        raise ValueError("Gemini API key is missing.")
    if not columns:
        raise ValueError("No schema columns available for SQL generation.")

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)
    prompt = build_prompt(user_question=user_question, columns=columns)
    response = model.generate_content(prompt)
    sql = _clean_sql(response.text or "")

    normalized = sql.lower().strip()
    if not normalized.startswith(("select", "with")):
        raise ValueError("Model did not return a valid SELECT SQL statement.")

    return sql
