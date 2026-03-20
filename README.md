# IPL Analytics

An AI-powered cricket analytics platform that converts natural-language questions into SQL, executes them against ball-by-ball IPL data (2008–2025), and visualises results in an interactive Streamlit dashboard.

## What You Can Ask

- Who are the top death-over wicket takers since 2018?
- How does Virat Kohli's strike rate compare in powerplay vs death overs?
- Which venues favour bowlers the most?
- Head-to-head: CSK vs MI win percentage by season

## Features

- **Natural language → SQL** via Google Gemini 2.5 Flash
- **SQL Studio** — run direct read-only PostgreSQL, no AI call needed
- **Schema-aware generation** grounded on real Supabase column names
- **Player alias normalisation** (`Virat Kohli` → `V Kohli`)
- **Interactive chart builder** with dynamic axis selection
- **Query result cache** — identical questions skip Gemini and the DB
- **Downloadable results** as CSV

## Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit |
| AI Engine | Google Gemini 2.5 Flash |
| Database | Supabase (PostgreSQL, `psycopg2-binary`) |
| Data processing | Pandas |

## Project Structure

```
app.py              Streamlit entry point — UI, chat, session state
config.py           Gemini model name, prompt tables, prompt template strings
core/
  database.py       Supabase connection, query execution, schema helpers, alias map
  ai_engine.py      Gemini prompt construction and SQL generation
tests/
  conftest.py       Shared fixtures
  test_database.py  SQL validation and execute_query tests
  test_ai_engine.py Prompt building and SQL generation tests
  test_aliases.py   Player alias resolution tests
docs/
  architecture.md   System flow and data layer design
  SKILL.md          Analytics capabilities reference
```

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY = "your_gemini_key"
SUPABASE_DATABASE_URL = "postgresql://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres"
```

```bash
streamlit run app.py
```

## Deploy to Streamlit Cloud

1. Push repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io), connect the repo, set main file to `app.py`
3. In **Secrets**, add:
   ```
   GEMINI_API_KEY = "..."
   SUPABASE_DATABASE_URL = "..."
   ```
4. Use the Supabase **connection pooler** URL (IPv4, port 5432) — not the direct DB URL

## Dataset

Static IPL ball-by-ball data, 2008–2025 (~278k deliveries across 1,169 matches). Hosted in Supabase — no CSV or local DB file required.
