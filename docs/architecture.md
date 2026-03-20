# IPL Analytics — Architecture

## Overview

Converts natural-language cricket questions into PostgreSQL queries, executes them against a normalised Supabase database (9 tables, ~278k deliveries), and renders results in Streamlit.

## End-to-End Flow

```
User Question (Streamlit chat)
        │
        ▼
Player Alias Normalisation (app.py)
  "Virat Kohli" → "V Kohli"  via players table + manual overrides
        │
        ▼
Gemini 2.5 Flash (core/ai_engine.py)
  build_prompt() injects schema, join guide, cricket formulas, query rules
  generate_sql() calls Gemini API → raw text → _clean_sql() strips fences
        │
        ▼
SQL Validation (core/database.py)
  _validate_sql() — sqlparse check: single statement, SELECT/WITH only
  execute_query() — keyword block: INSERT/UPDATE/DELETE/DROP/ALTER/CREATE
        │
        ▼
Supabase / PostgreSQL (psycopg2)
  pd.read_sql_query() → Pandas DataFrame
        │
        ▼
Streamlit UI (app.py)
  Data Preview | SQL Logic (typewriter) | Visual Analytics tabs
```

## Data Layer

**Database:** Supabase (PostgreSQL), connected via connection pooler (IPv4, port 5432).

**Key tables:**

| Table | Rows | Purpose |
|-------|------|---------|
| `deliveries` | ~278k | Ball-by-ball events — batter, bowler, runs, wicket, phase |
| `matches` | 1,169 | Match metadata — season, venue, teams, outcome |
| `innings` | 2,365 | Innings context — batting team, target |
| `players` | 925 | Player profiles — full name, style, nationality |

**Primary join:** `deliveries.match_id → matches.match_id` (required for any season or venue filter)

**Pre-computed columns:**
- `phase` — `'powerplay'` / `'middle'` / `'death'` (prefer over filtering `over_number`)
- `over_number` — 1-indexed (1–20)
- `legal_balls_bowled`, `balls_remaining` — pre-computed per delivery

## Configuration (`config.py`)

All prompt strings, the Gemini model name, and the list of tables exposed to the AI live in `config.py`. Changes here directly affect query quality — no other file needs touching.

**Cricket formulas injected into every prompt:**
- Strike Rate: `(SUM(runs_batter) * 100.0) / NULLIF(legal balls, 0)`
- Economy Rate: `(SUM(runs_total) * 6.0) / NULLIF(legal balls, 0)`

## Safety

- `_validate_sql()` uses `sqlparse` — rejects non-SELECT, empty, or multi-statement SQL before any DB call
- `execute_query()` does a second keyword scan for write operations
- 20 AI query limit per session (rate limiting in `app.py`)
- Identical questions are served from an MD5 hash cache (session state), skipping Gemini and the DB entirely
- All DB connections use `connect_timeout=10s`

## Secrets

```toml
# .streamlit/secrets.toml
GEMINI_API_KEY = "..."
SUPABASE_DATABASE_URL = "postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres"
```

Use the Supabase **connection pooler** URL (not the direct DB URL) to avoid IPv6 routing issues on Streamlit Cloud.
