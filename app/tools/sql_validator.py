# file: app/tools/sql_validator.py

"""
SQL Query Validator.

This module provides deterministic validation of SQL queries generated
by the LLM agent or provided by users.

Every query must pass all checks before being sent to the database.
"""

import re
from typing import Tuple, Optional

# List of keywords that modify data, alter schemas, or execute administrative commands.
# Any occurrence of these keywords as standalone words will cause the query to be rejected.
FORBIDDEN_KEYWORDS = [
    # Data Modification
    "DELETE",
    "INSERT",
    "UPDATE",
    "REPLACE",
    "MERGE",
    "UPSERT",
    # Schema Modification
    "DROP",
    "ALTER",
    "TRUNCATE",
    "CREATE",
    "RENAME",
    # Administrative & SQLite Specific
    "ATTACH",
    "DETACH",
    "PRAGMA",
    "VACUUM",
    "REINDEX",
    # Permissions & Execution
    "GRANT",
    "REVOKE",
    "EXEC",
    "EXECUTE",
]

# Compile regular expressions with word boundaries (\b) for each forbidden keyword.
# \b ensures that "DROP" is matched, but "BACKDROP" or "DROPSHIP" is not.
FORBIDDEN_PATTERNS = [
    re.compile(rf"\b{keyword}\b", re.IGNORECASE)
    for keyword in FORBIDDEN_KEYWORDS
]


def validate_sql_query(query: str) -> Tuple[bool, Optional[str]]:
    """
    Validates a SQL query string to ensure it is strictly read-only and safe.

    Args:
        query: The raw SQL string to validate.

    Returns:
        A tuple of (is_valid, error_message).
        If valid: (True, None)
        If invalid: (False, "Explanation of why the query was rejected")
    """
    # ── Check 1: Empty or whitespace-only query ──────────────────
    if not query or not query.strip():
        return False, "Query cannot be empty."

    cleaned_query = query.strip()

    # ── Check 2: Remove a single optional trailing semicolon ──────
    # A single semicolon at the very end of a query is standard SQL syntax.
    # We strip it so the multi-statement check below won't flag it.
    if cleaned_query.endswith(";"):
        cleaned_query = cleaned_query[:-1].strip()

    # ── Check 3: Reject multiple statements (semicolon check) ─────
    # If a semicolon still exists inside the query, it is an attempt
    # to execute multiple stacked SQL statements.
    if ";" in cleaned_query:
        return (
            False,
            "Multiple SQL statements are strictly forbidden. Remove internal semicolons.",
        )

    # ── Check 4: Must start with SELECT or WITH ───────────────────
    # Read-only queries must start with SELECT, or WITH (Common Table Expressions).
    # We remove leading comments or whitespace to inspect the first command word.
    # Strip single-line SQL comments starting with --
    query_without_comments = re.sub(r"--.*$", "", cleaned_query, flags=re.MULTILINE).strip()

    first_word_match = re.match(r"^([a-zA-Z]+)", query_without_comments)
    if not first_word_match:
        return False, "Unable to identify SQL statement command."

    first_word = first_word_match.group(1).upper()
    if first_word not in ("SELECT", "WITH"):
        return (
            False,
            f"Only read-only queries are permitted. Query must start with SELECT or WITH, not '{first_word}'.",
        )

    # ── Check 5: Scan for forbidden keywords ──────────────────────
    for pattern, keyword in zip(FORBIDDEN_PATTERNS, FORBIDDEN_KEYWORDS):
        if pattern.search(cleaned_query):
            return (
                False,
                f"Query contains forbidden keyword '{keyword}'. Write and administrative operations are blocked.",
            )

    # All checks passed
    return True, None