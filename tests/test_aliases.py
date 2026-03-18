from __future__ import annotations

from unittest.mock import patch

import pytest


# Import resolve_player_aliases from app — patch get_player_alias_map
def _resolve(question: str, alias_map: dict[str, str]) -> tuple[str, list[str]]:
    """Thin wrapper that injects a fixed alias_map without hitting the DB."""
    with patch("app.get_player_alias_map", return_value=alias_map):
        from app import resolve_player_aliases
        return resolve_player_aliases(question, database_url="mock://")


def test_resolves_full_name_to_short(sample_alias_map):
    rewritten, notes = _resolve("How many runs did Virat Kohli score?", sample_alias_map)
    assert "V Kohli" in rewritten
    assert any("virat kohli" in n for n in notes)


def test_resolves_rohit_sharma(sample_alias_map):
    rewritten, notes = _resolve("Rohit Sharma's centuries", sample_alias_map)
    assert "RG Sharma" in rewritten


def test_unknown_name_passes_through(sample_alias_map):
    rewritten, notes = _resolve("MS Dhoni's stumpings", sample_alias_map)
    assert "MS Dhoni" in rewritten
    assert notes == []


def test_empty_alias_map_returns_original():
    rewritten, notes = _resolve("any question", alias_map={})
    assert rewritten == "any question"
    assert notes == []


def test_case_insensitive_match(sample_alias_map):
    rewritten, _ = _resolve("virat KOHLI scored 100", sample_alias_map)
    assert "V Kohli" in rewritten
