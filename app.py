from __future__ import annotations

import logging
import os
import re
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)

import pandas as pd
import streamlit as st

from ai_engine import generate_sql
from database import (
    execute_query,
    get_dataset_stats,
    get_player_alias_map,
    get_schema_for_prompt,
    get_table_columns,
)

st.set_page_config(
    page_title="IPL Analytics",
    page_icon="🏏",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ────────────────────────────────────────────────────────────────────────
GLASS_CSS = """
<style>
.stApp {
    background: radial-gradient(ellipse at top left, #0d1b4b 0%, #080f2e 55%, #04071e 100%);
    color: #e8edf8;
}

/* KPI cards */
.kpi-card {
    background: rgba(255,255,255,0.04);
    backdrop-filter: blur(18px);
    -webkit-backdrop-filter: blur(18px);
    border: 1px solid rgba(255,255,255,0.09);
    border-radius: 16px;
    padding: 18px 22px;
    margin-bottom: 10px;
    transition: transform 0.22s cubic-bezier(.34,1.56,.64,1),
                box-shadow 0.22s ease,
                border-color 0.22s ease;
    cursor: default;
}
.kpi-card:hover {
    transform: translateY(-7px);
    box-shadow: 0 22px 48px rgba(0,0,0,0.45), 0 0 28px rgba(90,140,255,0.18);
    border-color: rgba(90,140,255,0.35);
}
.kpi-title {
    font-size: 0.78rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #8aa0d4 !important;
    margin-bottom: 6px;
}
.kpi-value {
    font-size: 2rem;
    font-weight: 700;
    color: #f4c95d !important;
    line-height: 1.1;
}

/* Chat — Claude-style */
[data-testid="stVerticalBlockBorderWrapper"]:has([data-testid="stChatMessage"]) {
    max-width: 820px;
    margin: 0 auto;
}
.stChatMessage {
    background: transparent !important;
    border: none !important;
    border-radius: 0 !important;
    backdrop-filter: none !important;
    padding: 1rem 0.25rem !important;
    border-bottom: 1px solid rgba(255,255,255,0.045) !important;
}
.stChatMessage:last-child { border-bottom: none !important; }
.stChatMessage:has([data-testid="stChatMessageAvatarUser"]) {
    background: rgba(244,201,93,0.05) !important;
    border: 1px solid rgba(244,201,93,0.1) !important;
    border-radius: 12px !important;
    padding: 0.85rem 1.1rem !important;
}
[data-testid="stChatMessageAvatarUser"],
[data-testid="stChatMessageAvatarAssistant"] {
    width: 28px !important;
    height: 28px !important;
    min-width: 28px !important;
    border-radius: 6px !important;
    background: rgba(255,255,255,0.06) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
}
[data-testid="stChatMessageContent"] {
    font-size: 0.95rem;
    line-height: 1.7;
    color: #dde4f5 !important;
}

/* Chat input */
[data-testid="stChatInputContainer"] {
    background: rgba(4,8,28,0.95) !important;
    border-top: 1px solid rgba(255,255,255,0.07) !important;
    backdrop-filter: blur(20px);
    padding: 0.6rem 1rem !important;
}
[data-testid="stChatInputContainer"] textarea {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(255,255,255,0.1) !important;
    border-radius: 10px !important;
    color: #e8edf8 !important;
    font-size: 0.95rem !important;
}
[data-testid="stChatInputContainer"] textarea:focus {
    border-color: rgba(90,140,255,0.45) !important;
    box-shadow: 0 0 0 2px rgba(90,140,255,0.12) !important;
}

/* Tabs */
[data-testid="stTabs"] button {
    color: #8aa0d4 !important;
    font-size: 0.88rem;
    font-weight: 500;
    border-radius: 10px 10px 0 0;
    transition: color 0.15s, background 0.15s;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #f4c95d !important;
    border-bottom: 2px solid #f4c95d !important;
    background: rgba(244,201,93,0.07) !important;
}
[data-testid="stTabsContent"] > div {
    animation: tabFadeIn 0.28s ease-out;
}
@keyframes tabFadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* Thinking animation */
.thinking-wrap {
    display: flex;
    align-items: center;
    gap: 14px;
    padding: 16px 22px;
    background: rgba(255,255,255,0.04);
    border: 1px solid rgba(90,140,255,0.2);
    border-radius: 14px;
    margin: 8px 0;
}
.thinking-label { font-size: 0.9rem; color: #8aa0d4; letter-spacing: 0.04em; }
.thinking-dots { display: flex; gap: 6px; }
.thinking-dots span {
    width: 9px; height: 9px;
    border-radius: 50%;
    background: linear-gradient(135deg, #5a8cff, #a78bfa);
    animation: dotBounce 1.3s ease-in-out infinite;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.18s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.36s; }
@keyframes dotBounce {
    0%, 80%, 100% { transform: scale(0.55); opacity: 0.4; }
    40%           { transform: scale(1.1);  opacity: 1;   }
}

/* Prompt chips */
.prompt-chip button {
    background: rgba(255,255,255,0.04) !important;
    border: 1px solid rgba(90,140,255,0.28) !important;
    border-radius: 999px !important;
    color: #b0c4f0 !important;
    font-size: 0.85rem !important;
    padding: 0.38rem 1.1rem !important;
    transition: background 0.16s, border-color 0.16s, transform 0.16s;
}
.prompt-chip button:hover {
    background: rgba(90,140,255,0.12) !important;
    border-color: rgba(90,140,255,0.6) !important;
    color: #f4c95d !important;
    transform: translateY(-2px);
}

/* Welcome hero */
.welcome-hero {
    text-align: center;
    padding: 2.8rem 1rem 1.8rem;
}
.welcome-hero .hero-emoji { font-size: 3.2rem; line-height: 1; }
.welcome-hero .hero-title {
    font-size: 1.6rem; font-weight: 700;
    color: #f8f9fc !important; margin-top: 0.7rem;
}
.welcome-hero .hero-sub {
    font-size: 0.95rem; color: #8aa0d4 !important; margin-top: 0.5rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: rgba(6,12,36,0.88) !important;
    border-right: 1px solid rgba(255,255,255,0.07) !important;
    backdrop-filter: blur(14px);
}

/* Metric strip */
[data-testid="stMetric"] {
    background: rgba(255,255,255,0.03);
    border-radius: 10px;
    padding: 8px 12px !important;
}

/* Code blocks */
code, .stCode {
    background: rgba(4,8,28,0.92) !important;
    border: 1px solid rgba(255,255,255,0.08) !important;
    border-radius: 10px !important;
    color: #c9d8f8 !important;
}

h1, h2, h3, h4, h5, h6, p, label { color: #e8edf8 !important; }
</style>
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_api_key() -> str:
    try:
        return st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")


def get_database_url() -> str:
    try:
        return st.secrets.get("SUPABASE_DATABASE_URL", os.getenv("SUPABASE_DATABASE_URL", ""))
    except Exception:
        return os.getenv("SUPABASE_DATABASE_URL", "")


def _normalize_free_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text.lower())).strip()


def resolve_player_aliases(question: str, database_url: str) -> tuple[str, list[str]]:
    alias_map = get_player_alias_map(database_url=database_url)
    if not alias_map:
        return question, []

    rewritten = question
    normalized = _normalize_free_text(rewritten)
    notes: list[str] = []

    for alias in sorted(alias_map.keys(), key=len, reverse=True):
        canonical = alias_map[alias]
        if not canonical or not re.search(r"\b" + re.escape(alias) + r"\b", normalized):
            continue
        pattern = r"\b" + r"\s+".join(re.escape(t) for t in alias.split() if t) + r"\b"
        updated = re.sub(pattern, canonical, rewritten, flags=re.IGNORECASE)
        if updated != rewritten:
            rewritten = updated
            normalized = _normalize_free_text(rewritten)
            notes.append(f"{alias} → {canonical}")

    return rewritten, notes


def _safe_col(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "col"


def typewriter_sql(sql: str, container) -> None:
    placeholder = container.empty()
    step = max(4, len(sql) // 55)
    for i in range(step, len(sql), step):
        placeholder.code(sql[:i], language="sql")
        time.sleep(0.018)
    placeholder.code(sql, language="sql")


def show_thinking(placeholder) -> None:
    placeholder.markdown(
        """
        <div class="thinking-wrap">
            <span class="thinking-label">AI is thinking</span>
            <div class="thinking-dots"><span></span><span></span><span></span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── UI components ──────────────────────────────────────────────────────────────

def render_kpis(stats: dict[str, str]) -> None:
    for col, title, value in zip(
        st.columns(3),
        ["Total Deliveries", "Unique Matches", "Seasons Covered"],
        [stats["deliveries"], stats["matches"], stats["seasons"]],
    ):
        with col:
            st.markdown(
                f'<div class="kpi-card"><div class="kpi-title">{title}</div>'
                f'<div class="kpi-value">{value}</div></div>',
                unsafe_allow_html=True,
            )


def render_chart(df: pd.DataFrame, chart_key: str) -> None:
    if df.empty:
        st.info("No rows to chart.")
        return
    numeric_cols = list(df.select_dtypes(include="number").columns)
    if not numeric_cols:
        st.info("No numeric columns available for charting.")
        return

    all_cols = list(df.columns)
    x_default = next((c for c in all_cols if c not in numeric_cols), all_cols[0])

    c1, c2, c3 = st.columns(3)
    x_col = c1.selectbox("X-axis", all_cols, index=all_cols.index(x_default), key=f"{chart_key}_x")
    y_col = c2.selectbox("Y-axis", numeric_cols, key=f"{chart_key}_y")
    chart_type = c3.selectbox("Chart type", ["Bar", "Line", "Scatter"], key=f"{chart_key}_type")

    chart_df = df[[x_col, y_col]].dropna().head(200).copy()
    if chart_df.empty:
        st.info("No chartable rows after dropping nulls.")
        return

    chart_df[x_col] = chart_df[x_col].astype(str)
    sx, sy = _safe_col(x_col), _safe_col(y_col)
    if sx == sy:
        sy += "_value"
    chart_df = chart_df.rename(columns={x_col: sx, y_col: sy})

    if chart_type == "Bar":
        st.bar_chart(chart_df.set_index(sx), width="stretch")
    elif chart_type == "Line":
        st.line_chart(chart_df.set_index(sx), width="stretch")
    else:
        st.scatter_chart(chart_df, x=sx, y=sy, width="stretch")


def render_response(payload: dict, response_key: str) -> None:
    if payload.get("text"):
        st.markdown(payload["text"])
    if payload.get("error"):
        st.error(payload["error"])

    df  = payload.get("data")
    sql = payload.get("sql", "")
    if df is None and not sql:
        return

    tab_data, tab_sql, tab_viz = st.tabs(["Data Preview", "SQL Logic", "Visual Analytics"])

    with tab_data:
        if df is not None and not df.empty:
            st.dataframe(df, use_container_width=True, height=400)
            m1, m2, m3 = st.columns(3)
            m1.metric("Rows", f"{len(df):,}")
            m2.metric("Columns", f"{len(df.columns):,}")
            m3.download_button(
                "Download CSV",
                data=df.to_csv(index=False).encode("utf-8"),
                file_name=f"{response_key}.csv",
                mime="text/csv",
                use_container_width=True,
                key=f"{response_key}_dl",
            )
        else:
            st.info("No rows returned.")

    with tab_sql:
        if sql:
            typed_set: set = st.session_state.setdefault("typed_messages", set())
            if response_key not in typed_set:
                typed_set.add(response_key)
                typewriter_sql(sql, st.container())
            else:
                st.code(sql, language="sql")
        else:
            st.info("No SQL available.")

    with tab_viz:
        if df is not None:
            render_chart(df, chart_key=response_key)
        else:
            st.info("Run a query to see charts.")


_EXAMPLE_PROMPTS = [
    ("🏆", "Top 10 run scorers of all time"),
    ("🎯", "Best death-over bowlers since 2018"),
    ("📈", "Virat Kohli's year-on-year run tally"),
    ("🏟️", "Powerplay economy rate by venue"),
    ("💥", "Most sixes in a single season"),
    ("⚔️", "Head-to-head: CSK vs MI matches"),
]


def render_welcome() -> None:
    st.markdown(
        """
        <div class="welcome-hero">
            <div class="hero-emoji">🏏</div>
            <div class="hero-title">IPL AI Analyst</div>
            <div class="hero-sub">Ask any cricket analytics question in plain English</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    cols = st.columns(2)
    for i, (icon, text) in enumerate(_EXAMPLE_PROMPTS):
        with cols[i % 2]:
            st.markdown('<div class="prompt-chip">', unsafe_allow_html=True)
            if st.button(f"{icon}  {text}", use_container_width=True, key=f"_eg_{i}"):
                st.session_state["_prefill"] = text
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)


# ── App ────────────────────────────────────────────────────────────────────────

st.markdown(GLASS_CSS, unsafe_allow_html=True)
st.session_state.setdefault("messages", [])
st.session_state.setdefault("message_counter", 0)
st.session_state.setdefault("direct_sql", "SELECT * FROM deliveries LIMIT 50")
st.session_state.setdefault("typed_messages", set())

api_key      = get_api_key()
database_url = get_database_url()

with st.sidebar:
    st.markdown("## IPL Analytics")
    st.caption("Powered by Gemini 2.5 Flash + Supabase")
    st.divider()
    st.markdown(
        """
**How to use**
1. Type a question in **AI Analyst** to get SQL-powered answers.
2. Use **SQL Studio** for direct queries — no Gemini calls.
3. Explore results across **Data Preview**, **SQL Logic**, and **Visual Analytics** tabs.
4. Download any result as CSV.
        """
    )
    st.divider()
    if st.button("Clear chat history", use_container_width=True):
        st.session_state.messages = []
        st.session_state.message_counter = 0
        st.session_state.typed_messages = set()
        st.rerun()
    st.divider()
    st.caption("Dataset: IPL ball-by-ball 2008–2025 · Static")

if not database_url:
    st.error("Supabase not configured. Set `SUPABASE_DATABASE_URL` in `.streamlit/secrets.toml`.")
    st.stop()

st.title("IPL Analytics")
st.caption("Natural-language cricket analytics — 2008 to 2025.")
render_kpis(get_dataset_stats(database_url=database_url))
st.divider()

tab_ai, tab_sql_studio = st.tabs(["AI Analyst", "SQL Studio"])

with tab_ai:
    if not api_key:
        st.warning("Gemini API key not configured. Add `GEMINI_API_KEY` to secrets.")

    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            render_response(msg, response_key=msg.get("id", f"history_{idx}"))

    if not st.session_state.messages:
        render_welcome()

    question = st.chat_input("Ask anything about IPL…")
    if not question:
        question = st.session_state.pop("_prefill", None)

    if question:
        counter      = st.session_state.message_counter
        assistant_id = f"assistant_{counter}"

        st.session_state.messages.append({"id": f"user_{counter}", "role": "user", "text": question})
        with st.chat_message("user"):
            st.markdown(question)

        assistant_payload: dict = {"id": assistant_id, "role": "assistant"}
        with st.chat_message("assistant"):
            thinking_ph = st.empty()
            show_thinking(thinking_ph)
            try:
                if not api_key:
                    raise ValueError("Gemini API key missing — configure secrets and retry.")
                schema = get_schema_for_prompt(database_url=database_url)
                if not schema:
                    raise ValueError("No schema found. Check your Supabase connection.")
                rewritten, alias_notes = resolve_player_aliases(question, database_url=database_url)
                sql       = generate_sql(user_question=rewritten, schema=schema, api_key=api_key)
                result_df = execute_query(sql, database_url=database_url)
                thinking_ph.empty()

                row_count = len(result_df)
                summary = (
                    f"Here {'is' if row_count == 1 else 'are'} the results — "
                    f"**{row_count:,}** {'row' if row_count == 1 else 'rows'} returned."
                )
                if alias_notes:
                    summary += f"\n\n*Names normalized: {', '.join(alias_notes[:5])}*"
                assistant_payload.update({"text": summary, "sql": sql, "data": result_df})
            except Exception as exc:
                thinking_ph.empty()
                assistant_payload.update({"text": "I couldn't complete that request.", "error": str(exc)})

            render_response(assistant_payload, response_key=assistant_id)

        st.session_state.messages.append(assistant_payload)
        st.session_state.message_counter = counter + 1

with tab_sql_studio:
    st.markdown("### SQL Studio")
    st.caption("Run read-only PostgreSQL directly against Supabase. No Gemini calls.")

    with st.expander("Schema reference", expanded=False):
        try:
            cols = get_table_columns(database_url=database_url)
            if cols:
                st.markdown("**`deliveries`** table")
                st.caption(f"{len(cols)} columns")
                st.code(", ".join(cols))
        except Exception as exc:
            st.info(f"Could not load schema: {exc}")

    direct_sql = st.text_area("SQL Query", value=st.session_state.direct_sql, height=200)
    st.session_state.direct_sql = direct_sql

    run_col, sample_col = st.columns([1, 2])
    run_clicked = run_col.button("Run SQL", type="primary", use_container_width=True)
    sample_col.code(
        "SELECT batter, SUM(runs_batter) AS runs\nFROM deliveries\n"
        "GROUP BY batter\nORDER BY runs DESC\nLIMIT 20",
        language="sql",
    )

    if run_clicked:
        try:
            with st.spinner("Executing…"):
                result_df = execute_query(direct_sql, database_url=database_url)
            st.session_state.direct_sql_result = {
                "id": "studio_result",
                "text": f"Returned **{len(result_df):,}** rows.",
                "sql": direct_sql,
                "data": result_df,
            }
        except Exception as exc:
            st.session_state.direct_sql_result = {
                "id": "studio_result",
                "text": "Query failed.",
                "sql": direct_sql,
                "error": str(exc),
            }

    if st.session_state.get("direct_sql_result"):
        render_response(st.session_state.direct_sql_result, response_key="studio_result")
