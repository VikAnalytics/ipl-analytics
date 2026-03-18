from __future__ import annotations

import pandas as pd
import pytest


@pytest.fixture
def sample_alias_map() -> dict[str, str]:
    """Minimal alias map mirroring the manual overrides in database.py."""
    return {
        "virat kohli": "V Kohli",
        "v kohli": "V Kohli",
        "rohit sharma": "RG Sharma",
        "rg sharma": "RG Sharma",
    }


@pytest.fixture
def sample_df() -> pd.DataFrame:
    return pd.DataFrame({"batter": ["V Kohli", "RG Sharma"], "runs": [500, 450]})


@pytest.fixture
def empty_df() -> pd.DataFrame:
    return pd.DataFrame()


@pytest.fixture
def sample_schema() -> dict[str, list[str]]:
    return {
        "deliveries": ["match_id", "batter", "bowler", "runs_batter", "runs_total", "phase", "is_wicket"],
        "matches": ["match_id", "season", "venue", "outcome_winner"],
    }
