# file: app/schemas/api_models.py

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class AnalyzeRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=3,
        max_length=1000,
        description="Natural-language question about the database.",
        examples=["Which product category generated the highest revenue?"],
    )

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 3:
            raise ValueError("Question cannot be empty or only whitespace.")
        return cleaned


class StepInfo(BaseModel):
    """One step in the agent pipeline."""
    step: str = Field(..., description="Human-readable step name")
    status: str = Field(..., description="success, error, warning, or running")
    detail: str = Field(default="", description="Short detail about this step")


class AnalyzeResponse(BaseModel):
    question: str
    answer: str
    sql: Optional[str] = None
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    row_count: int = Field(default=0, ge=0)
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)
    error: Optional[str] = None
    steps: list[StepInfo] = Field(
        default_factory=list,
        description="Pipeline steps the agent went through",
    )


class HealthResponse(BaseModel):
    status: str
    message: str
    version: str