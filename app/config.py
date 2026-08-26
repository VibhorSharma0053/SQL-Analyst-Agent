# file: app/config.py

"""
Application configuration — fully free version using Ollama.

All LLM inference runs locally through Ollama.
No API keys required. No cost per query.
"""

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """
    All application settings loaded from environment variables.
    """

    # ── Ollama / LLM Settings ─────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description=(
            "URL where Ollama is running on your computer. "
            "Default is always localhost:11434 after installing Ollama."
        )
    )

    llm_model: str = Field(
        default="llama3.1:8b",
        description=(
            "Which Ollama model to use. "
            "llama3.1:8b is recommended. "
            "Use llama3.2:3b if your computer has less than 8GB RAM."
        )
    )

    # ── Database Settings ─────────────────────────────────────────
    database_url: str = Field(
        default="sqlite:///./data/analytics.db",
        description="SQLite database file path."
    )

    # ── Application Settings ──────────────────────────────────────
    app_env: str = Field(
        default="development",
        description="Environment: development or production."
    )

    max_query_rows: int = Field(
        default=100,
        description="Maximum rows the query tool can return."
    )

    query_timeout_seconds: int = Field(
        default=30,
        description="Maximum seconds a query can run."
    )

    port: int = Field(
        default=8000,
        description="Port FastAPI listens on."
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