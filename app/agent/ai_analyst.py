# file: app/agent/ai_analyst.py

"""
AI-Powered SQL Analyst.
Supports both local Ollama and cloud Groq inference automatically.
"""

import re
from typing import Dict, Any, Optional, List, Generator
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
    """
    AI SQL Analyst supporting dual LLM providers:
    - Groq Cloud API (if GROQ_API_KEY is provided)
    - Ollama Local (default fallback)
    """

    def __init__(self, model_name=None, base_url=None):
        self.schema_text = get_schema_for_prompt()

        # Check if Groq API key is present in configuration
        if settings.groq_api_key and settings.groq_api_key.strip():
            from langchain_groq import ChatGroq
            # Groq's active high-performance free model
            groq_model = "llama-3.3-70b-versatile"
            self.llm = ChatGroq(
                model_name=groq_model,
                groq_api_key=settings.groq_api_key.strip(),
                temperature=0.0,
            )
            print("AIAnalyst initialized with Groq Cloud Provider.")
        else:
            from langchain_ollama import ChatOllama
            self.model = model_name or settings.llm_model
            self.base_url = base_url or settings.ollama_base_url
            self.llm = ChatOllama(
                model=self.model,
                base_url=self.base_url,
                temperature=0.0,
            )
            print("AIAnalyst initialized with local Ollama Provider.")

    def _call_llm(self, prompt: str) -> str:
        response = self.llm.invoke([HumanMessage(content=prompt)])
        content = response.content
        return content if isinstance(content, str) else str(content)

    def generate_sql(self, question: str) -> str:
        prompt = SQL_GENERATION_PROMPT.format(
            schema=self.schema_text, question=question
        )
        return clean_sql_output(self._call_llm(prompt))

    def retry_sql(self, question: str, failed_sql: str, error_message: str) -> str:
        prompt = SQL_RETRY_PROMPT.format(
            schema=self.schema_text,
            question=question,
            failed_sql=failed_sql,
            error_message=error_message,
        )
        return clean_sql_output(self._call_llm(prompt))

    def summarize_results(self, question: str, sql: str, result_data: Any) -> str:
        if not result_data:
            return "No matching data was found in the database for your query."
        prompt = RESULT_SUMMARIZATION_PROMPT.format(
            question=question, sql=sql, result_data=str(result_data)
        )
        return self._call_llm(prompt).strip()

    @staticmethod
    def _step(name: str, status: str, detail: str = "") -> dict:
        return {"type": "step", "step": name, "status": status, "detail": detail}

    @staticmethod
    def _result(data: dict) -> dict:
        return {"type": "result", "data": data}

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

    def analyze_stream(self, question: str) -> Generator[dict, None, None]:
        steps: List[Dict[str, str]] = []

        def record(name, status, detail=""):
            s = {"step": name, "status": status, "detail": detail}
            steps.append(s)
            return s

        if not question or not question.strip():
            record("Understanding the question", "error", "Empty")
            yield self._step("Understanding the question", "error", "Empty question")
            yield self._result(self._error_dict(
                question, get_user_message(ErrorCategory.USER_INPUT),
                "Empty question.", steps=steps
            ))
            return

        question = question.strip()
        record("Understanding the question", "success", f"'{question[:60]}'")
        yield self._step(
            "Understanding the question", "success",
            f"Received: '{question[:60]}'"
        )

        record("Inspecting the database schema", "success", "4 tables found")
        yield self._step(
            "Inspecting the database schema", "success",
            "Found tables: customers, products, orders, order_items"
        )

        yield self._step("Generating SQL query", "running", "Asking LLM...")
        try:
            current_sql = self.generate_sql(question)
            record("Generating SQL query", "success", current_sql[:100])
            yield self._step("Generating SQL query", "success", current_sql[:100])
        except Exception as e:
            record("Generating SQL query", "error", str(e)[:100])
            yield self._step("Generating SQL query", "error", str(e)[:100])
            yield self._result(self._error_dict(
                question, get_user_message(ErrorCategory.LLM_FAILURE),
                str(e), steps=steps
            ))
            return

        if not current_sql:
            record("Generating SQL query", "error", "Empty output")
            yield self._step("Generating SQL query", "error", "LLM returned empty output")
            yield self._result(self._error_dict(
                question, "The AI could not generate a query.",
                "Empty SQL.", steps=steps
            ))
            return

        last_error = None

        for attempt in range(1, MAX_RETRIES + 2):
            is_valid, val_err = validate_sql_query(current_sql)

            if not is_valid:
                record("Validating SQL for safety", "error", val_err[:80])
                yield self._step("Validating SQL for safety", "error", val_err[:80])

                cat = categorize_error(val_err)
                if is_retryable(cat) and attempt <= MAX_RETRIES + 1:
                    yield self._step("Retrying — fixing SQL", "running", f"Attempt {attempt + 1}...")
                    try:
                        current_sql = self.retry_sql(question, current_sql, val_err)
                        record("Retrying — fixing SQL", "success", current_sql[:100])
                        yield self._step("Retrying — fixing SQL", "success", current_sql[:100])
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
                    record("Validating SQL for safety", "success", "Read-only and safe")
                    yield self._step("Validating SQL for safety", "success", "Query is read-only and safe")

            yield self._step("Executing query against database", "running", "Running SELECT query...")
            exec_res = execute_readonly_query(current_sql)

            if exec_res["success"]:
                record(
                    "Executing query against database", "success",
                    f"Returned {exec_res['row_count']} row(s)"
                )
                yield self._step(
                    "Executing query against database", "success",
                    f"Returned {exec_res['row_count']} row(s)"
                )

                yield self._step("Summarizing results", "running", "Generating plain-English answer...")
                try:
                    summary = self.summarize_results(question, current_sql, exec_res["rows"])
                    record("Summarizing results", "success", "Answer generated")
                    yield self._step("Summarizing results", "success", "Answer generated")
                except Exception:
                    summary = f"Query returned {exec_res['row_count']} row(s)."
                    record("Summarizing results", "warning", "Summarization failed")
                    yield self._step("Summarizing results", "warning", "Showing raw data")

                warnings = []
                if exec_res.get("truncated"):
                    warnings.append(f"Results limited to {settings.max_query_rows} rows.")
                if exec_res["row_count"] == 0:
                    warnings.append("No results found.")
                if attempt > 1:
                    warnings.append(f"AI corrected query after {attempt - 1} retry.")

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
                record("Executing query against database", "error", exec_res["error"][:100])
                yield self._step("Executing query against database", "error", exec_res["error"][:100])
                last_error = exec_res["error"]
                cat = categorize_error(exec_res["error"])

                if is_retryable(cat) and attempt <= MAX_RETRIES + 1:
                    yield self._step(
                        "Retrying — fixing SQL", "running",
                        f"Attempt {attempt + 1}: {exec_res['error'][:60]}"
                    )
                    try:
                        current_sql = self.retry_sql(question, current_sql, exec_res["error"])
                        record("Retrying — fixing SQL", "success", current_sql[:100])
                        yield self._step("Retrying — fixing SQL", "success", current_sql[:100])
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

        yield self._result(self._error_dict(
            question,
            f"Failed after {len(steps)} steps. Try rephrasing.",
            last_error or "All retries failed.",
            sql=current_sql, steps=steps
        ))

    def analyze(self, question: str) -> Dict[str, Any]:
        final_result = None
        for event in self.analyze_stream(question):
            if event["type"] == "result":
                final_result = event["data"]
        return final_result or self._error_dict(
            question, "Analysis failed.", "No result produced."
        )