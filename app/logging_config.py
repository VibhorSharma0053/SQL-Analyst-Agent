# file: app/logging_config.py

"""
Centralized logging configuration.

This module sets up Python's logging system for the entire application.
Every other module imports the logger from here:

    from app.logging_config import get_logger
    logger = get_logger(__name__)

Why a central config?
  - One place to change the log format for the entire app
  - Consistent timestamps and structure across all modules
  - Easy to switch between console and file output
  - Easy to change log levels without editing every file
"""

import logging
import sys
from app.config import settings


def setup_logging():
    """
    Configures the root logger for the application.

    Call this once at application startup (in main.py).
    After this, all loggers created with get_logger() will
    use this configuration automatically.
    """

    # ── Determine log level based on environment ──────────────────
    #
    # Development: Show everything (DEBUG and above)
    # Production: Show only warnings and errors
    if settings.is_development:
        log_level = logging.DEBUG
    else:
        log_level = logging.WARNING

    # ── Define the log format ─────────────────────────────────────
    #
    # Format breakdown:
    #   %(asctime)s     → timestamp: 2024-11-15 14:32:07
    #   %(levelname)-8s → level, left-aligned, 8 chars wide: INFO
    #   %(name)-25s     → module name: app.agent.ai_analyst
    #   %(message)s     → the actual log message
    #
    # The result looks like:
    #   2024-11-15 14:32:07 | INFO     | app.agent.ai_analyst    | SQL generated in 2.3s

    log_format = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # ── Configure the root logger ─────────────────────────────────
    logging.basicConfig(
        level=log_level,
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Console handler: logs go to the terminal
            logging.StreamHandler(sys.stdout),
        ],
    )

    # ── Silence noisy third-party loggers ─────────────────────────
    #
    # SQLAlchemy and httpx produce a LOT of debug output.
    # We set them to WARNING so they only log real problems.
    # You can change these to DEBUG if you need to troubleshoot
    # database or HTTP issues.

    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    # Get the app logger and log a startup message
    logger = get_logger("app")
    logger.info("Logging system initialized (level=%s)", logging.getLevelName(log_level))


def get_logger(name: str) -> logging.Logger:
    """
    Returns a logger for the given module name.

    Usage in any file:
        from app.logging_config import get_logger
        logger = get_logger(__name__)

    __name__ is a Python built-in that contains the module's full name,
    e.g., "app.agent.ai_analyst" or "app.tools.database_tools".
    This makes it easy to see which module produced each log line.
    """
    return logging.getLogger(name)