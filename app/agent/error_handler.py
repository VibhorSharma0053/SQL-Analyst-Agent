# file: app/agent/error_handler.py

"""
Error categorization and user-friendly message generation.

This module classifies every error that can occur in the SQL analyst
pipeline and converts technical error messages into clear, helpful
messages for the end user.

Why not just show the raw error?
  Raw: "sqlite3.OperationalError: no such column: custmer_name"
  User-friendly: "The query referenced a column that doesn't exist.
                  The AI will try to correct this automatically."

We never expose:
  - Stack traces
  - File paths
  - Internal function names
  - Database credentials
  - Model configuration details
"""

from enum import Enum
from typing import Tuple


class ErrorCategory(Enum):
    """
    Every error falls into exactly one category.
    This determines how we respond to the user.
    """
    USER_INPUT = "user_input"           # The user's question is the problem
    SQL_SYNTAX = "sql_syntax"           # The generated SQL is malformed
    SQL_SAFETY = "sql_safety"           # The generated SQL was blocked
    UNKNOWN_TABLE = "unknown_table"     # SQL references a non-existent table
    UNKNOWN_COLUMN = "unknown_column"   # SQL references a non-existent column
    EMPTY_RESULT = "empty_result"       # Query ran but returned no data
    LLM_FAILURE = "llm_failure"         # The LLM could not generate a response
    LLM_TIMEOUT = "llm_timeout"         # The LLM took too long
    DATABASE_CONNECTION = "db_connection"  # Cannot reach the database
    DATABASE_EXECUTION = "db_execution"    # Database rejected the query
    UNKNOWN = "unknown"                 # Catch-all for unexpected errors


def categorize_error(error_message: str) -> ErrorCategory:
    """
    Analyzes an error message string and returns the most likely category.

    This uses simple keyword matching. It is not perfect, but it covers
    the most common SQLite error patterns.

    Args:
        error_message: The raw error string from the database or LLM.

    Returns:
        The most likely ErrorCategory.
    """
    if not error_message:
        return ErrorCategory.UNKNOWN

    error_lower = error_message.lower()

    # ── User Input Errors ──────────────────────────────────────────
    if "empty question" in error_lower:
        return ErrorCategory.USER_INPUT
    if "invalid input" in error_lower:
        return ErrorCategory.USER_INPUT

    # ── SQL Safety Errors ──────────────────────────────────────────
    if "forbidden keyword" in error_lower:
        return ErrorCategory.SQL_SAFETY
    if "dangerous keyword" in error_lower:
        return ErrorCategory.SQL_SAFETY
    if "multiple sql statements" in error_lower:
        return ErrorCategory.SQL_SAFETY
    if "read-only" in error_lower:
        return ErrorCategory.SQL_SAFETY

    # ── Unknown Table ──────────────────────────────────────────────
    if "no such table" in error_lower:
        return ErrorCategory.UNKNOWN_TABLE

    # ── Unknown Column ─────────────────────────────────────────────
    if "no such column" in error_lower:
        return ErrorCategory.UNKNOWN_COLUMN

    # ── SQL Syntax Errors ──────────────────────────────────────────
    if "syntax error" in error_lower:
        return ErrorCategory.SQL_SYNTAX
    if "near \"" in error_lower:
        return ErrorCategory.SQL_SYNTAX
    if "incomplete input" in error_lower:
        return ErrorCategory.SQL_SYNTAX

    # ── LLM Failures ──────────────────────────────────────────────
    if "connect" in error_lower and "refused" in error_lower:
        return ErrorCategory.LLM_FAILURE
    if "timeout" in error_lower:
        return ErrorCategory.LLM_TIMEOUT
    if "ollama" in error_lower:
        return ErrorCategory.LLM_FAILURE

    # ── Database Connection ────────────────────────────────────────
    if "unable to open database" in error_lower:
        return ErrorCategory.DATABASE_CONNECTION
    if "database is locked" in error_lower:
        return ErrorCategory.DATABASE_CONNECTION

    # ── Default ────────────────────────────────────────────────────
    return ErrorCategory.DATABASE_EXECUTION


def get_user_message(category: ErrorCategory, raw_error: str = "") -> str:
    """
    Converts an error category into a clear, user-friendly message.

    The message explains what went wrong in plain English without
    exposing technical details.

    Args:
        category: The error category.
        raw_error: The original error (used for context but not shown).

    Returns:
        A user-friendly error string.
    """
    messages = {
        ErrorCategory.USER_INPUT: (
            "I could not understand your question. "
            "Please try rephrasing it. For example: "
            "'How many customers do we have?' or 'What is the total revenue?'"
        ),

        ErrorCategory.SQL_SYNTAX: (
            "The AI generated a query with a syntax error. "
            "It will attempt to correct this automatically. "
            "If the problem persists, try rephrasing your question."
        ),

        ErrorCategory.SQL_SAFETY: (
            "The generated query was blocked by our safety system "
            "because it contained a restricted operation. "
            "Only read-only queries are allowed. "
            "Please rephrase your question."
        ),

        ErrorCategory.UNKNOWN_TABLE: (
            "The AI referenced a table that does not exist in the database. "
            "It will attempt to correct this automatically."
        ),

        ErrorCategory.UNKNOWN_COLUMN: (
            "The AI referenced a column that does not exist in the database. "
            "It will attempt to correct this automatically."
        ),

        ErrorCategory.EMPTY_RESULT: (
            "Your query was executed successfully, but no matching data "
            "was found. This could mean the filters are too specific "
            "or the data does not contain what you are looking for."
        ),

        ErrorCategory.LLM_FAILURE: (
            "The AI model is currently unavailable. "
            "Please make sure Ollama is running and try again. "
            "You can start it with: ollama serve"
        ),

        ErrorCategory.LLM_TIMEOUT: (
            "The AI model took too long to respond. "
            "This can happen with complex questions on slower hardware. "
            "Please try a simpler question or try again later."
        ),

        ErrorCategory.DATABASE_CONNECTION: (
            "The database is currently unavailable. "
            "Please check that the database file exists and try again."
        ),

        ErrorCategory.DATABASE_EXECUTION: (
            "An error occurred while running the query. "
            "The AI will attempt to correct this automatically."
        ),

        ErrorCategory.UNKNOWN: (
            "An unexpected error occurred. "
            "Please try again or rephrase your question."
        ),
    }

    return messages.get(category, messages[ErrorCategory.UNKNOWN])


def is_retryable(category: ErrorCategory) -> bool:
    """
    Determines whether the agent should retry after this type of error.

    Retryable errors are ones where the LLM might fix the problem
    if given the error message as feedback.

    Non-retryable errors are ones where retrying would waste time
    because the problem is not the LLM's fault.
    """
    retryable = {
        ErrorCategory.SQL_SYNTAX,
        ErrorCategory.UNKNOWN_TABLE,
        ErrorCategory.UNKNOWN_COLUMN,
        ErrorCategory.DATABASE_EXECUTION,
    }
    return category in retryable