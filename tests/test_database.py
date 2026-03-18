from __future__ import annotations

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from database import _validate_sql, execute_query


# ── _validate_sql ──────────────────────────────────────────────────────────────

def test_validate_sql_accepts_select():
    _validate_sql("SELECT * FROM deliveries")


def test_validate_sql_accepts_cte():
    _validate_sql("WITH cte AS (SELECT 1) SELECT * FROM cte")


def test_validate_sql_rejects_empty():
    with pytest.raises(ValueError, match="empty"):
        _validate_sql("   ")


def test_validate_sql_rejects_insert():
    with pytest.raises(ValueError):
        _validate_sql("INSERT INTO deliveries VALUES (1)")


def test_validate_sql_rejects_update():
    with pytest.raises(ValueError):
        _validate_sql("UPDATE deliveries SET runs_batter = 0")


def test_validate_sql_rejects_multiple_statements():
    with pytest.raises(ValueError, match="single"):
        _validate_sql("SELECT 1; SELECT 2")


# ── execute_query keyword blocking ────────────────────────────────────────────

@pytest.mark.parametrize("sql", [
    "INSERT INTO deliveries VALUES (1)",
    "UPDATE deliveries SET runs_batter = 0",
    "DELETE FROM deliveries",
    "DROP TABLE deliveries",
    "ALTER TABLE deliveries ADD COLUMN x INT",
    "CREATE TABLE foo (id INT)",
])
def test_execute_query_blocks_write_operations(sql):
    with pytest.raises(ValueError):
        execute_query(sql, database_url="unused")


def test_execute_query_returns_dataframe():
    mock_df = pd.DataFrame({"batter": ["V Kohli"], "runs": [600]})
    with patch("database._connect") as mock_connect:
        mock_conn = MagicMock()
        mock_connect.return_value.__enter__ = MagicMock(return_value=mock_conn)
        mock_connect.return_value.__exit__ = MagicMock(return_value=False)
        with patch("database.pd.read_sql_query", return_value=mock_df):
            result = execute_query("SELECT batter, SUM(runs_batter) AS runs FROM deliveries GROUP BY batter", database_url="mock://")
    assert isinstance(result, pd.DataFrame)
    assert len(result) == 1
