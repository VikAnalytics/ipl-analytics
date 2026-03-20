# CLAUDE.md — IPL Analytics

## Project Overview

AI-powered cricket analytics platform. Converts natural-language questions to SQL, executes against ball-by-ball IPL data (2008–2025), and visualizes results in Streamlit. Uses Google Gemini 2.5 Flash for NL-to-SQL.

## Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| AI Engine | Google Gemini 2.5 Flash (`google-generativeai`) |
| Database | Supabase / PostgreSQL (`psycopg2-binary`) |
| Data | Pandas (query results from Supabase) |
| Python | 3.9 |

## File Map

```
app.py                    Main Streamlit entry point — UI, chat, chart rendering, session state
config.py                 All config — Gemini model, prompt tables, prompt template strings
core/
  database.py             Supabase connection, query execution, player alias normalization
  ai_engine.py            Gemini prompt construction and SQL generation
tests/
  conftest.py             Shared fixtures
  test_database.py        SQL validation and execute_query tests
  test_ai_engine.py       Prompt building and SQL generation tests
  test_aliases.py         Player alias resolution tests
docs/
  SKILL.md                65+ documented analytics capabilities
  architecture.md         System flow diagram and data layer design
```

## Key Architecture Decisions

**Normalized Supabase schema** — 9 tables (`deliveries`, `matches`, `innings`, `players`, `teams`, `match_players`, `officials`, `powerplays`, `player_season`). The Gemini prompt includes `deliveries`, `matches`, `players`, and `innings` with explicit join guidance.

**Over numbering** — `over_number` in Supabase is **1-indexed** (1–20). The `phase` column is pre-computed (`'powerplay'`, `'middle'`, `'death'`). Always prefer `phase` over filtering `over_number`.

**Player alias normalization** — `get_player_alias_map()` queries `players.full_name → players.player_name` in Supabase. Manual overrides (e.g., "Virat Kohli" → "V Kohli") are in `core/database.py:MANUAL_PLAYER_ALIASES`.

**Read-only SQL enforcement** — `execute_query()` blocks INSERT/UPDATE/DELETE/DROP/ALTER/CREATE/ATTACH. Only SELECT and WITH (CTEs) are allowed. Never relax this.

**Gemini prompt engineering** — `core/ai_engine.py:build_prompt()` receives the multi-table schema dict and injects join guidance, cricket formulas, and PostgreSQL-specific syntax rules. Changes here directly affect query quality.

## Database Schema (Supabase / PostgreSQL)

Key tables:

| Table | Rows | Key Columns |
|-------|------|-------------|
| `deliveries` | 278,205 | `match_id`, `innings_id`, `over_number` (0-idx), `batter`, `bowler`, `runs_batter`, `runs_total`, `is_wicket`, `wicket_kind`, `wicket_player_out`, `phase`, `extras_wides`, `extras_noballs` |
| `matches` | 1,169 | `match_id`, `season`, `venue`, `city`, `match_date`, `team1`, `team2`, `outcome_winner`, `outcome_by_runs`, `outcome_by_wickets` |
| `players` | 925 | `player_key`, `player_name`, `full_name`, `nationality`, `batting_style`, `bowling_style`, `playing_role` |
| `innings` | 2,365 | `innings_id`, `match_id`, `innings_number`, `team`, `target_runs`, `is_super_over` |

Primary join: `deliveries.match_id → matches.match_id` (needed for season/venue/outcome filters)

## Cricket Formulas (embedded in prompts)

- **Strike Rate:** `(SUM(runs_batter) * 100.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides=0 AND extras_noballs=0), 0)`
- **Economy Rate:** `(SUM(runs_total) * 6.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides=0 AND extras_noballs=0), 0)`
- **Phase:** use pre-computed `phase` column (`'powerplay'`, `'middle'`, `'death'`) — do not filter by `over_number`; if needed: powerplay = 1–6, middle = 7–15, death = 16–20
- PostgreSQL `FILTER (WHERE ...)` syntax for conditional aggregates, not SQLite `CASE WHEN`

## Local Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Create .streamlit/secrets.toml:
# GEMINI_API_KEY="your_key_here"
# SUPABASE_DATABASE_URL="postgresql://postgres:[password]@db.[ref].supabase.co:5432/postgres"
streamlit run app.py
```

## Deployment (Streamlit Cloud)

- Secrets panel: set `GEMINI_API_KEY` and `SUPABASE_DATABASE_URL`
- No CSV or SQLite file needed — all data is in Supabase

## Dataset

The dataset is **static** — IPL 2008–2025 ball-by-ball data. It will not be refreshed or updated. Do not build data ingestion pipelines, refresh jobs, or update workflows.

## Sensitive Files (never commit)

- `.streamlit/secrets.toml` — Gemini API key
- `cricket.db` — generated artifact
- `data.csv` — large binary, host externally for cloud deploys

## Scalability & Robustness Recommendations

See the section below for prioritized upgrade paths.

---

# Upgrade Recommendations

## Done

| # | Item |
|---|------|
| 1 | Pin dependency versions — all packages pinned in `requirements.txt` |
| 2 | Query timeout — `connect_timeout=10` in `core/database.py:_connect()` |
| 3 | Rate-limit Gemini calls — 20 queries/session, counter shown in sidebar (`app.py:QUERY_LIMIT`) |
| 4 | Migrate to PostgreSQL — on Supabase/psycopg2, SQLite removed |
| 5 | Remove flat files — data lives in Supabase, no CSV/DB artifacts |
| 6 | Composite indexes — run in Supabase SQL editor (see below) |
| 7 | Query result caching — MD5 hash cache in session state (`app.py:query_cache`) |
| 8 | SQL validation — `sqlparse` pre-execution check in `core/database.py:_validate_sql()` |
| 9 | Structured logging — `logging` module in all files, INFO level |
| 10 | Test suite — 30 tests across `tests/` (database, ai_engine, aliases) |
| 11 | Separate config — `config.py` holds model name and all prompt text |
| 12 | PostgreSQL migration — done (see #4) |
| 15 | Dataset scope in UI — sidebar caption + AI query counter |

## Composite Index SQL (run once in Supabase SQL Editor)

`season` and `venue` live in `matches`, not `deliveries`. Indexes must target the correct tables:

```sql
-- deliveries: filter by batter, bowler, phase, wicket; join via match_id / innings_id
CREATE INDEX IF NOT EXISTS idx_deliveries_batter        ON deliveries(batter);
CREATE INDEX IF NOT EXISTS idx_deliveries_bowler        ON deliveries(bowler);
CREATE INDEX IF NOT EXISTS idx_deliveries_phase_wicket  ON deliveries(phase, is_wicket);
CREATE INDEX IF NOT EXISTS idx_deliveries_match_id      ON deliveries(match_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_innings_id    ON deliveries(innings_id);

-- matches: filter by season, venue
CREATE INDEX IF NOT EXISTS idx_matches_season           ON matches(season);
CREATE INDEX IF NOT EXISTS idx_matches_venue            ON matches(venue);
```

## Remaining (P3 — Long-term)

### 13. Async Gemini calls
`generate_sql()` is synchronous and blocks the Streamlit event loop. Use `asyncio` + `google.generativeai.GenerativeModel.generate_content_async()` to keep the UI responsive during long model calls.

### 14. Upgrade Python to 3.12
Python 3.9 EOL is October 2025. Streamlit Cloud already supports 3.12. Upgrading unlocks performance improvements and security patches with no breaking changes for this codebase.
