# IPL Analytics

AI-powered cricket analytics platform. Ask questions in plain English — Gemini 2.5 Flash converts them to SQL, runs against 282K+ ball-by-ball IPL deliveries (2008–2025), and returns results instantly.

**Live:** https://ipl-master.vercel.app

## What You Can Ask

- Who are the top death-over wicket takers since 2018?
- How does Virat Kohli's strike rate compare in powerplay vs death overs?
- Which venues favour bowlers the most?
- Head-to-head: CSK vs MI win percentage by season
- Most sixes in a single season?

## Features

- **Natural language → SQL** via Google Gemini 2.5 Flash
- **REST API** — paginated, filterable access to all 9 IPL tables
- **Schema-aware generation** grounded on real Supabase column names
- **Player alias normalisation** (`Virat Kohli` → `V Kohli`)
- **Interactive chart builder** with dynamic axis selection
- **Downloadable results** as CSV
- **Live stats** — row counts fetched from DB on page load, never hardcoded
- **Champions section** — derived from match results, updates automatically each season

## Stack

| Layer | Technology |
|-------|-----------|
| UI | Vanilla HTML/CSS/JS (`index.html`) — no build step |
| API | FastAPI (`server.py`) |
| AI Engine | Google Gemini 2.5 Flash (`google-generativeai`) |
| Database | Supabase / PostgreSQL (`psycopg2-binary`) |
| Deployment | Vercel |

## Project Structure

```
server.py               FastAPI app — REST endpoints, rate limiting, security headers
index.html              Single-page frontend — AI query, champions, API explorer
api/index.py            Vercel entry point
vercel.json             Routes all traffic → api/index
config.py               Gemini model name, prompt tables, template strings
core/
  database.py           Supabase connection, query execution, alias map
  ai_engine.py          Gemini prompt construction and SQL generation
requirements.txt        Production deps
requirements-dev.txt    Dev deps (adds streamlit, pytest, uvicorn)
tests/                  30 tests — database, ai_engine, aliases
docs/
  architecture.md       System flow and data layer design
  SKILL.md              Analytics capabilities reference
```

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Create `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_gemini_key"
SUPABASE_DATABASE_URL = "postgresql://postgres.[ref]:[password]@aws-[n]-[region].pooler.supabase.com:6543/postgres"
```

```bash
uvicorn server:app --reload   # http://localhost:8000
```

## Deploy to Vercel

```bash
vercel --prod
```

Set environment variables once:

```bash
vercel env add GEMINI_API_KEY production
vercel env add SUPABASE_DATABASE_URL production
```

> **Important:** Use the Supabase **connection pooler** URL (Transaction mode, port 6543) — not the direct `db.*.supabase.co` URL. Vercel's network resolves the direct host to IPv6 only, which is blocked.
> Get it from: Supabase dashboard → Settings → Database → Connection Pooling → Transaction mode.

## Dataset

Static IPL ball-by-ball data, 2008–2025. 282,974 deliveries across 1,190 matches, 19 seasons, 945 players. Hosted in Supabase — no CSV or local DB file required.
