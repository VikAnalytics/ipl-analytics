from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from core.ai_engine import _clean_sql, build_prompt, generate_sql
from config import GEMINI_MODEL


# ── _clean_sql ─────────────────────────────────────────────────────────────────

def test_clean_sql_strips_markdown_fence():
    assert _clean_sql("```sql\nSELECT 1\n```") == "SELECT 1"


def test_clean_sql_strips_plain_fence():
    assert _clean_sql("```\nSELECT 1\n```") == "SELECT 1"


def test_clean_sql_strips_trailing_semicolon():
    assert _clean_sql("SELECT 1;") == "SELECT 1"


def test_clean_sql_passthrough_clean_sql():
    assert _clean_sql("SELECT * FROM deliveries") == "SELECT * FROM deliveries"


# ── build_prompt ───────────────────────────────────────────────────────────────

def test_build_prompt_includes_question(sample_schema):
    prompt = build_prompt("top run scorers", sample_schema)
    assert "top run scorers" in prompt


def test_build_prompt_includes_table_names(sample_schema):
    prompt = build_prompt("any question", sample_schema)
    assert "deliveries" in prompt
    assert "matches" in prompt


def test_build_prompt_includes_column_notes(sample_schema):
    prompt = build_prompt("any question", sample_schema)
    assert "phase" in prompt
    assert "is_wicket" in prompt


# ── generate_sql ───────────────────────────────────────────────────────────────

def test_generate_sql_raises_without_api_key(sample_schema):
    with pytest.raises(ValueError, match="API key"):
        generate_sql("top scorers", sample_schema, api_key="")


def test_generate_sql_raises_without_schema():
    with pytest.raises(ValueError, match="schema"):
        generate_sql("top scorers", schema={}, api_key="fake-key")


def test_generate_sql_returns_select(sample_schema):
    mock_response = MagicMock()
    mock_response.text = "SELECT batter, SUM(runs_batter) FROM deliveries GROUP BY batter"
    with patch("core.ai_engine.genai.configure"), \
         patch("core.ai_engine.genai.GenerativeModel") as mock_model_cls:
        mock_model_cls.return_value.generate_content.return_value = mock_response
        sql = generate_sql("top run scorers", sample_schema, api_key="fake-key")
    assert sql.strip().lower().startswith("select")


def test_generate_sql_raises_on_non_select(sample_schema):
    mock_response = MagicMock()
    mock_response.text = "I cannot generate that query."
    with patch("core.ai_engine.genai.configure"), \
         patch("core.ai_engine.genai.GenerativeModel") as mock_model_cls:
        mock_model_cls.return_value.generate_content.return_value = mock_response
        with pytest.raises(ValueError, match="SELECT"):
            generate_sql("drop all tables", sample_schema, api_key="fake-key")


def test_generate_sql_uses_configured_model(sample_schema):
    mock_response = MagicMock()
    mock_response.text = "SELECT 1"
    with patch("core.ai_engine.genai.configure"), \
         patch("core.ai_engine.genai.GenerativeModel") as mock_model_cls:
        mock_model_cls.return_value.generate_content.return_value = mock_response
        generate_sql("test", sample_schema, api_key="fake-key")
    mock_model_cls.assert_called_once_with(model_name=GEMINI_MODEL)
