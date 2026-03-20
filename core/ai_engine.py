from __future__ import annotations

import logging
import re

import google.generativeai as genai

from config import (
    COLUMN_NOTES,
    CRICKET_FORMULAS,
    GEMINI_MODEL,
    JOIN_GUIDE,
    QUERY_RULES,
    SYSTEM_PROMPT_HEADER,
)

logger = logging.getLogger(__name__)


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
    return sql.strip().rstrip(";")


def build_prompt(user_question: str, schema: dict[str, list[str]]) -> str:
    return f"""
{SYSTEM_PROMPT_HEADER}

Database: Supabase (PostgreSQL). Schema below — use only columns that exist.

{_format_schema(schema)}

{JOIN_GUIDE}

{COLUMN_NOTES}

{CRICKET_FORMULAS}

{QUERY_RULES}

User question:
{user_question}
""".strip()


def generate_sql(
    user_question: str,
    schema: dict[str, list[str]],
    api_key: str,
    model_name: str = GEMINI_MODEL,
) -> str:
    if not api_key:
        raise ValueError("Gemini API key is missing.")
    if not schema:
        raise ValueError("No schema available for SQL generation.")

    logger.info("Generating SQL for: %.120s", user_question)

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name=model_name)
    prompt = build_prompt(user_question=user_question, schema=schema)

    try:
        response = model.generate_content(prompt)
        sql = _clean_sql(response.text or "")
    except Exception as exc:
        logger.error("Gemini call failed: %s", exc)
        raise

    if not sql.lower().strip().startswith(("select", "with")):
        raise ValueError("Model did not return a valid SELECT SQL statement.")

    logger.info("Generated SQL: %.200s", sql.replace("\n", " "))
    return sql
