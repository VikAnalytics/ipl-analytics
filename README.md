# IPL Analytics

> Ask any question about eighteen seasons of Indian Premier League cricket. AI converts your words to SQL, runs it against 282,974 ball-by-ball deliveries, and returns the answer in seconds.

**Live → [ipl-master.vercel.app](https://ipl-master.vercel.app)**

---

## What it does

Type a question in plain English. The platform uses **Google Gemini 2.5 Flash** to generate a PostgreSQL query, executes it against a live **Supabase** database, and renders the result as a sortable table, chart, or raw SQL — all in the browser, no login required.

Prefer writing SQL yourself? Switch to **SQL mode** for a full raw query interface with an inline schema reference.

---

## Example questions

```
Who are the top 10 run scorers of all time?
Virat Kohli's strike rate by season
Best death-over bowlers since 2018
Which venues favour bowlers the most?
Head-to-head: CSK vs MI win percentage by season
Most sixes hit in a single IPL season
Economy rate of spinners in powerplay overs
```

---

## Features

| | |
|---|---|
| **AI Query** | Natural language → SQL via Gemini 2.5 Flash |
| **Raw SQL Mode** | Write and run PostgreSQL directly, with inline schema reference |
| **REST API** | Paginated, filterable access to all 9 IPL tables |
| **Champions** | Hall of Champions derived live from match results |
| **Live Stats** | Delivery/match/player counts fetched from DB on load |
| **Charts** | Auto-generated bar/line charts with dynamic axis selection |
| **CSV Export** | Download any result set |
| **Player Aliases** | `Virat Kohli` → `V Kohli` normalisation before query generation |
| **Rate Limiting** | 20 requests/min per IP |
| **Read-only** | INSERT/UPDATE/DELETE/DROP blocked at query execution layer |

---

## Dataset

| Stat | Value |
|---|---|
| Deliveries | 282,974 |
| Matches | 1,190 |
| Seasons | 2008 – 2025 |
| Players | 945 |
| Tables | 9 normalised Supabase tables |

**Tables:** `deliveries` · `matches` · `innings` · `players` · `teams` · `match_players` · `officials` · `powerplays` · `player_season`

Data is static — ball-by-ball IPL records hosted in Supabase PostgreSQL. No CSV or local DB file required.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Vanilla HTML / CSS / JS — single file, zero build step |
| Backend | FastAPI (`server.py`) |
| AI | Google Gemini 2.5 Flash (`google-generativeai`) |
| Database | Supabase PostgreSQL via `psycopg2-binary` (connection pooler) |
| Deployment | Vercel (Python 3.12 runtime) |

---

## Project structure

```
.
├── server.py              FastAPI app — all endpoints, rate limiting, security headers
├── index.html             Single-page frontend
├── config.py              Gemini model, prompt tables, template strings
├── api/
│   └── index.py           Vercel entry point (imports app from server.py)
├── vercel.json            Routes all traffic → api/index
├── core/
│   ├── database.py        Supabase connection, query execution, alias normalisation
│   └── ai_engine.py       Gemini prompt construction and SQL generation
├── static/
│   ├── immersive.css      Cinematic section overrides
│   └── seq/               Scroll-sequence images
├── tests/                 30 tests — database, ai_engine, aliases
├── docs/
│   ├── architecture.md    System flow and data layer design
│   └── SKILL.md           65+ documented analytics capabilities
├── requirements.txt       Production dependencies (pinned)
└── requirements-dev.txt   Dev dependencies (adds pytest, uvicorn)
```

---

## API

Full programmatic access — no key required.

### List tables
```
GET /api/tables
```

### Query a table
```
GET /api/tables/{table}?limit=100&offset=0&order_by=runs_batter&order_dir=desc
```

Filter by any column:
```
GET /api/tables/deliveries?batter=V+Kohli&phase=powerplay&limit=50
GET /api/tables/matches?season=2023&order_by=match_date&order_dir=desc
```

### AI query
```
POST /api/query
Content-Type: application/json

{ "question": "Top 10 run scorers of all time" }
```

### Raw SQL
```
POST /api/sql
Content-Type: application/json

{ "sql": "SELECT batter, SUM(runs_batter) AS runs FROM deliveries GROUP BY batter ORDER BY runs DESC LIMIT 10" }
```

### Live stats
```
GET /api/stats
```

### Champions
```
GET /api/champions
```

Full interactive docs at `/docs` (Swagger UI).

---

## Run locally

```bash
git clone https://github.com/VikAnalytics/ipl-analytics.git
cd ipl-analytics

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
```

Create `.streamlit/secrets.toml`:

```toml
GEMINI_API_KEY         = "your_gemini_key"
SUPABASE_DATABASE_URL  = "postgresql://postgres.[ref]:[password]@aws-[n]-[region].pooler.supabase.com:6543/postgres"
```

```bash
uvicorn server:app --reload
# → http://localhost:8000
```

---

## Deploy to Vercel

```bash
vercel --prod
```

Set environment variables:

```bash
vercel env add GEMINI_API_KEY production
vercel env add SUPABASE_DATABASE_URL production
```

> **Supabase URL:** Use the **connection pooler** URL (Transaction mode, port 6543), not the direct `db.*.supabase.co` host. Vercel resolves the direct host to IPv6 only, which Supabase blocks.
>
> Find it: Supabase dashboard → Settings → Database → Connection Pooling → Transaction mode

---

## Key implementation notes

**Over numbering** — `over_number` in the database is 1-indexed (1–20). The `phase` column is pre-computed (`powerplay` / `middle` / `death`) and preferred over filtering by over number.

**Cricket formulas**
- Strike rate: `(SUM(runs_batter) * 100.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides=0 AND extras_noballs=0), 0)`
- Economy: `(SUM(runs_total) * 6.0) / NULLIF(COUNT(*) FILTER (WHERE extras_wides=0 AND extras_noballs=0), 0)`

**Security** — all SQL identifiers are whitelisted; values are parameterised. Only `SELECT` and `WITH` (CTEs) are permitted. Security headers (CSP, X-Frame-Options, Referrer-Policy) applied via FastAPI middleware.

---

## License

Data © ESPN Cricinfo / Cricsheet. Code MIT.
