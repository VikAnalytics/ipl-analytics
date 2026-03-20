# Cricket Analytics AI - Architecture

## Overview

This system converts natural-language cricket questions into executable SQLite queries, runs them on a local indexed database, and visualizes results in Streamlit.

## End-to-End Flow

1. **User Query (Streamlit UI)**
   - User asks a question in chat format (for example, "Top 5 bowlers by death-over wickets").

2. **Gemini SQL Generation (`ai_engine.py`)**
   - The app sends the user question plus the exact `deliveries` table schema to Gemini.
   - Prompt constraints force output to be a single valid SQLite `SELECT`/`WITH` query.
   - Domain rules include cricket formulas like strike rate and economy rate.

3. **SQLite Execution (`database.py`)**
   - SQL is validated as read-only and executed against local SQLite DB.
   - Results are returned as a Pandas DataFrame.

4. **Result Display (`app.py`)**
   - Shows generated SQL in an expander.
   - Renders raw result table.
   - Auto-generates a quick summary chart when numeric output is present.

## Data Layer Design

- CSV source: `data.csv` (ball-by-ball IPL data for 2008-2025).
- DB file: `cricket.db`.
- Table: `deliveries` (flat "fat table" for LLM-friendly querying).
- Indexes:
  - `bowler`
  - `batter`
  - `match_id`
  - `venue`

This indexing strategy significantly improves query speed for common player, match, and venue filters.

## Safety and Reliability

- Only read-only SQL is executed (`SELECT` / `WITH`).
- Write and schema-changing SQL keywords are blocked.
- Errors (invalid SQL, missing schema, missing API key, DB init failures) are surfaced cleanly in UI.
- Gemini API key is loaded from Streamlit secrets or environment variables.

## Configuration

- API key in `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY="your_key_here"
```

- Run app:

```bash
streamlit run app.py
```
