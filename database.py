from __future__ import annotations

import re
from typing import Sequence

import pandas as pd
import psycopg2

DELIVERIES_TABLE = "deliveries"
MATCHES_TABLE = "matches"
INNINGS_TABLE = "innings"
PLAYERS_TABLE = "players"

MANUAL_PLAYER_ALIASES = {
    "virat kohli": "V Kohli",
    "rohit sharma": "RG Sharma",
}

# Tables included in the AI prompt schema (ordered by relevance)
PROMPT_TABLES = [DELIVERIES_TABLE, MATCHES_TABLE, PLAYERS_TABLE, INNINGS_TABLE]


def _connect(database_url: str):
    return psycopg2.connect(database_url)


def _normalize_player_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def get_table_columns(database_url: str, table_name: str = DELIVERIES_TABLE) -> list[str]:
    """Return ordered column names for a given table."""
    sql = """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
    """
    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(sql, (table_name,))
            return [row[0] for row in cur.fetchall()]


def get_schema_for_prompt(database_url: str) -> dict[str, list[str]]:
    """Return column lists for the main analytics tables used in Gemini prompts."""
    schema: dict[str, list[str]] = {}
    with _connect(database_url) as conn:
        with conn.cursor() as cur:
            for table in PROMPT_TABLES:
                cur.execute(
                    """
                    SELECT column_name FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = %s
                    ORDER BY ordinal_position;
                    """,
                    (table,),
                )
                cols = [row[0] for row in cur.fetchall()]
                if cols:
                    schema[table] = cols
    return schema


def get_player_alias_map(database_url: str) -> dict[str, str]:
    """Return alias->canonical mappings from the players table and manual overrides."""
    sql = """
        SELECT player_name, full_name FROM players
        WHERE full_name IS NOT NULL AND full_name <> player_name;
    """
    alias_map: dict[str, str] = {}
    try:
        with _connect(database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                rows = cur.fetchall()

        for player_name, full_name in rows:
            alias_map[_normalize_player_name(full_name)] = player_name
            alias_map[_normalize_player_name(player_name)] = player_name

        # Manual overrides (full-name → Cricsheet short name)
        for alias, canonical in MANUAL_PLAYER_ALIASES.items():
            alias_map[_normalize_player_name(alias)] = canonical

    except Exception:
        pass

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
        pass
    return stats


def execute_query(sql: str, database_url: str) -> pd.DataFrame:
    """
    Execute read-only analytics SQL against Supabase and return a DataFrame.

    Accepts SELECT/CTE-style queries and blocks write operations.
    """
    normalized = sql.strip().lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise ValueError("Only SELECT queries are allowed.")

    forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "create ", "attach ")
    if any(keyword in normalized for keyword in forbidden):
        raise ValueError("SQL contains disallowed operations.")

    with _connect(database_url) as conn:
        return pd.read_sql_query(sql, conn)
