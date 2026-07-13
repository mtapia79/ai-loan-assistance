"""
AI Loan Assistance – Application Configuration

Uses pydantic-settings for type-safe, environment-driven configuration.
All secrets are sourced from environment variables or an .env file.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, computed_field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralised, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────
    app_env: Literal["development", "staging", "production"] = "development"
    app_name: str = "AI Loan Assistant"
    app_version: str = "0.1.0"
    log_level: str = "INFO"

    # ── OpenAI ─────────────────────────────────────────────────────
    openai_api_key: str = Field(default="sk-placeholder", alias="OPENAI_API_KEY")
    openai_model: str = "gpt-4o"
    openai_embedding_model: str = "text-embedding-3-small"

    # ── PostgreSQL ─────────────────────────────────────────────────
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "loan_assistance"
    postgres_user: str = "loan_user"
    postgres_password: str = "changeme"

    # ── pgvector ───────────────────────────────────────────────────
    vector_dimension: int = 1536

    # ── Redis Cache ────────────────────────────────────────────────
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str = ""

    # ── JWT ────────────────────────────────────────────────────────
    jwt_secret_key: str = "dev-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # ── OpenTelemetry ──────────────────────────────────────────────
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"
    otel_service_name: str = "ai-loan-assistance"
    otel_enabled: bool = False

    # ── MCP ────────────────────────────────────────────────────────
    mcp_server_url: str = "http://localhost:8001"

    # ── AWS ────────────────────────────────────────────────────────
    aws_region: str = "us-east-1"
    aws_s3_bucket: str = "loan-documents-bucket"

    # ── Computed ───────────────────────────────────────────────────
    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def database_url_sync(self) -> str:
        """Sync URL used by Alembic migrations."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def redis_url(self) -> str:
        """Redis connection URL."""
        if self.redis_password:
            return (
                f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/"
                f"{self.redis_db}"
            )
        return f"redis://{self.redis_host}:{self.redis_port}/{self.redis_db}"

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        if self.app_env == "production":
            if self.jwt_secret_key == "dev-secret-key-change-in-production":
                raise ValueError("JWT_SECRET_KEY must be set in production")
            if self.openai_api_key == "sk-placeholder":
                raise ValueError("OPENAI_API_KEY must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance (singleton)."""
    return Settings()
