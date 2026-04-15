# CLAUDE.md — IPL Analytics

## Project Overview

AI-powered cricket analytics platform. Converts natural-language questions to SQL, executes against ball-by-ball IPL data (2008–2025), and returns results via a FastAPI backend + single-page HTML frontend. Uses Google Gemini 2.5 Flash for NL-to-SQL. Deployed on Vercel.

## Stack

| Layer | Technology |
|-------|-----------|
| UI | Vanilla HTML/CSS/JS (`index.html`) — single file, no build step |
| API | FastAPI (`server.py`) — REST + AI endpoints |
| AI Engine | Google Gemini 2.5 Flash (`google-generativeai`) |
| Database | Supabase / PostgreSQL (`psycopg2-binary`) via connection pooler |
| Data | Pandas (query results from Supabase) |
| Python | 3.12 (Vercel runtime) |
| Deployment | Vercel (`vercel.json`, entry point `api/index.py`) |

## File Map

```
server.py                 FastAPI app — all REST endpoints, rate limiting, security headers
index.html                Single-page frontend — hero stats, champions, AI query, API explorer
api/
  index.py                Vercel entry point — imports FastAPI app from server.py
vercel.json               Vercel routing — all requests → /api/index
requirements.txt          Production deps (no Streamlit/pytest/uvicorn)
requirements-dev.txt      Dev deps — extends requirements.txt + streamlit, pytest, uvicorn
.vercelignore             Excludes secrets.toml, .venv, tests from Vercel deploys
config.py                 All config — Gemini model, prompt tables, prompt template strings
core/
  database.py             Supabase connection (pooler, SSL, sslmode=require), query execution, alias normalization
  ai_engine.py            Gemini prompt construction and SQL generation
app.py                    Legacy Streamlit entry point (local dev only)
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
| `deliveries` | 282,974 | `match_id`, `innings_id`, `over_number` (1-idx), `batter`, `bowler`, `runs_batter`, `runs_total`, `is_wicket`, `wicket_kind`, `wicket_player_out`, `phase`, `extras_wides`, `extras_noballs` |
| `matches` | 1,190 | `match_id`, `season`, `venue`, `city`, `match_date`, `team1`, `team2`, `outcome_winner`, `outcome_by_runs`, `outcome_by_wickets` |
| `players` | 945 | `player_key`, `player_name`, `full_name`, `nationality`, `batting_style`, `bowling_style`, `playing_role` |
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
pip install -r requirements-dev.txt
# Create .streamlit/secrets.toml:
# GEMINI_API_KEY="your_key_here"
# SUPABASE_DATABASE_URL="postgresql://postgres.[ref]:[password]@[region].pooler.supabase.com:6543/postgres"
uvicorn server:app --reload          # FastAPI at http://localhost:8000
# or: streamlit run app.py           # Legacy Streamlit UI
```

## Deployment (Vercel)

- Project: `vikanalytics-projects/ipl-master` → https://ipl-master.vercel.app
- Entry point: `api/index.py` imports `app` from `server.py`; `vercel.json` routes all traffic there
- **Use the Supabase connection pooler URL** (not the direct `db.*.supabase.co` URL) — Vercel's network resolves the direct host to IPv6 only, which is blocked
  - Get from: Supabase dashboard → Settings → Database → Connection Pooling → Transaction mode
  - Format: `postgresql://postgres.[ref]:[password]@aws-[n]-[region].pooler.supabase.com:6543/postgres`
- Env vars set via `vercel env add`: `GEMINI_API_KEY`, `SUPABASE_DATABASE_URL`
- Env var precedence: `os.getenv()` first, then `.streamlit/secrets.toml` (local fallback)
- `.vercelignore` excludes `secrets.toml`, `.venv`, `tests/` from deploys
- Redeploy: `vercel --prod`

## Dataset

The dataset is **static** — IPL 2008–2025 ball-by-ball data. It will not be refreshed or updated. Do not build data ingestion pipelines, refresh jobs, or update workflows.

## Sensitive Files (never commit)

- `.streamlit/secrets.toml` — API keys and DB URL (also excluded from Vercel via `.vercelignore`)
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
| 2 | Query timeout — `connect_timeout=10` + `sslmode=require` in `core/database.py:_connect()` |
| 3 | Rate-limit AI calls — 20 req/min per IP in `server.py:_check_rate_limit()` |
| 4 | Migrate to PostgreSQL — on Supabase/psycopg2, SQLite removed |
| 5 | Remove flat files — data lives in Supabase, no CSV/DB artifacts |
| 6 | Composite indexes — run in Supabase SQL editor (see below) |
| 7 | Query result caching — MD5 hash cache in session state (`app.py:query_cache`) |
| 8 | SQL validation — `sqlparse` pre-execution check in `core/database.py:_validate_sql()` |
| 9 | Structured logging — `logging` module in all files, INFO level |
| 10 | Test suite — 30 tests across `tests/` (database, ai_engine, aliases) |
| 11 | Separate config — `config.py` holds model name and all prompt text |
| 12 | PostgreSQL migration — done (see #4) |
| 15 | Dataset scope in UI — live counts fetched from `/api/stats` on page load |
| 16 | FastAPI backend — `server.py` replaces Streamlit for production; HTML frontend in `index.html` |
| 17 | Vercel deployment — `vercel.json` + `api/index.py`; Supabase pooler for IPv4 compatibility |
| 18 | Security hardening — XSS escaping in table render, generic 500 errors, security headers middleware, question length cap (500 chars), env-var-first secret precedence |
| 19 | Dynamic data — champions section and hero stats fetched live from DB, no hardcoded counts |

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
`generate_sql()` is synchronous and blocks the FastAPI event loop during AI queries. Use `asyncio.to_thread()` or `google.generativeai.GenerativeModel.generate_content_async()` to avoid blocking other requests.

### 14. Python version — resolved
Vercel runtime uses Python 3.12 automatically. No action needed.

### 20. Persistent rate limiting
Current rate limiter is in-memory per Vercel function instance — resets on cold start, not shared across instances. For stricter enforcement use Vercel KV or Upstash Redis.
