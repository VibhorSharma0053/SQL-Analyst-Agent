# file: app/agent/ai_analyst.py

"""
AI-Powered SQL Analyst with streaming step events.

New: analyze_stream() is a generator that yields step events
in real time as each phase of the pipeline completes.
"""
from app.logging_config import get_logger

logger = get_logger(__name__)
import re
from typing import Dict, Any, Optional, List, Generator
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

from app.config import settings
from app.database.schema_inspector import get_schema_for_prompt
from app.tools.sql_validator import validate_sql_query
from app.tools.database_tools import execute_readonly_query
from app.agent.prompts import (
    SQL_GENERATION_PROMPT,
    RESULT_SUMMARIZATION_PROMPT,
    SQL_RETRY_PROMPT,
)
from app.agent.error_handler import (
    categorize_error,
    get_user_message,
    is_retryable,
    ErrorCategory,
)

MAX_RETRIES = 2


def clean_sql_output(raw_output: str) -> str:
    cleaned = raw_output.strip()
    code_block_match = re.search(
        r"```(?:sql)?\s*([\s\S]*?)\s*```", cleaned, re.IGNORECASE
    )
    if code_block_match:
        cleaned = code_block_match.group(1).strip()
    if cleaned.startswith("`") and cleaned.endswith("`"):
        cleaned = cleaned.strip("`").strip()
    sql_start_match = re.search(r"\b(SELECT|WITH)\b", cleaned, re.IGNORECASE)
    if sql_start_match:
        cleaned = cleaned[sql_start_match.start():].strip()
    if cleaned.endswith(";"):
        cleaned = cleaned[:-1].strip()
    return cleaned


