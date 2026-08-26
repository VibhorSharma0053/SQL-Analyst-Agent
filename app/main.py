# file: app/main.py

"""
FastAPI application entry point with logging middleware.

Run with:
    python -m uvicorn app.main:app --reload
"""

import time
import uuid
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.config import settings
from app.logging_config import setup_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Runs on server startup and shutdown."""
    # Initialize logging first so all subsequent messages are captured
    setup_logging()

    logger.info("=" * 50)
    logger.info("SQL Analyst Agent — Server Starting")
    logger.info("Environment:   %s", settings.app_env)
    logger.info("LLM Model:     %s", settings.llm_model)
    logger.info("Ollama URL:    %s", settings.ollama_base_url)
    logger.info("Database:      %s", settings.database_url)
    logger.info("Max Rows:      %s", settings.max_query_rows)
    logger.info("Query Timeout: %ss", settings.query_timeout_seconds)
    logger.info("=" * 50)
    logger.info("API Docs: http://localhost:%s/docs", settings.port)

    yield

    logger.info("SQL Analyst Agent — Server shutting down.")


app = FastAPI(
    title="SQL Analyst Agent API",
    description="AI-powered SQL analyst with read-only database access.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.is_development else [],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Logging Middleware ────────────────────────────────────────────
#
# This middleware runs for EVERY HTTP request.
# It assigns a unique request ID, measures the response time,
# and logs a summary line.
#
# Why middleware?
#   Without middleware, you would need to add logging code to
#   every single endpoint. Middleware does it automatically
#   for all endpoints, including ones you add in the future.

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Logs every HTTP request with:
    - Unique request ID
    - HTTP method and path
    - Response status code
    - Duration in seconds
    """
    # Generate a unique ID for this request
    request_id = str(uuid.uuid4())[:8]

    # Store the request ID on the request object so endpoints
    # can access it if they want to include it in their logs
    request.state.request_id = request_id

    # Record the start time
    start_time = time.time()

    # Log the incoming request
    logger.info(
        "[%s] → %s %s",
        request_id,
        request.method,
        request.url.path,
    )

    # Process the request (this calls the actual endpoint)
    response = await call_next(request)

    # Calculate duration
    duration = time.time() - start_time

    # Log the response
    logger.info(
        "[%s] ← %s %s → %d (%.2fs)",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration,
    )

    # Add the request ID to the response headers
    # so the frontend can reference it in bug reports
    response.headers["X-Request-ID"] = request_id

    return response


app.include_router(router)