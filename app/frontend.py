# file: app/frontend.py

"""
Streamlit frontend with real-time streaming progress.

Run:  streamlit run app/frontend.py
Requires: FastAPI on port 8000, Ollama running
"""

import streamlit as st
import httpx
import json

API_URL = "http://localhost:8000"
STREAM_ENDPOINT = f"{API_URL}/analyze/stream"
REQUEST_TIMEOUT = 180.0

st.set_page_config(page_title="SQL Analyst Agent", page_icon="📊", layout="wide")

if "history" not in st.session_state:
    st.session_state.history = []


def stream_analyze(question: str):
    """
    Connects to the SSE streaming endpoint and yields parsed events
    one at a time as they arrive from the server.
    """
    try:
        with httpx.stream(
            "POST",
            STREAM_ENDPOINT,
            json={"question": question},
            timeout=REQUEST_TIMEOUT,
        ) as response:
            if response.status_code != 200:
                yield {
                    "type": "result",
                    "data": {
                        "question": question,
                        "answer": f"Server error (HTTP {response.status_code})",
                        "error": response.read().decode(),
                        "sql": None, "columns": [], "rows": [],
                        "row_count": 0, "truncated": False,
                        "warnings": [], "steps": [],
                    },
                }
                return

            # Read the SSE stream line by line
            buffer = ""
            for chunk in response.iter_text():
                buffer += chunk
                # SSE events are separated by double newlines
                while "\n\n" in buffer:
                    event_text, buffer = buffer.split("\n\n", 1)
                    for line in event_text.strip().split("\n"):
                        if line.startswith("data: "):
                            try:
                                yield json.loads(line[6:])
                            except json.JSONDecodeError:
                                pass

    except httpx.ConnectError:
        yield {
            "type": "result",
            "data": {
                "question": question,
                "answer": "Cannot connect to the backend.",
                "error": "Start the server: python -m uvicorn app.main:app --reload",
                "sql": None, "columns": [], "rows": [],
                "row_count": 0, "truncated": False,
                "warnings": [], "steps": [],
            },
        }
    except httpx.ReadTimeout:
        yield {
            "type": "result",
            "data": {
                "question": question,
                "answer": "The analysis timed out.",
                "error": f"Exceeded {REQUEST_TIMEOUT}s timeout.",
                "sql": None, "columns": [], "rows": [],
                "row_count": 0, "truncated": False,
                "warnings": [], "steps": [],
            },
        }
    except Exception as e:
        yield {
            "type": "result",
            "data": {
                "question": question,
                "answer": "Unexpected error.",
                "error": str(e),
                "sql": None, "columns": [], "rows": [],
                "row_count": 0, "truncated": False,
                "warnings": [], "steps": [],
            },
        }


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
    st.caption("Ollama + FastAPI + SQLite")


# ── Main ──────────────────────────────────────────────────────────

st.title("📊 SQL Analyst Agent")
st.markdown(
    "Ask questions about your sales database in plain English. "
    "Watch the AI work step by step in real time."
)
st.divider()

question = st.text_input(
    "💬 Ask a question:",
    placeholder="e.g., Which product sold the most units?",
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
        "Or try a sample:",
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

    # The status container stays open while we read the stream.
    # Each event updates it in real time.
    with st.status("⏳ Analyzing your question...", state="running", expanded=True) as status_box:

        for event in stream_analyze(question.strip()):

            if event["type"] == "step":
                status = event.get("status", "running")
                name = event.get("step", "")
                detail = event.get("detail", "")

                if status == "success":
                    icon = "✅"
                elif status == "error":
                    icon = "❌"
                elif status == "warning":
                    icon = "⚠️"
                else:
                    icon = "⏳"

                if detail:
                    st.markdown(f"{icon} **{name}** — _{detail}_")
                else:
                    st.markdown(f"{icon} **{name}**")

            elif event["type"] == "result":
                result_data = event["data"]
                # Update the status box to final state
                if result_data.get("error"):
                    status_box.update(label="❌ Analysis failed", state="error")
                else:
                    status_box.update(label="✅ Analysis complete", state="complete")

    # ── Display final result below the status box ─────────────────

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
        elif not result_data.get("error"):
            st.info("ℹ️ No results found.")

        st.divider()

st.markdown("---")
st.caption(
    "🔒 Read-only SELECT queries only. All SQL validated before execution."
)