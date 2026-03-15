from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd
import streamlit as st

from ai_engine import generate_sql
from database import (
    DEFAULT_CSV_PATH,
    DEFAULT_DB_PATH,
    execute_query,
    get_player_alias_map,
    get_table_columns,
    init_db,
    refresh_player_aliases,
)

st.set_page_config(page_title="IPL Analytics", layout="wide")


def apply_theme() -> None:
    st.markdown(
        """
        <style>
          .stApp {
            background: radial-gradient(circle at top right, #1b2f78 0%, #10204f 42%, #0a1637 100%);
            color: #f8f9fc;
          }
          h1, h2, h3, h4, h5, h6, p, div, span, label { color: #f8f9fc !important; }
          .stChatMessage {
            background: rgba(7, 18, 52, 0.72);
            border: 1px solid rgba(218, 169, 74, 0.22);
            border-radius: 14px;
            backdrop-filter: blur(4px);
          }
          [data-testid="stChatInputContainer"] {
            border-top: 1px solid rgba(218, 169, 74, 0.35);
            background: rgba(6, 16, 44, 0.96);
          }
          .kpi-card {
            border: 1px solid rgba(218, 169, 74, 0.35);
            border-radius: 12px;
            padding: 14px;
            background: rgba(9, 24, 63, 0.72);
            margin-bottom: 8px;
          }
          .kpi-title {
            font-size: 0.85rem;
            color: #d7dff7 !important;
            margin-bottom: 2px;
          }
          .kpi-value {
            font-size: 1.4rem;
            font-weight: 700;
            color: #f4c95d !important;
          }
          code {
            background-color: rgba(8, 20, 56, 0.96) !important;
            color: #e8ecfa !important;
          }
          /* Example prompt chip buttons */
          .prompt-chip button {
            background: rgba(255,255,255,0.05) !important;
            border: 1px solid rgba(218, 169, 74, 0.30) !important;
            border-radius: 999px !important;
            color: #d7dff7 !important;
            font-size: 0.85rem !important;
            padding: 0.35rem 1rem !important;
            transition: background 0.15s, border-color 0.15s;
          }
          .prompt-chip button:hover {
            background: rgba(218,169,74,0.12) !important;
            border-color: rgba(218,169,74,0.65) !important;
            color: #f4c95d !important;
          }
          /* Welcome screen */
          .welcome-hero {
            text-align: center;
            padding: 2.5rem 1rem 1.5rem;
          }
          .welcome-hero .title {
            font-size: 1.5rem;
            font-weight: 700;
            color: #f8f9fc !important;
          }
          .welcome-hero .subtitle {
            font-size: 0.95rem;
            color: #9aafd4 !important;
            margin-top: 0.4rem;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )


def get_api_key() -> str:
    try:
        return st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    except Exception:
        return os.getenv("GEMINI_API_KEY", "")


def ensure_database(csv_path: str, db_path: str) -> None:
    if not Path(db_path).exists():
        with st.spinner("Initializing SQLite database from CSV..."):
            init_db(csv_path=csv_path, db_path=db_path)


def get_runtime_paths() -> tuple[str, str]:
    csv_path = os.getenv("CSV_PATH", DEFAULT_CSV_PATH)
    db_path = os.getenv("DB_PATH", DEFAULT_DB_PATH)
    return csv_path, db_path


@st.cache_resource(show_spinner=False)
def prepare_database(csv_path: str, db_path: str, csv_mtime: float) -> bool:
    # csv_mtime is included in cache key to refresh DB when CSV changes.
    _ = csv_mtime
    ensure_database(csv_path=csv_path, db_path=db_path)
    refresh_player_aliases(db_path=db_path)
    return True


def _normalize_free_text(text: str) -> str:
    text = re.sub(r"[^a-z0-9 ]+", " ", text.lower())
    text = re.sub(r"\s+", " ", text).strip()
    return text


def resolve_player_aliases(question: str, db_path: str) -> tuple[str, list[str]]:
    alias_map = get_player_alias_map(db_path=db_path)
    if not alias_map:
        try:
            refresh_player_aliases(db_path=db_path)
            alias_map = get_player_alias_map(db_path=db_path)
        except Exception:
            return question, []
    if not alias_map:
        return question, []

    rewritten_question = question
    normalized_question = _normalize_free_text(rewritten_question)
    replacement_notes: list[str] = []
    alias_candidates = sorted(alias_map.keys(), key=len, reverse=True)
    for alias in alias_candidates:
        canonical_name = alias_map[alias]
        if not canonical_name:
            continue
        normalized_pattern = r"\b" + re.escape(alias) + r"\b"
        if not re.search(normalized_pattern, normalized_question):
            continue

        tokens = [t for t in alias.split(" ") if t]
        original_pattern = r"\b" + r"\s+".join(re.escape(t) for t in tokens) + r"\b"
        updated_question = re.sub(
            original_pattern,
            canonical_name,
            rewritten_question,
            flags=re.IGNORECASE,
        )
        if updated_question != rewritten_question:
            rewritten_question = updated_question
            normalized_question = _normalize_free_text(rewritten_question)
            replacement_notes.append(f"{alias} -> {canonical_name}")

    return rewritten_question, replacement_notes


def get_dataset_stats(db_path: str) -> dict[str, str]:
    stats = {"deliveries": "-", "matches": "-", "seasons": "-"}
    try:
        deliveries = execute_query("SELECT COUNT(*) AS c FROM deliveries", db_path=db_path)
        matches = execute_query("SELECT COUNT(DISTINCT match_id) AS c FROM deliveries", db_path=db_path)
        seasons = execute_query("SELECT COUNT(DISTINCT season) AS c FROM deliveries", db_path=db_path)
        stats["deliveries"] = f"{int(deliveries.iloc[0]['c']):,}"
        stats["matches"] = f"{int(matches.iloc[0]['c']):,}"
        stats["seasons"] = f"{int(seasons.iloc[0]['c']):,}"
    except Exception:
        pass
    return stats


def render_kpis(stats: dict[str, str]) -> None:
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Total Deliveries</div><div class='kpi-value'>{stats['deliveries']}</div></div>",
            unsafe_allow_html=True,
        )
    with c2:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Unique Matches</div><div class='kpi-value'>{stats['matches']}</div></div>",
            unsafe_allow_html=True,
        )
    with c3:
        st.markdown(
            f"<div class='kpi-card'><div class='kpi-title'>Seasons Covered</div><div class='kpi-value'>{stats['seasons']}</div></div>",
            unsafe_allow_html=True,
        )


def _safe_col_name(name: str) -> str:
    """Strip characters that Altair misreads as aggregation shorthand."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", name).strip("_") or "col"


