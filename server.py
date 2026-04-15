from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import psycopg2
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from core.ai_engine import generate_sql
from core.database import execute_query, get_player_alias_map, get_schema_for_prompt, get_table_columns

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# ── Secrets ───────────────────────────────────────────────────────────────────

def _load_toml(path: Path) -> dict:
    result: dict = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip().strip('"').strip("'")
    return result


_secrets: dict = {}
_secrets_path = Path(".streamlit/secrets.toml")
if _secrets_path.exists():
    try:
        _secrets = _load_toml(_secrets_path)
    except Exception as exc:
        log.warning("Could not load secrets.toml: %s", exc)


def get_secret(key: str) -> str:
    return os.getenv(key) or _secrets.get(key, "")


GEMINI_API_KEY = get_secret("GEMINI_API_KEY")
DATABASE_URL   = get_secret("SUPABASE_DATABASE_URL")

# ── Table whitelist + column cache ────────────────────────────────────────────

ALLOWED_TABLES: frozenset[str] = frozenset({
    "deliveries", "matches", "innings", "players", "teams",
    "match_players", "officials", "powerplays", "player_season",
})

_col_cache: dict[str, list[str]] = {}


def _cols(table: str) -> list[str]:
    """Return (cached) column list for a whitelisted table."""
    if table not in _col_cache:
        _col_cache[table] = get_table_columns(DATABASE_URL, table)
    return _col_cache[table]


def _conn():
    return psycopg2.connect(DATABASE_URL, connect_timeout=10, sslmode="require")


def _run(sql: str, params: tuple = ()) -> tuple[list[str], list[list[Any]], int]:
    """Execute parameterized SELECT, return (columns, rows, total_count)."""
    with _conn() as conn:
        with conn.cursor() as cur:
            # total count — wrap query in a COUNT(*)
            count_sql = f"SELECT COUNT(*) FROM ({sql.rstrip(';')}) _q"
            cur.execute(count_sql, params)
            total = cur.fetchone()[0]
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [d[0] for d in cur.description]
            rows = [list(r) for r in cur.fetchall()]
    return cols, rows, total


# ── AI query helpers ──────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def resolve_aliases(question: str) -> tuple[str, list[str]]:
    try:
        alias_map = get_player_alias_map(database_url=DATABASE_URL)
    except Exception:
        return question, []
    if not alias_map:
        return question, []
    rewritten, norm, notes = question, _normalize(question), []
    for alias in sorted(alias_map, key=len, reverse=True):
        canonical = alias_map[alias]
        if not canonical or not re.search(r"\b" + re.escape(alias) + r"\b", norm):
            continue
        pattern = r"\b" + r"\s+".join(re.escape(t) for t in alias.split()) + r"\b"
        updated = re.sub(pattern, canonical, rewritten, flags=re.IGNORECASE)
        if updated != rewritten:
            rewritten, norm = updated, _normalize(updated)
            notes.append(f"{alias} → {canonical}")
    return rewritten, notes


# ── Rate limiter (in-memory, per IP) ─────────────────────────────────────────

_rate_store: dict[str, list[float]] = defaultdict(list)
_RATE_LIMIT  = 20   # max requests
_RATE_WINDOW = 60   # per seconds

def _check_rate_limit(ip: str) -> None:
    now = time.time()
    window_start = now - _RATE_WINDOW
    calls = _rate_store[ip] = [t for t in _rate_store[ip] if t > window_start]
    if len(calls) >= _RATE_LIMIT:
        raise HTTPException(429, "Too many requests — slow down")
    calls.append(now)


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="IPL Analytics API",
    description="Ball-by-ball IPL data (2008–2025). Read-only REST access + AI-powered NL-to-SQL.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # read-only public data — open is fine; tighten if needed
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"]        = "DENY"
    response.headers["Referrer-Policy"]        = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src https://fonts.gstatic.com; "
        "img-src 'self' data: https://upload.wikimedia.org; "
        "connect-src 'self';"
    )
    return response


