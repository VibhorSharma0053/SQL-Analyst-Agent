# file: app/config.py

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration."""

    # ── LLM Settings ─────────────────────────────────────────────
    groq_api_key: str = Field(
        default="",
        description="Groq API key for cloud deployment (optional)."
    )

    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Ollama base URL for local development."
    )

    llm_model: str = Field(
        default="llama3.1:8b",
        description="Model name to use."
    )

    # ── Database Settings ─────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./data/analytics.db",
        description="SQLite database connection URL."
    )

    # ── Application Settings ──────────────────────────────────────
    app_env: str = Field(
        default="development",
        description="Application environment: development or production."
    )

    max_query_rows: int = Field(
        default=100,
        description="Maximum rows returned by query tool."
    )

    query_timeout_seconds: int = Field(
        default=30,
        description="Maximum query execution timeout in seconds."
    )

    port: int = Field(
        default=8000,
        description="FastAPI port."
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() == "development"

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"


settings = Settings()