def render_chart(df: pd.DataFrame, chart_key: str) -> None:
    if df.empty:
        st.info("No rows returned, so no chart is shown.")
        return

    numeric_cols = list(df.select_dtypes(include="number").columns)
    if not numeric_cols:
        st.info("No numeric columns available for charting.")
        return

    st.markdown("**Interactive Chart Builder**")
    all_cols = list(df.columns)
    x_default = next((col for col in all_cols if col not in numeric_cols), all_cols[0])
    y_default = numeric_cols[0]

    control_col_1, control_col_2, control_col_3 = st.columns(3)
    x_col = control_col_1.selectbox(
        "X-axis",
        options=all_cols,
        index=all_cols.index(x_default),
        key=f"{chart_key}_x_col",
    )
    y_col = control_col_2.selectbox(
        "Y-axis",
        options=numeric_cols,
        index=numeric_cols.index(y_default),
        key=f"{chart_key}_y_col",
    )
    chart_type = control_col_3.selectbox(
        "Chart Type",
        options=["Bar", "Line", "Scatter"],
        index=0,
        key=f"{chart_key}_chart_type",
    )

    chart_df = df[[x_col, y_col]].dropna().head(200).copy()
    if chart_df.empty:
        st.info("No chartable rows after filtering null values.")
        return

    # Flatten x-axis to scalar strings so set_index never receives multi-dimensional data
    # (can happen with YoY / grouped queries where SQLite returns object-typed columns).
    chart_df[x_col] = chart_df[x_col].astype(str)

    # Altair interprets parens/slashes in column names as aggregation expressions and
    # raises ValueError. Rename both columns to safe identifiers for the chart only.
    safe_x = _safe_col_name(x_col)
    safe_y = _safe_col_name(y_col)
    if safe_x == safe_y:
        safe_y = safe_y + "_value"
    chart_df = chart_df.rename(columns={x_col: safe_x, y_col: safe_y})

    if chart_type == "Bar":
        st.bar_chart(chart_df.set_index(safe_x), width="stretch")
    elif chart_type == "Line":
        st.line_chart(chart_df.set_index(safe_x), width="stretch")
    else:
        st.scatter_chart(chart_df, x=safe_x, y=safe_y, width="stretch")