# ── Serve HTML ────────────────────────────────────────────────────────────────

_HTML = Path(__file__).parent / "index.html"

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
async def serve_index() -> str:
    return _HTML.read_text(encoding="utf-8")


# ── AI query ──────────────────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=500)


@app.post(
    "/api/query",
    summary="AI-powered NL-to-SQL query",
    tags=["AI"],
)
async def ai_query(req: QueryRequest, request: Request) -> dict:
    """
    Convert a natural-language question to SQL via Gemini 2.5 Flash,
    execute it against the Supabase database, and return results.
    """
    _check_rate_limit(request.client.host)

    if not GEMINI_API_KEY:
        raise HTTPException(503, "GEMINI_API_KEY not configured")
    if not DATABASE_URL:
        raise HTTPException(503, "SUPABASE_DATABASE_URL not configured")

    question = req.question.strip()
    if not question:
        raise HTTPException(400, "Question cannot be empty")

    try:
        schema = get_schema_for_prompt(database_url=DATABASE_URL)
        if not schema:
            raise HTTPException(503, "Cannot reach database schema")
        rewritten, alias_notes = resolve_aliases(question)
        sql = generate_sql(user_question=rewritten, schema=schema, api_key=GEMINI_API_KEY)
        df  = execute_query(sql, database_url=DATABASE_URL)
        df  = df.where(pd.notnull(df), None)
        return {
            "sql":         sql,
            "columns":     list(df.columns),
            "rows":        df.values.tolist(),
            "row_count":   len(df),
            "alias_notes": alias_notes,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("AI query failed")
        raise HTTPException(500, "Query failed — check server logs")


# ── Live stats ────────────────────────────────────────────────────────────────

@app.get(
    "/api/stats",
    summary="Live row counts for hero stats",
    tags=["Data"],
)
async def get_stats() -> dict:
    """Return live counts: deliveries, matches, seasons, players."""
    if not DATABASE_URL:
        raise HTTPException(503, "Database not configured")
    try:
        sql = """
            SELECT
                (SELECT COUNT(*) FROM deliveries) AS deliveries,
                (SELECT COUNT(*) FROM matches)    AS matches,
                (SELECT COUNT(DISTINCT season) FROM matches) AS seasons,
                (SELECT COUNT(*) FROM players)    AS players
        """
        cols, rows, _ = _run(sql)
        d = dict(zip(cols, rows[0]))
        return {
            "deliveries": int(d["deliveries"]),
            "matches":    int(d["matches"]),
            "seasons":    int(d["seasons"]),
            "players":    int(d["players"]),
        }
    except Exception as exc:
        log.exception("get_stats failed")
        raise HTTPException(500, "Failed to load stats")


# ── Champions ─────────────────────────────────────────────────────────────────

@app.get(
    "/api/champions",
    summary="IPL champions by season derived from match results",
    tags=["Data"],
)
async def get_champions() -> dict:
    """
    Return each season's champion (winner of the last match played that season).
    Groups by team: title count + winning years.
    """
    if not DATABASE_URL:
        raise HTTPException(503, "Database not configured")
    try:
        sql = """
            SELECT season, outcome_winner
            FROM (
                SELECT DISTINCT ON (season) season, outcome_winner, match_date
                FROM matches
                WHERE outcome_winner IS NOT NULL
                ORDER BY season, match_date DESC
            ) finals
            ORDER BY season
        """
        _, rows, _ = _run(sql)
        # rows: [[season, winner], ...]
        champions: dict[str, dict] = {}
        for season, winner in rows:
            if winner not in champions:
                champions[winner] = {"team": winner, "titles": 0, "years": []}
            champions[winner]["titles"] += 1
            champions[winner]["years"].append(str(season))
        result = sorted(champions.values(), key=lambda x: (-x["titles"], x["years"][0]))
        return {"champions": result}
    except Exception as exc:
        log.exception("get_champions failed")
        raise HTTPException(500, "Failed to load champions")


# ── Table catalog ─────────────────────────────────────────────────────────────

@app.get(
    "/api/tables",
    summary="List all tables and their columns",
    tags=["Data"],
)
async def list_tables() -> dict:
    """Return every available table with its column names."""
    if not DATABASE_URL:
        raise HTTPException(503, "Database not configured")
    try:
        return {
            "tables": {
                table: _cols(table)
                for table in sorted(ALLOWED_TABLES)
            }
        }
    except Exception as exc:
        log.exception("list_tables failed")
        raise HTTPException(500, "Failed to load table catalog")


# ── Generic table endpoint ────────────────────────────────────────────────────

@app.get(
    "/api/tables/{table}",
    summary="Query any table with filters, sorting, and pagination",
    tags=["Data"],
)
async def query_table(
    request: Request,
    table: str,
    limit: int  = Query(100, ge=1,  le=1000, description="Rows to return (max 1000)"),
    offset: int = Query(0,   ge=0,           description="Rows to skip"),
    order_by:  Optional[str] = Query(None, description="Column to sort by"),
    order_dir: str        = Query("asc", pattern="^(asc|desc)$", description="asc or desc"),
) -> dict:
    """
    Paginated, filterable access to any IPL table.

    **Filtering** — add any column name as a query param to filter by exact value:
    ```
    /api/tables/deliveries?batter=V+Kohli&phase=powerplay&limit=50
    /api/tables/matches?season=2023&order_by=match_date&order_dir=desc
    /api/tables/players?nationality=Indian&playing_role=Batter
    ```

    **Pagination** — use `limit` + `offset`:
    ```
    /api/tables/deliveries?limit=100&offset=200
    ```
    """
    if not DATABASE_URL:
        raise HTTPException(503, "Database not configured")

    if table not in ALLOWED_TABLES:
        raise HTTPException(
            404,
            f"Table '{table}' not found. Available: {sorted(ALLOWED_TABLES)}",
        )

    valid_cols = _cols(table)
    if not valid_cols:
        raise HTTPException(404, f"Table '{table}' has no columns — check DB connection")

    # Reserved params already captured by FastAPI
    reserved = {"limit", "offset", "order_by", "order_dir"}

    # Remaining query params → column filters (whitelist column names)
    filter_params = {
        k: v for k, v in request.query_params.items()
        if k not in reserved
    }
    bad_cols = [k for k in filter_params if k not in valid_cols]
    if bad_cols:
        raise HTTPException(
            400,
            f"Unknown filter column(s): {bad_cols}. Valid columns: {valid_cols}",
        )

    # Validate order_by column
    if order_by and order_by not in valid_cols:
        raise HTTPException(
            400,
            f"Invalid order_by column '{order_by}'. Valid columns: {valid_cols}",
        )

    # Build SQL — table/column identifiers are whitelisted, values are parameterized
    where_parts = [f"{col} = %s" for col in filter_params]
    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""
    order_clause = f"ORDER BY {order_by} {order_dir.upper()}" if order_by else ""

    sql = f"""
        SELECT *
        FROM {table}
        {where_clause}
        {order_clause}
        LIMIT %s OFFSET %s
    """.strip()

    params = (*filter_params.values(), limit, offset)

    try:
        cols, rows, total = _run(sql, params)
        # Serialize non-JSON-safe types (dates, decimals, etc.)
        safe_rows = [
            [v.isoformat() if hasattr(v, "isoformat") else
             float(v) if hasattr(v, "__float__") and not isinstance(v, (int, float, str, bool, type(None))) else v
             for v in row]
            for row in rows
        ]
        return {
            "table":      table,
            "columns":    cols,
            "rows":       safe_rows,
            "row_count":  len(rows),
            "total":      total,
            "limit":      limit,
            "offset":     offset,
            "filters":    filter_params,
        }
    except HTTPException:
        raise
    except Exception as exc:
        log.exception("query_table failed: %s", exc)
        raise HTTPException(500, "Query failed — check server logs")
