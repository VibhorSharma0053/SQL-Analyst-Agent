# file: app/tools/database_tools.py

"""
Read-Only Database Query Execution Tool with logging.
"""

import time
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.database.connection import SessionLocal
from app.tools.sql_validator import validate_sql_query
from app.config import settings
from app.logging_config import get_logger

logger = get_logger(__name__)


def execute_readonly_query(
    query: str,
    max_rows: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Validates and executes a read-only SQL query with full logging.
    """
    limit = max_rows if max_rows is not None else settings.max_query_rows

    # ── Step 1: Validate ──────────────────────────────────────────
    is_valid, validation_error = validate_sql_query(query)
    if not is_valid:
        logger.warning("SQL validation FAILED: %s", validation_error)
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": f"Validation Error: {validation_error}",
        }

    logger.debug("SQL validation passed: %s", query[:120])

    # ── Step 2: Execute ───────────────────────────────────────────
    db = SessionLocal()
    start_time = time.time()

    try:
        statement = text(query)
        result = db.execute(statement)
        columns = list(result.keys())
        fetched = result.mappings().fetchmany(limit + 1)

        truncated = len(fetched) > limit
        rows = [dict(row) for row in fetched[:limit]]
        duration = time.time() - start_time

        logger.info(
            "Query executed: %d rows, %.3fs, truncated=%s",
            len(rows),
            duration,
            truncated,
        )

        return {
            "success": True,
            "columns": columns,
            "rows": rows,
            "row_count": len(rows),
            "truncated": truncated,
            "error": None,
        }

    except SQLAlchemyError as db_err:
        duration = time.time() - start_time
        error_msg = str(db_err.orig) if hasattr(db_err, "orig") else str(db_err)
        logger.error(
            "Database error after %.3fs: %s",
            duration,
            error_msg[:200],
        )
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": f"Database Error: {error_msg}",
        }

    except Exception as general_err:
        duration = time.time() - start_time
        logger.error(
            "Unexpected error after %.3fs: %s",
            duration,
            str(general_err)[:200],
        )
        return {
            "success": False,
            "columns": [],
            "rows": [],
            "row_count": 0,
            "truncated": False,
            "error": f"Execution Error: {str(general_err)}",
        }

    finally:
        db.close()