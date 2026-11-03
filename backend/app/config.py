"""Runtime configuration. Every value can be overridden with an ORKESTR_* environment variable."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ORKESTR_", env_file=".env", extra="ignore")

    env: str = "development"
    database_url: str = "postgresql+psycopg://orkestr:orkestr@localhost:5432/orkestr"
    redis_url: str | None = None

    # Auth
    jwt_secret: str = "dev-only-change-me-please-32-bytes-min"
    jwt_ttl_minutes: int = 12 * 60
    # Shared secret n8n uses when calling the API (sent as X-Orkestr-Service-Token)
    service_token: str = "dev-service-token"
    # HMAC secret used to sign webhooks exchanged with n8n (both directions)
    webhook_secret: str = "dev-webhook-secret"
    webhook_max_skew_seconds: int = 300

    # n8n
    n8n_base_url: str = "http://localhost:5678"
    n8n_api_key: str | None = None
    n8n_workflows_dir: Path = REPO_ROOT / "n8n" / "workflows"
    # When false, the API records workflow intent but does not call n8n (unit tests).
    n8n_enabled: bool = True

    # LLM providers. Provider "fixture" is deterministic and clearly labelled as such.
    llm_provider: str = "fixture"  # fixture | anthropic | openai
    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-sonnet-4-5"
    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"
    embedding_provider: str = "hashing"  # hashing | openai
    embedding_dim: int = 384

    # Storage
    storage_dir: Path = REPO_ROOT / "var" / "storage"
    max_upload_mb: int = 25

    # Live integrations (credentials are referenced, never stored in the DB)
    slack_webhook_url: str | None = None
    jira_base_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_project_key: str | None = None
    hubspot_token: str | None = None

    # Platform behaviour
    rate_limit_per_minute: int = 240
    retention_days: int = 365
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    otel_enabled: bool = False
    otel_endpoint: str | None = None
    seed_demo_data: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
