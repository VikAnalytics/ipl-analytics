from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Iterable, Sequence

import pandas as pd

DEFAULT_DB_PATH = "cricket.db"
DEFAULT_CSV_PATH = "data.csv"
DELIVERIES_TABLE = "deliveries"
PLAYER_ALIASES_TABLE = "player_aliases"
PLAYER_NAME_COLUMNS = ("batter", "bowler", "non_striker", "player_out", "new_batter", "next_batter")
MANUAL_PLAYER_ALIASES = {
    "virat kohli": "V Kohli",
    "rohit sharma": "RG Sharma",
}


def _build_index_statements(table_name: str, columns: Sequence[str]) -> Iterable[str]:
    indexed_columns = ("bowler", "batter", "match_id", "venue")
    existing = set(columns)
    statements: list[str] = []
    for column in indexed_columns:
        if column in existing:
            statements.append(
                f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{column} ON {table_name}({column});"
            )
    return tuple(statements)


def _load_dataframe(csv_path: str) -> pd.DataFrame:
    """
    Load CSV data from a local file path or an HTTP(S) URL.
    """
    if csv_path.startswith(("http://", "https://")):
        return pd.read_csv(csv_path, low_memory=False)

    csv_file = Path(csv_path)
    if not csv_file.exists():
        raise FileNotFoundError(
            f"CSV file not found at '{csv_path}'. Provide a valid local path or HTTP(S) URL."
        )
    return pd.read_csv(csv_file, low_memory=False)


def _normalize_player_name(name: str) -> str:
    normalized = re.sub(r"[^a-z0-9 ]+", " ", name.lower())
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _generate_alias_candidates(canonical_name: str) -> set[str]:
    normalized = _normalize_player_name(canonical_name)
    aliases = {normalized}
    parts = [p for p in normalized.split(" ") if p]
    if len(parts) >= 2:
        aliases.add(f"{parts[0][0]} {parts[-1]}")
    return {a for a in aliases if a}


def _distinct_players(conn: sqlite3.Connection, table_columns: set[str]) -> list[str]:
    players: set[str] = set()
    for column in PLAYER_NAME_COLUMNS:
        if column not in table_columns:
            continue
        cursor = conn.execute(
            f"SELECT DISTINCT {column} FROM {DELIVERIES_TABLE} "
            f"WHERE {column} IS NOT NULL AND TRIM({column}) <> '';"
        )
        players.update(str(row[0]).strip() for row in cursor.fetchall() if row[0])
    return sorted(players)


def refresh_player_aliases(db_path: str = DEFAULT_DB_PATH) -> int:
    """Build or refresh deterministic player aliases from dataset values."""
    with sqlite3.connect(db_path) as conn:
        table_info = conn.execute(f"PRAGMA table_info({DELIVERIES_TABLE});").fetchall()
        table_columns = {row[1] for row in table_info}
        if not table_columns:
            raise ValueError(f"Table '{DELIVERIES_TABLE}' was not found.")

        players = _distinct_players(conn, table_columns)
        alias_map: dict[str, str | None] = {}
        for canonical_name in players:
            for alias in _generate_alias_candidates(canonical_name):
                existing = alias_map.get(alias)
                if existing is None and alias in alias_map:
                    continue
                if existing and existing != canonical_name:
                    alias_map[alias] = None
                else:
                    alias_map[alias] = canonical_name

        # Always keep exact normalized canonical names as deterministic mappings.
        for canonical_name in players:
            alias_map[_normalize_player_name(canonical_name)] = canonical_name

        # Add curated full-name aliases only when canonical exists in dataset.
        player_set = set(players)
        for alias, canonical in MANUAL_PLAYER_ALIASES.items():
            if canonical in player_set:
                alias_map[_normalize_player_name(alias)] = canonical

        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PLAYER_ALIASES_TABLE} (
                alias_name TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL
            );
            """
        )
        conn.execute(f"DELETE FROM {PLAYER_ALIASES_TABLE};")
        rows = [
            (alias, canonical)
            for alias, canonical in alias_map.items()
            if canonical is not None and alias and canonical
        ]
        conn.executemany(
            f"INSERT INTO {PLAYER_ALIASES_TABLE}(alias_name, canonical_name) VALUES (?, ?);",
            rows,
        )
        conn.commit()
    return len(rows)


def get_player_alias_map(db_path: str = DEFAULT_DB_PATH) -> dict[str, str]:
    """Return alias->canonical mappings."""
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {PLAYER_ALIASES_TABLE} (
                alias_name TEXT PRIMARY KEY,
                canonical_name TEXT NOT NULL
            );
            """
        )
        rows = conn.execute(
            f"SELECT alias_name, canonical_name FROM {PLAYER_ALIASES_TABLE};"
        ).fetchall()
    return {str(alias): str(canonical) for alias, canonical in rows}


def init_db(csv_path: str = DEFAULT_CSV_PATH, db_path: str = DEFAULT_DB_PATH) -> str:
    """
    Initialize SQLite DB from CSV data.

    Reads `csv_path`, writes a flat table named `deliveries`, and creates
    indexes for key cricket analytics dimensions.
    """
    dataframe = _load_dataframe(csv_path)

    with sqlite3.connect(db_path) as conn:
        dataframe.to_sql(DELIVERIES_TABLE, conn, if_exists="replace", index=False)
        for stmt in _build_index_statements(DELIVERIES_TABLE, dataframe.columns):
            conn.execute(stmt)
        conn.commit()

    refresh_player_aliases(db_path=db_path)

    return db_path


def get_table_columns(db_path: str = DEFAULT_DB_PATH, table_name: str = DELIVERIES_TABLE) -> list[str]:
    """Return ordered column names for a given table."""
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(f"PRAGMA table_info({table_name});")
        rows = cursor.fetchall()
    return [row[1] for row in rows]


def execute_query(sql: str, db_path: str = DEFAULT_DB_PATH) -> pd.DataFrame:
    """
    Execute read-only analytics SQL and return a DataFrame.

    Accepts SELECT/CTE-style queries and blocks write operations.
    """
    normalized = sql.strip().lower()
    if not (normalized.startswith("select") or normalized.startswith("with")):
        raise ValueError("Only SELECT queries are allowed.")

    forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "create ", "attach ", "pragma ")
    if any(keyword in normalized for keyword in forbidden):
        raise ValueError("SQL contains disallowed operations.")

    with sqlite3.connect(db_path) as conn:
        return pd.read_sql_query(sql, conn)
