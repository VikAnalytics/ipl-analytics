# IPL Analytics

An AI-powered cricket intelligence workspace for fans, analysts, and strategy leaders.

`IPL Analytics` turns natural-language questions into SQL, runs them on ball-by-ball IPL data (2008-2025), and returns executive-ready insights with interactive visualizations.

## Why This Is Different

- **For cricket lovers:** ask real match questions in plain English and explore player, phase, venue, and season trends instantly.
- **For stats-first users:** inspect generated SQL, run direct SQL, and validate every number from source data.
- **For business decision-makers:** convert large, noisy match data into concise, explainable insights fast enough for weekly reviews and sponsor narratives.

## Executive Narrative

- **Data to decision in minutes:** from raw ball-by-ball events to boardroom-ready trend cuts.
- **Transparent AI:** every natural-language output is backed by inspectable SQL.
- **Scalable foundation:** lightweight stack (Streamlit + SQLite + Gemini) with clear migration path to managed data warehouses.

In short, this is not just a dashboard. It is a decision-support system where cricket intuition and statistical rigor meet.


## What You Can Ask

- Who are the top death-over wicket takers since 2018?
- How does powerplay strike rate differ by venue?
- Which bowlers maintain the best economy against specific batting units?
- How have batting acceleration patterns changed by season?

## Product Highlights

- **Natural Language -> SQL** with Gemini
- **Direct SQL Studio** (no AI call required)
- **Schema-aware SQL generation** grounded on real columns
- **Interactive chart builder** with dynamic X/Y selection
- **Name normalization** for player aliases (for example, `Virat Kohli` -> `V Kohli`)
- **Downloadable result datasets** as CSV

## Architecture

Flow:
`User Query -> Gemini SQL Generation -> SQLite Execution -> Streamlit Visualization`

Code layout:

- `app.py` - Streamlit application, chat/SQL studio, visualization
- `database.py` - CSV -> SQLite, indexing, alias mapping, query execution
- `ai_engine.py` - Gemini prompt and SQL generation rules
- `architecture.md` - system-level architecture notes
- `SKILL.md` - cricket analytics capabilities supported by the assistant

## Data Model

- Single flat table: `deliveries`
- Indexed dimensions: `bowler`, `batter`, `match_id`, `venue`
- Designed for low-friction analytics and LLM reliability (no join guessing)

## Run Locally

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Add your API key in `.streamlit/secrets.toml`:
   - `GEMINI_API_KEY="your_key_here"`
3. Place dataset as `data.csv` in project root.
4. Start app:
   - `streamlit run app.py`

## Deployment Notes (Streamlit Community Cloud)

- Add `GEMINI_API_KEY` in Streamlit app Secrets (never commit it).
- Dataset and DB are intentionally excluded from Git in this repo template.
- Configure runtime paths using environment variables if needed:
- `CSV_PATH` (default: `data.csv`, can also be an `https://` CSV URL)
  - `DB_PATH` (default: `cricket.db`)

### One-Click Streamlit Cloud Setup

1. Go to [Streamlit Community Cloud](https://share.streamlit.io/).
2. Select repo: `VikAnalytics/ipl-analytics`
3. Main file: `app.py`
4. In app settings, set:
   - **Secrets**:
     - `GEMINI_API_KEY = "your_key"`
   - **Environment variables**:
     - `CSV_PATH = "https://<your-public-host>/data.csv"` (recommended for cloud)
     - optional `DB_PATH = "cricket.db"`
5. Deploy.

If `CSV_PATH` is a URL, the app loads data directly from that source and builds SQLite on startup.
