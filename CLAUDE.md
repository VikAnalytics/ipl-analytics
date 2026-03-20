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

## P0 — Critical for Reliability

### 1. Pin dependency versions in `requirements.txt`
Current `requirements.txt` has no version pins. A Gemini API or Streamlit breaking change will silently break the app.
```
streamlit==1.43.0
google-generativeai==0.8.3
pandas==2.2.3
```
Run `pip freeze > requirements.txt` after verifying the app works.

### 2. Add query timeout to SQLite execution
Long-running LLM-generated queries (e.g., full table scans with subqueries) can hang the app. Add a timeout:
```python
conn.execute("PRAGMA busy_timeout = 5000")  # 5s
```
Or use `sqlite3.Connection` with a thread-based timeout wrapper.

### 3. Rate-limit Gemini API calls per session
No rate limiting exists. A user can spam queries and exhaust the API quota. Add a per-session query counter in `st.session_state`.

## P1 — Scalability

### 4. Replace SQLite with DuckDB
DuckDB is a drop-in analytical database that outperforms SQLite 5–20x on aggregation queries over wide tables. It supports Parquet natively, reducing storage from ~121MB to ~30MB. Migration is minimal — `duckdb.connect()` instead of `sqlite3.connect()`, same SQL dialect.

### 5. Store data as Parquet instead of CSV
`data.csv` at 103MB loads slowly. Parquet with snappy compression reduces this to ~20–25MB and is 3–5x faster to load with Pandas. Use `df.to_parquet("data.parquet")` and update `_load_dataframe()`.

### 6. Add composite indexes for common query patterns
Current indexes are single-column. Common analytics queries filter on `(season, batter)`, `(batting_team, venue)`, etc. Add:
```sql
CREATE INDEX idx_season_batter ON deliveries(season, batter);
CREATE INDEX idx_team_venue ON deliveries(batting_team, venue);
CREATE INDEX idx_over_wicket ON deliveries(over, wicket_kind);
```

### 7. Implement query result caching
Identical NL questions re-call Gemini and re-run SQL. Cache `(question_hash → DataFrame)` in session state or an LRU cache. Saves API cost and latency for repeated queries.

## P2 — Robustness

### 8. Add SQL validation before execution
Gemini occasionally returns syntactically invalid SQL. Parse the SQL with `sqlparse` before running it and surface a clean error message instead of a raw SQLite exception.

### 9. Structured logging
Currently errors are printed to console. Use Python `logging` with structured output (JSON) so Streamlit Cloud logs are queryable:
```python
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
```

### 10. Add a `conftest.py` test suite
Zero automated tests exist. At minimum, test:
- `execute_query()` blocks write keywords
- `generate_sql()` returns a SELECT/WITH statement
- `resolve_player_aliases()` maps known aliases correctly
- Chart rendering doesn't crash on empty DataFrames

Use `pytest` with a fixture that creates an in-memory SQLite DB from a 100-row sample.

### 11. Separate config from code
`ai_engine.py` hardcodes `gemini-2.5-flash` and prompt text inline. Move model name and prompt template to a config dict or `config.py` so swapping models or tuning prompts doesn't require editing logic code.

## P3 — Long-term Scale

### 12. Multi-user: move to PostgreSQL + connection pool
SQLite is single-writer. For >5 concurrent users (e.g., shared team deployment), migrate to PostgreSQL with `psycopg2` + SQLAlchemy connection pooling. The flat table schema transfers directly.

### 13. Async Gemini calls
`generate_sql()` is synchronous and blocks the Streamlit event loop. Use `asyncio` + `google.generativeai.GenerativeModel.generate_content_async()` to keep the UI responsive during long model calls.

### 14. Upgrade Python to 3.12
Python 3.9 EOL is October 2025. Streamlit Cloud already supports 3.12. Upgrading unlocks performance improvements and security patches with no breaking changes for this codebase.

### 15. Surface dataset scope in the UI
The dataset is static (IPL 2008–2025). Add a small info note in the UI sidebar so users know the data boundary upfront — prevents confusion when querying for seasons beyond 2025.
