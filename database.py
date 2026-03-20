from __future__ import annotations

import logging
import re

import pandas as pd
import psycopg2
import sqlparse

from config import PROMPT_TABLES

logger = logging.getLogger(__name__)

DELIVERIES_TABLE = "deliveries"

MANUAL_PLAYER_ALIASES = {
    "virat kohli": "V Kohli",
    "rohit sharma": "RG Sharma",
}


def _connect(database_url: str):
    return psycopg2.connect(database_url, connect_timeout=10)


def _normalize_player_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    return re.sub(r"\s+", " ", normalized).strip()


def _validate_sql(sql: str) -> None:
    """Parse SQL with sqlparse and raise a clean ValueError if malformed."""
    try:
        parsed = sqlparse.parse(sql.strip())
    except Exception as exc:
        raise ValueError(f"Could not parse SQL: {exc}") from exc

    statements = [s for s in parsed if s.value.strip()]
    if not statements:
        raise ValueError("SQL statement is empty.")
    if len(statements) > 1:
        raise ValueError("Only a single SQL statement is allowed.")

    stmt_type = statements[0].get_type()
    # sqlparse returns None for WITH/CTE blocks, "SELECT" for plain SELECT
    if stmt_type not in (None, "SELECT"):
        raise ValueError(f"Only SELECT queries are allowed (got: {stmt_type}).")


def get_table_columns(database_url: str, table_name: str = DELIVERIES_TABLE) -> list[str]:
    """Return ordered column names for a given table."""
    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_schema = 'public' AND table_name = %s "
                "ORDER BY ordinal_position;",
                (table_name,),
            )
            return [row[0] for row in cur.fetchall()]


def get_schema_for_prompt(database_url: str) -> dict[str, list[str]]:
    """Return column lists for the main analytics tables used in Gemini prompts."""
    schema: dict[str, list[str]] = {}
    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            for table in PROMPT_TABLES:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema = 'public' AND table_name = %s "
                    "ORDER BY ordinal_position;",
                    (table,),
                )
                cols = [row[0] for row in cur.fetchall()]
                if cols:
                    schema[table] = cols
    return schema


def get_player_alias_map(database_url: str) -> dict[str, str]:
    """Return alias->canonical mappings from the players table and manual overrides."""
    alias_map: dict[str, str] = {}
    try:
        with _connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT player_name, full_name FROM players "
                    "WHERE full_name IS NOT NULL AND full_name <> player_name;"
                )
                rows = cur.fetchall()

        for player_name, full_name in rows:
            alias_map[_normalize_player_name(full_name)] = player_name
            alias_map[_normalize_player_name(player_name)] = player_name

        for alias, canonical in MANUAL_PLAYER_ALIASES.items():
            alias_map[_normalize_player_name(alias)] = canonical

    except Exception:
        logger.exception("Failed to load player alias map")

    return alias_map


def get_dataset_stats(database_url: str) -> dict[str, str]:
    stats = {"deliveries": "-", "matches": "-", "seasons": "-"}
    try:
        with _connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM deliveries;")
                stats["deliveries"] = f"{cur.fetchone()[0]:,}"
                cur.execute("SELECT COUNT(*) FROM matches;")
                stats["matches"] = f"{cur.fetchone()[0]:,}"
                cur.execute("SELECT COUNT(DISTINCT season) FROM matches;")
                stats["seasons"] = f"{cur.fetchone()[0]:,}"
    except Exception:
        logger.exception("Failed to fetch dataset stats")
    return stats


def execute_query(sql: str, database_url: str) -> pd.DataFrame:
    """Execute read-only analytics SQL against Supabase and return a DataFrame."""
    _validate_sql(sql)

    normalized = sql.strip().lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise ValueError("Only SELECT queries are allowed.")

    forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "create ", "attach ")
    if any(kw in normalized for kw in forbidden):
        raise ValueError("SQL contains disallowed operations.")

    logger.info("Executing query: %.200s", sql.replace("\n", " "))
    try:
        with _connect(database_url) as conn:
            df = pd.read_sql_query(sql, conn)
        logger.info("Query returned %d rows", len(df))
        return df
    except Exception as exc:
        logger.error("Query failed: %s", exc)
        raise
