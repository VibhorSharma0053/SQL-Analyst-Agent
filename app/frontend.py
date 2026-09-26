# file: app/frontend.py

"""
Streamlit frontend for SQL Analyst Agent.
Supports both remote FastAPI connection and direct Cloud execution.
"""

import os
import sys
from pathlib import Path

# ── Fix Python Path for Streamlit Cloud Deployment ─────────────────
# Adds the root project folder to sys.path so 'import app...' works cleanly
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import streamlit as st
import httpx
import json

# Sync Streamlit Cloud Secrets to os.environ for Groq API Key
try:
    if "GROQ_API_KEY" in st.secrets:
        os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]
except Exception:
    pass

from app.agent.ai_analyst import AIAnalyst

API_URL = os.getenv("API_URL", "http://localhost:8000")
STREAM_ENDPOINT = f"{API_URL}/analyze/stream"
REQUEST_TIMEOUT = 120.0

st.set_page_config(page_title="SQL Analyst Agent", page_icon="📊", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []

@st.cache_resource
def get_direct_analyst():
    """Instantiates a cached AIAnalyst for in-process cloud execution."""
    return AIAnalyst()


def stream_analyze(question: str):
    """
    Attempts to stream via external FastAPI backend.
    If backend is unreachable (e.g. standalone Streamlit Cloud deployment),
    falls back seamlessly to running the in-process AIAnalyst!
    """
    try:
        with httpx.stream(
            "POST",
            STREAM_ENDPOINT,
            json={"question": question},
            timeout=3.0,  # Fast timeout check for local API
        ) as response:
            if response.status_code == 200:
                buffer = ""
                for chunk in response.iter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        event_text, buffer = buffer.split("\n\n", 1)
                        for line in event_text.strip().split("\n"):
                            if line.startswith("data: "):
                                try:
                                    yield json.loads(line[6:])
                                except json.JSONDecodeError:
                                    pass
                return
    except Exception:
        # FastAPI backend not reachable; fallback to direct in-process execution
        pass

    # Direct In-Process Stream Execution (for Streamlit Community Cloud)
    analyst = get_direct_analyst()
    for event in analyst.analyze_stream(question):
        yield event


# ── Sidebar ───────────────────────────────────────────────────────

with st.sidebar:
    st.header("📜 Query History")
    if st.session_state.history:
        if st.button("🗑️ Clear History"):
            st.session_state.history = []
            st.rerun()
        st.divider()
        for entry in reversed(st.session_state.history):
            icon = "✅" if entry["success"] else "❌"
            with st.expander(f"{icon} {entry['question'][:50]}..."):
                st.write(f"**Q:** {entry['question']}")
                st.write(f"**A:** {entry['answer'][:200]}")
                if entry.get("sql"):
                    st.code(entry["sql"], language="sql")
    else:
        st.info("No queries yet.")
    st.divider()
    st.caption("SQL Analyst Agent v0.1.0")
    st.caption("Powered by LangChain & Streamlit Cloud")


# ── Main ──────────────────────────────────────────────────────────

st.title("📊 SQL Analyst Agent")
st.markdown(
    "Ask questions about your sales database in plain English. "
    "Watch the AI agent inspect the schema, validate SQL safety, and answer in real time."
)
st.divider()

question = st.text_input(
    "💬 Ask a question:",
    placeholder="e.g., Which product category generated the highest sales revenue?",
    key="question_input",
)

col1, col2 = st.columns([1, 3])
with col1:
    analyze_button = st.button(
        "🔍 Analyze", type="primary",
        use_container_width=True,
        disabled=not question.strip(),
    )
with col2:
    sample = st.selectbox(
        "Or try a sample question:",
        [
            "",
            "How many customers do we have?",
            "What is the total revenue?",
            "Which product category generated the highest sales revenue?",
            "Who are the top 5 customers by spending?",
            "How many orders are currently pending?",
            "What is the average order value?",
            "Which city has the most customers?",
            "Show revenue by month",
        ],
        key="sample_select",
    )
if sample:
    question = sample


# ── Process with live streaming ───────────────────────────────────

if analyze_button and question.strip():
    result_data = None

    with st.status("⏳ Analyzing your question...", state="running", expanded=True) as status_box:
        for event in stream_analyze(question.strip()):
            if event["type"] == "step":
                status = event.get("status", "running")
                name = event.get("step", "")
                detail = event.get("detail", "")

                icon = "✅" if status == "success" else "❌" if status == "error" else "⚠️" if status == "warning" else "⏳"
                if detail:
                    st.markdown(f"{icon} **{name}** — _{detail}_")
                else:
                    st.markdown(f"{icon} **{name}**")

            elif event["type"] == "result":
                result_data = event["data"]
                if result_data.get("error"):
                    status_box.update(label="❌ Analysis failed", state="error")
                else:
                    status_box.update(label="✅ Analysis complete", state="complete")

    if result_data:
        st.session_state.history.append({
            "question": question.strip(),
            "answer": result_data.get("answer", ""),
            "sql": result_data.get("sql"),
            "success": result_data.get("error") is None,
        })

        if result_data.get("error"):
            st.error(f"⚠️ {result_data['error']}")

        st.subheader("💡 Answer")
        st.markdown(result_data.get("answer", "No answer."))

        for w in result_data.get("warnings", []):
            st.warning(f"⚠️ {w}")

        sql = result_data.get("sql")
        if sql:
            st.subheader("🔧 Generated SQL")
            st.code(sql, language="sql")

        rows = result_data.get("rows", [])
        if rows:
            st.subheader(f"📋 Results ({result_data.get('row_count', 0)} rows)")
            if result_data.get("truncated"):
                st.info("ℹ️ Results limited by row cap.")
            st.dataframe(rows, use_container_width=True, hide_index=True)
        elif not result.get("error"):
            st.info("ℹ️ No results found.")

        st.divider()

st.markdown("---")
st.caption(
    "🔒 Read-only SELECT queries only. All SQL validated before execution."
)