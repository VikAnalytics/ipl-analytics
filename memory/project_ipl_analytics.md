---
name: project_ipl_analytics
description: Full current state of the IPL Analytics app — stack, architecture, open issues
type: project
---

## Repo
GitHub: https://github.com/VikAnalytics/ipl-analytics
Local: /Users/vikrantindi/Documents/ipl-master

## Stack
- UI: Streamlit (running locally on port 8504)
- AI: Google Gemini 2.5 Flash via `google-generativeai` (deprecated SDK — not yet migrated to `google-genai`)
- DB: Supabase / PostgreSQL via `psycopg2-binary`
- Python: 3.9 (EOL — upgrade to 3.12 is P3)

## Key files
- `app.py` — Streamlit UI, chat, glassmorphic CSS, tabs, typewriter SQL effect
- `database.py` — psycopg2 connection, execute_query, player alias map, schema fetch
- `ai_engine.py` — Gemini prompt construction and SQL generation
- `config.py` — GEMINI_MODEL, PROMPT_TABLES, all prompt template sections
- `tests/` — 30 pytest tests, all passing

## Supabase schema (from ipl-etl repo)
9 tables: deliveries, matches, innings, players, teams, match_players, officials, powerplays, player_season
- over_number is 1-indexed (1–20)
- phase column is pre-computed: 'powerplay', 'middle', 'death'
- wicket_player_out (not player_out), is_wicket is BOOLEAN
- season is VARCHAR like '2024' or '2020/21'
- Primary join: deliveries.match_id → matches.match_id

## ETL repo
GitHub: https://github.com/VikAnalytics/ipl-etl
Dataset is static — IPL 2008–2025, will not be refreshed.

## Secrets (local)
- .streamlit/secrets.toml has GEMINI_API_KEY and SUPABASE_DATABASE_URL (quoted, correct TOML)
- SUPABASE_DATABASE_URL uses direct connection db.[ref].supabase.co:5432

## Supabase connection
Using IPv4 connection pooler URL (aws-0-[region].pooler.supabase.com:5432) — confirmed working.
Direct connection URL (db.[ref].supabase.co:5432) had IPv6 issues on Streamlit Cloud.

## P0/P1 status (all done or irrelevant)
- Moved to Supabase → P1 items (DuckDB, Parquet, SQLite indexes) are obsolete
- connect_timeout=10 added to psycopg2

## P2 status (all implemented 2026-03-18)
- #8 sqlparse SQL validation (_validate_sql in database.py)
- #9 structured logging (logging.basicConfig in app.py, getLogger in all modules)
- #10 pytest suite (30 tests in tests/)
- #11 config.py extracted (GEMINI_MODEL, PROMPT_TABLES, prompt template sections)

## P3 status (not done)
- #12 connection pooling — partially done (Supabase handles pooling but no SQLAlchemy pool)
- #13 async Gemini calls — not done
- #14 Python 3.12 upgrade — not done
- #15 dataset scope in UI — done (sidebar caption)

## UI
- Glassmorphic dark-mode (radial gradient navy background)
- Claude-style chat UX: transparent messages, subtle user pill, 820px max-width
- KPI cards with hover-lift CSS animation
- Results in 3 tabs: Data Preview / SQL Logic / Visual Analytics
- Typewriter effect for SQL (first render only, tracked in session_state)
- Pulsing thinking animation (CSS, Lottie placeholder available via LOTTIE_THINKING_URL)
- No unnecessary emojis — only in welcome hero and example prompt chips
