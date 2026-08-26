# file: app/api/routes.py

"""
API route definitions.

Public endpoints:
  GET  /health    — liveness check
  GET  /schema    — database schema (for debugging / transparency)
  GET  /customers — sample read endpoint
  GET  /products  — sample read endpoint
  POST /analyze   — AI SQL analyst
"""
import json
from fastapi.responses import StreamingResponse
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from app.config import settings
from app.database.connection import get_db
from app.database.models import Customer, Product
from app.database.schema_inspector import get_schema_for_prompt, get_full_schema
from app.agent.ai_analyst import AIAnalyst
from app.schemas.api_models import AnalyzeRequest, AnalyzeResponse, HealthResponse


router = APIRouter()

# One shared analyst instance. Created lazily on first /analyze call.
_analyst: AIAnalyst | None = None


def get_analyst() -> AIAnalyst:
    """
    Returns a process-wide AIAnalyst.

    Creating it once avoids re-reading the schema and
    re-creating the Ollama client on every request.
    """
    global _analyst
    if _analyst is None:
        _analyst = AIAnalyst()
    return _analyst


def _build_warnings(result: dict) -> list[str]:
    """Collect user-safe warnings from an analyst result."""
    warnings: list[str] = []

    if result.get("truncated"):
        warnings.append(
            f"Results were limited to {settings.max_query_rows} rows."
        )

    if result.get("sql") and result.get("error") is None:
        sql_upper = result["sql"].upper()
        if "WHERE" in sql_upper and result.get("row_count") == 1:
            # Soft hint only — do not claim the filter is wrong
            first_row = result.get("rows") or []
            if first_row:
                values = list(first_row[0].values())
                if values and values[0] in (None, 0, 0.0):
                    warnings.append(
                        "The query returned an empty or zero result. "
                        "Check the generated SQL filters (for example status values)."
                    )

    return warnings


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health_check():
    """Verify the API process is running."""
    return HealthResponse(
        status="healthy",
        message="SQL Analyst Agent API is running",
        version="0.1.0",
    )


@router.get("/schema", tags=["metadata"])
def get_database_schema(raw: bool = False):
    """
    Return the database schema.

    raw=false → compact text used in LLM prompts
    raw=true  → structured JSON
    """
    if raw:
        return get_full_schema()
    return {"schema_text": get_schema_for_prompt()}


@router.get("/customers", tags=["database"])
def get_customers(db: Session = Depends(get_db)):
    """Return all customers. Read-only."""
    customers = db.query(Customer).all()
    result = [
        {
            "customer_id": customer.customer_id,
            "name": customer.name,
            "email": customer.email,
            "city": customer.city,
            "signup_date": str(customer.signup_date),
        }
        for customer in customers
    ]
    return {"count": len(result), "customers": result}


@router.get("/products", tags=["database"])
def get_products(db: Session = Depends(get_db)):
    """Return all products. Read-only."""
    products = db.query(Product).all()
    result = [
        {
            "product_id": product.product_id,
            "product_name": product.product_name,
            "category": product.category,
            "price": product.price,
            "stock": product.stock,
        }
        for product in products
    ]
    return {"count": len(result), "products": result}


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    tags=["analyst"],
    summary="Ask a natural-language question about the database",
)
def analyze_question(payload: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run the full AI SQL analyst pipeline.

    1. Generate a read-only SQL query with the local LLM
    2. Validate the query
    3. Execute it
    4. Summarize the result

    This call can take 15–60 seconds with a local CPU model.
    """
    analyst = get_analyst()

    try:
        result = analyst.analyze(payload.question)
    except Exception:
        # Never leak stack traces to the client.
        raise HTTPException(
            status_code=500,
            detail="The analyst failed unexpectedly. Check server logs.",
        )

    warnings = _build_warnings(result)

    return AnalyzeResponse(
        question=result.get("question", payload.question),
        answer=result.get("answer") or "No answer was produced.",
        sql=result.get("sql"),
        columns=result.get("columns") or [],
        rows=result.get("rows") or [],
        row_count=result.get("row_count") or 0,
        truncated=bool(result.get("truncated")),
        warnings=warnings,
        error=result.get("error"),
        steps=result.get("steps") or [],   # ← ADD THIS LINE
    )


@router.get("/query", tags=["database"], include_in_schema=False)
def execute_test_query(sql: str, db: Session = Depends(get_db)):
    """
    Temporary development-only raw SQL endpoint.
    Hidden from Swagger. Prefer POST /analyze.
    """
    sql_upper = sql.strip().upper()

    dangerous_keywords = [
        "DELETE", "DROP", "UPDATE", "INSERT",
        "ALTER", "TRUNCATE", "CREATE", "ATTACH",
        "REPLACE", "GRANT", "REVOKE",
    ]

    for keyword in dangerous_keywords:
        if f" {keyword} " in f" {sql_upper} ":
            raise HTTPException(
                status_code=403,
                detail=f"Query blocked: contains dangerous keyword '{keyword}'.",
            )

    if not (sql_upper.startswith("SELECT") or sql_upper.startswith("WITH")):
        raise HTTPException(
            status_code=403,
            detail="Query blocked: must start with SELECT or WITH.",
        )

    if ";" in sql:
        raise HTTPException(
            status_code=403,
            detail="Query blocked: multiple statements are not allowed.",
        )

    try:
        result = db.execute(text(sql))
        columns = list(result.keys())
        rows = [dict(row) for row in result.mappings()]
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Database error: {str(e)}")

    if len(rows) > settings.max_query_rows:
        rows = rows[: settings.max_query_rows]

    return {"columns": columns, "rows": rows, "row_count": len(rows)}



@router.post(
    "/analyze/stream",
    tags=["analyst"],
    summary="Stream the AI analysis pipeline in real time (SSE)",
)
def analyze_stream(payload: AnalyzeRequest):
    """
    Streams Server-Sent Events as each pipeline step completes.

    Event format:
      data: {"type": "step", "step": "...", "status": "...", "detail": "..."}
      data: {"type": "result", "data": {...full response...}}

    The client reads these events one by one and updates the UI live.
    """
    analyst = get_analyst()

    def event_generator():
        try:
            for event in analyst.analyze_stream(payload.question):
                # SSE format: each message is "data: <json>\n\n"
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as e:
            # If the generator crashes, send an error event
            error_event = {
                "type": "result",
                "data": {
                    "question": payload.question,
                    "answer": "The analyst crashed unexpectedly.",
                    "sql": None,
                    "columns": [],
                    "rows": [],
                    "row_count": 0,
                    "truncated": False,
                    "warnings": [],
                    "error": str(e),
                    "steps": [],
                },
            }
            yield f"data: {json.dumps(error_event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering if used
        },
    )