def render_response(payload: dict, response_key: str) -> None:
    if payload.get("text"):
        st.markdown(payload["text"])
    if payload.get("error"):
        st.error(payload["error"])
    if payload.get("sql"):
        with st.expander("SQL", expanded=False):
            st.code(payload["sql"], language="sql")
    if payload.get("data") is not None:
        df = payload["data"]
        st.dataframe(df, width="stretch", height=420)
        c1, c2, c3 = st.columns(3)
        c1.metric("Rows", f"{len(df):,}")
        c2.metric("Columns", f"{len(df.columns):,}")
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        c3.download_button(
            "Download CSV",
            data=csv_bytes,
            file_name=f"{response_key}.csv",
            mime="text/csv",
            width="stretch",
            key=f"{response_key}_download",
        )
        render_chart(df, chart_key=response_key)


_EXAMPLE_PROMPTS: list[tuple[str, str]] = [
    ("🏆", "Top 10 run scorers of all time"),
    ("🎯", "Best death-over bowlers since 2018"),
    ("📈", "Virat Kohli's year-on-year run tally"),
    ("🏟️", "Powerplay economy rate by venue"),
    ("💥", "Most sixes in a single season"),
    ("⚔️", "Head-to-head: CSK vs MI matches"),
]


def render_welcome_prompts() -> None:
    st.markdown(
        """
        <div class="welcome-hero">
          <div style="font-size:2.8rem; line-height:1;">🏏</div>
          <div class="title" style="margin-top:0.6rem;">IPL AI Analyst</div>
          <div class="subtitle">Ask any cricket analytics question in plain English</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("")
    cols = st.columns(2)
    for i, (icon, text) in enumerate(_EXAMPLE_PROMPTS):
        col = cols[i % 2]
        with col:
            st.markdown('<div class="prompt-chip">', unsafe_allow_html=True)
            if st.button(f"{icon}  {text}", width="stretch", key=f"_eg_{i}"):
                st.session_state["_prefill"] = text
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("")


def initialize_state() -> None:
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("message_counter", 0)
    st.session_state.setdefault("direct_sql", "SELECT * FROM deliveries LIMIT 50")


apply_theme()
initialize_state()
api_key = get_api_key()
csv_path, db_path = get_runtime_paths()

st.title("IPL Analytics")
st.caption("Production-ready dashboard for NL-to-SQL and direct SQL analytics (2008-2025).")

with st.sidebar:
    st.header("How To Use")
    st.markdown(
        """
1. Ask a question in **AI Analyst** to get SQL-powered answers.
2. Use **SQL Studio** to run your own SQL (no Gemini calls).
3. Use chart controls to choose X-axis, Y-axis, and chart type.
4. Download any result as CSV from the result card.
        """
    )
    st.divider()
    if st.button("🗑️  Clear chat history", width="stretch"):
        st.session_state.messages = []
        st.session_state.message_counter = 0
        st.rerun()
    st.divider()
    st.caption("Data: IPL ball-by-ball (2008-2025).")
    st.caption("For AI mode, `GEMINI_API_KEY` is configured by the app owner.")

try:
    if csv_path.startswith(("http://", "https://")):
        csv_mtime = 0.0
    else:
        csv_file = Path(csv_path)
        if not csv_file.exists():
            raise FileNotFoundError(f"Dataset not found at `{csv_path}`.")
        csv_mtime = csv_file.stat().st_mtime
    prepare_database(csv_path=csv_path, db_path=db_path, csv_mtime=csv_mtime)
except Exception as exc:
    st.error(f"Database not ready: {exc}")

render_kpis(get_dataset_stats(db_path=db_path))
tab_ai, tab_sql = st.tabs(["AI Analyst", "SQL Studio"])

with tab_ai:
    if not api_key:
        st.warning("Gemini API key missing. Configure it to use AI Analyst.")

    # Render full chat history from session state
    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"]):
            msg_key = msg.get("id", f"history_{idx}")
            render_response(msg, response_key=msg_key)

    # Show welcome prompts only when there are no messages yet
    if not st.session_state.messages:
        render_welcome_prompts()

    # Pick up a question from either the chat input or an example prompt button
    question = st.chat_input("Ask anything about IPL…")
    if not question:
        question = st.session_state.pop("_prefill", None)

    if question:
        message_counter = st.session_state.message_counter
        user_id = f"user_{message_counter}"
        assistant_id = f"assistant_{message_counter}"

        user_payload = {"id": user_id, "role": "user", "text": question}
        st.session_state.messages.append(user_payload)

        # Show the user bubble immediately (no rerun needed)
        with st.chat_message("user"):
            st.markdown(question)

        assistant_payload: dict = {"id": assistant_id, "role": "assistant"}
        with st.chat_message("assistant"):
            try:
                if not api_key:
                    raise ValueError("Gemini API key missing. Configure secrets and retry.")

                columns = get_table_columns(db_path=db_path)
                if not columns:
                    raise ValueError("No table schema found. Initialize the database first.")

                rewritten_question, alias_notes = resolve_player_aliases(question, db_path=db_path)

                with st.status("Thinking…", expanded=False) as status:
                    st.write("Generating SQL query…")
                    sql = generate_sql(user_question=rewritten_question, columns=columns, api_key=api_key)
                    st.write("Running query against database…")
                    result_df = execute_query(sql, db_path=db_path)
                    status.update(label="Done", state="complete", expanded=False)

                row_count = len(result_df)
                summary = f"Here {'is' if row_count == 1 else 'are'} the results — **{row_count:,}** {'row' if row_count == 1 else 'rows'} returned."
                if alias_notes:
                    summary += f"\n\n*Name{'s' if len(alias_notes) > 1 else ''} normalized: {', '.join(alias_notes[:5])}*"

                assistant_payload["text"] = summary
                assistant_payload["sql"] = sql
                assistant_payload["data"] = result_df

            except Exception as exc:
                assistant_payload["text"] = "I couldn't complete that request."
                assistant_payload["error"] = str(exc)

            render_response(assistant_payload, response_key=assistant_id)

        st.session_state.messages.append(assistant_payload)
        st.session_state.message_counter = message_counter + 1

with tab_sql:
    st.markdown("### SQL Studio")
    st.caption("Run your own read-only SQL directly. This mode does not call Gemini.")
    with st.expander("Dataset & Column Overview", expanded=False):
        st.markdown("**Dataset:** `deliveries`")
        try:
            studio_columns = get_table_columns(db_path=db_path)
            if studio_columns:
                st.caption(f"{len(studio_columns)} columns available")
                st.code(", ".join(studio_columns))
            else:
                st.info("No columns found. Database may still be initializing.")
        except Exception as exc:
            st.info(f"Could not load schema yet: {exc}")

    direct_sql = st.text_area("SQL Query", value=st.session_state.direct_sql, height=220)
    st.session_state.direct_sql = direct_sql
    run_col, sample_col = st.columns([1, 1])
    run_clicked = run_col.button("Run SQL", type="primary", width="stretch")
    sample_col.code("SELECT batter, SUM(runs_batter) AS runs FROM deliveries GROUP BY batter ORDER BY runs DESC LIMIT 20")
    if run_clicked:
        try:
            with st.spinner("Executing SQL..."):
                result_df = execute_query(direct_sql, db_path=db_path)
            st.session_state.direct_sql_result = {
                "id": "direct_sql_result",
                "role": "assistant",
                "text": f"SQL executed successfully. Returned **{len(result_df):,}** rows.",
                "sql": direct_sql,
                "data": result_df,
            }
        except Exception as exc:
            st.session_state.direct_sql_result = {
                "id": "direct_sql_result",
                "role": "assistant",
                "text": "I could not execute that SQL.",
                "sql": direct_sql,
                "error": str(exc),
            }
    if st.session_state.get("direct_sql_result"):
        render_response(st.session_state.direct_sql_result, response_key="direct_sql_result")