class AIAnalyst:

    def __init__(self, model_name=None, base_url=None):
        self.model = model_name or settings.llm_model
        self.base_url = base_url or settings.ollama_base_url
        self.llm = ChatOllama(
            model=self.model,
            base_url=self.base_url,
            temperature=0.0,
        )
        self.schema_text = get_schema_for_prompt()

    def _call_llm(self, prompt: str) -> str:
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        return content if isinstance(content, str) else str(content)

    def generate_sql(self, question: str) -> str:
        prompt = SQL_GENERATION_PROMPT.format(
            schema=self.schema_text, question=question
        )
        return clean_sql_output(self._call_llm(prompt))

    def retry_sql(self, question, failed_sql, error_message) -> str:
        prompt = SQL_RETRY_PROMPT.format(
            schema=self.schema_text,
            question=question,
            failed_sql=failed_sql,
            error_message=error_message,
        )
        return clean_sql_output(self._call_llm(prompt))

    def summarize_results(self, question, sql, result_data) -> str:
        if not result_data:
            return "No matching data was found in the database for your query."
        prompt = RESULT_SUMMARIZATION_PROMPT.format(
            question=question, sql=sql, result_data=str(result_data)
        )
        return self._call_llm(prompt).strip()

    # ── Helper to build a step event ──────────────────────────────
    @staticmethod
    def _step(name: str, status: str, detail: str = "") -> dict:
        return {"type": "step", "step": name, "status": status, "detail": detail}

    # ── Helper to build a final result event ──────────────────────
    @staticmethod
    def _result(data: dict) -> dict:
        return {"type": "result", "data": data}

    # ── Helper to build an error response dict ────────────────────
    def _error_dict(self, question, answer, error, sql=None, steps=None):
        return {
            "question": question,
            "answer": answer,
            "sql": sql,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "warnings": [],
            "error": error,
            "steps": steps or [],
        }

    # ══════════════════════════════════════════════════════════════
    #  STREAMING GENERATOR — yields events in real time
    # ══════════════════════════════════════════════════════════════

    def analyze_stream(self, question: str) -> Generator[dict, None, None]:
        """
        Generator that yields step events as each pipeline phase completes.

        Event types:
          {"type": "step",   "step": "...", "status": "success|error|running", "detail": "..."}
          {"type": "result", "data": {full response dict}}
        """
        steps: List[Dict[str, str]] = []

        def record(name, status, detail=""):
            s = {"step": name, "status": status, "detail": detail}
            steps.append(s)
            return s

        # ── 0. Validate input ─────────────────────────────────────
        if not question or not question.strip():
            logger.warning("Empty question received")
            record("Understanding the question", "error", "Question is empty")
            yield self._step("Understanding the question", "error", "Empty question")
            yield self._result(self._error_dict(
                question, get_user_message(ErrorCategory.USER_INPUT),
                "Empty question.", steps=steps
            ))
            return

        question = question.strip()
        logger.info("New analysis request: '%s'", question[:80])
        record("Understanding the question", "success", f"'{question[:60]}'")
        yield self._step(
            "Understanding the question", "success",
            f"Received: '{question[:60]}'"
        )

        # ── 1. Inspect schema ─────────────────────────────────────
        record("Inspecting the database schema", "success", "4 tables found")
        yield self._step(
            "Inspecting the database schema", "success",
            "Found tables: customers, products, orders, order_items"
        )

        # ── 2. Generate SQL ───────────────────────────────────────
        logger.info("Generating SQL for: '%s'", question[:60])
        yield self._step(
            "Generating SQL query", "running",
            "Asking the AI model..."
        )
        try:
            current_sql = self.generate_sql(question)
            logger.info("SQL generated: %s", current_sql[:120])
            record("Generating SQL query", "success", current_sql[:100])
            yield self._step(
                "Generating SQL query", "success",
                current_sql[:100]
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", str(e)[:200])
            record("Generating SQL query", "error", str(e)[:100])
            yield self._step("Generating SQL query", "error", str(e)[:100])
            yield self._result(self._error_dict(
                question, get_user_message(ErrorCategory.LLM_FAILURE),
                str(e), steps=steps
            ))
            return

        if not current_sql:
            logger.warning("LLM returned empty SQL")
            record("Generating SQL query", "error", "Empty output")
            yield self._step("Generating SQL query", "error", "LLM returned empty output")
            yield self._result(self._error_dict(
                question, "The AI could not generate a query.",
                "Empty SQL.", steps=steps
            ))
            return
        


        
        # ── 3–6. Validate → Execute → Retry loop ──────────────────
        last_error = None

        for attempt in range(1, MAX_RETRIES + 2):

            # ── Validate ──────────────────────────────────────────
            is_valid, val_err = validate_sql_query(current_sql)

            if not is_valid:
                logger.warning("SQL validation failed: %s", val_err[:100])
                record("Validating SQL for safety", "error", val_err[:80])
                yield self._step("Validating SQL for safety", "error", val_err[:80])

                cat = categorize_error(val_err)
                if is_retryable(cat) and attempt <= MAX_RETRIES + 1:
                    logger.info("Retrying SQL (attempt %d)", attempt + 1)
                    yield self._step(
                        "Retrying — fixing SQL", "running",
                        f"Attempt {attempt + 1}..."
                    )
                    try:
                        current_sql = self.retry_sql(question, current_sql, val_err)
                        record("Retrying — fixing SQL", "success", current_sql[:100])
                        yield self._step(
                            "Retrying — fixing SQL", "success",
                            current_sql[:100]
                        )
                        continue
                    except Exception:
                        record("Retrying — fixing SQL", "error", "Retry failed")
                        yield self._step("Retrying — fixing SQL", "error", "Retry failed")
                        break
                else:
                    yield self._result(self._error_dict(
                        question, get_user_message(cat),
                        val_err, sql=current_sql, steps=steps
                    ))
                    return
            else:
                if attempt == 1:
                    logger.debug("SQL validation passed")
                    record("Validating SQL for safety", "success", "Read-only and safe")
                    yield self._step(
                        "Validating SQL for safety", "success",
                        "Query is read-only and safe"
                    )


            
            # ── Execute ───────────────────────────────────────────
            logger.info("Executing SQL (attempt %d): %s", attempt, current_sql[:100])
            yield self._step(
                "Executing query against database", "running",
                "Running SELECT query..."
            )
            exec_res = execute_readonly_query(current_sql)

            if exec_res["success"]:
                logger.info(
                    "Query returned %d rows (attempt %d)",
                    exec_res["row_count"], attempt
                )
                record(
                    "Executing query against database", "success",
                    f"Returned {exec_res['row_count']} row(s)"
                )
                yield self._step(
                    "Executing query against database", "success",
                    f"Returned {exec_res['row_count']} row(s)"
                )
                logger.info(
                                "Query returned %d rows (attempt %d)",
                                exec_res["row_count"],
                                attempt,
                            )
                # ── Summarize ─────────────────────────────────────
                yield self._step(
                    "Summarizing results", "running",
                    "Generating plain-English answer..."
                )
                logger.info("Summarizing results with LLM")
                try:
                    summary = self.summarize_results(
                        question, current_sql, exec_res["rows"]
                    )
                    record("Summarizing results", "success", "Answer generated")
                    yield self._step("Summarizing results", "success", "Answer generated")
                except Exception:
                    summary = f"Query returned {exec_res['row_count']} row(s)."
                    logger.warning("Summarization failed, using fallback")
                    record("Summarizing results", "warning", "Summarization failed")
                    yield self._step(
                        "Summarizing results", "warning",
                        "Showing raw data"
                    )

                warnings = []
                if exec_res.get("truncated"):
                    warnings.append(f"Results limited to {settings.max_query_rows} rows.")
                if exec_res["row_count"] == 0:
                    warnings.append("No results found. Filters may be too specific.")
                if attempt > 1:
                    warnings.append(f"AI corrected query after {attempt - 1} retry.")

                logger.info("Analysis complete for: '%s'", question[:60])
                yield self._result({
                    "question": question,
                    "answer": summary,
                    "sql": current_sql,
                    "columns": exec_res["columns"],
                    "rows": exec_res["rows"],
                    "row_count": exec_res["row_count"],
                    "truncated": exec_res["truncated"],
                    "warnings": warnings,
                    "error": None,
                    "steps": steps,
                })
                return
            else:
                logger.error(
                    "Query failed (attempt %d): %s",
                    attempt, exec_res["error"][:100]
                )
                record(
                    "Executing query against database", "error",
                    exec_res["error"][:100]
                )
                yield self._step(
                    "Executing query against database", "error",
                    exec_res["error"][:100]
                )
                last_error = exec_res["error"]
                cat = categorize_error(exec_res["error"])
                logger.warning( 
                                    "Retry %d/%d — error: %s",
                                    attempt + 1,
                                    MAX_RETRIES + 2,
                                    exec_res["error"][:100],
                                )
                if is_retryable(cat) and attempt <= MAX_RETRIES + 1:
                    logger.warning(
                        "Retrying (attempt %d/%d): %s",
                        attempt + 1, MAX_RETRIES + 2,
                        exec_res["error"][:60]
                    )
                    yield self._step(
                        "Retrying — fixing SQL", "running",
                        f"Attempt {attempt + 1}: {exec_res['error'][:60]}"
                    )
                    try:
                        current_sql = self.retry_sql(
                            question, current_sql, exec_res["error"]
                        )
                        record("Retrying — fixing SQL", "success", current_sql[:100])
                        yield self._step(
                            "Retrying — fixing SQL", "success",
                            current_sql[:100]
                        )
                        continue
                    except Exception:
                        record("Retrying — fixing SQL", "error", "Retry failed")
                        yield self._step("Retrying — fixing SQL", "error", "Retry failed")
                        break
                else:
                    yield self._result(self._error_dict(
                        question, get_user_message(cat),
                        exec_res["error"], sql=current_sql, steps=steps
                    ))
                    return
            
                
        logger.error("Analysis failed after %d steps", len(steps))
        # All retries exhausted
        yield self._result(self._error_dict(
            question,
            f"Failed after {len(steps)} steps. Try rephrasing.",
            last_error or "All retries failed.",
            sql=current_sql, steps=steps
        ))

    # ══════════════════════════════════════════════════════════════
    #  NON-STREAMING WRAPPER — collects all events into one dict
    # ══════════════════════════════════════════════════════════════

    def analyze(self, question: str) -> Dict[str, Any]:
        """
        Non-streaming wrapper. Runs the full pipeline and returns
        the final result dict. Used by the /analyze endpoint.
        """
        final_result = None
        for event in self.analyze_stream(question):
            if event["type"] == "result":
                final_result = event["data"]
        return final_result or self._error_dict(
            question, "Analysis failed.", "No result produced."
        )