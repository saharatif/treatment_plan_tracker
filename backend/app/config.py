"""Application configuration loaded from environment variables / .env.

A single `Settings` instance (`settings`) is created at import time and
shared across the app. Every field maps to an env var via `validation_alias`,
with sensible local-dev defaults so the app can boot without a .env file.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(
        "postgresql+asyncpg://orbs:orbs@localhost/orbs",
        validation_alias="DATABASE_URL",
    )
    kms_key: str = Field("", validation_alias="KMS_KEY")
    mistral_api_key: str = Field("", validation_alias="MISTRAL_API_KEY")
    openai_api_key: str = Field("", validation_alias="OPENAI_API_KEY")
    smtp_host: str = Field("", validation_alias="SMTP_HOST")
    smtp_port: int = Field(587, validation_alias="SMTP_PORT")
    smtp_user: str = Field("", validation_alias="SMTP_USER")
    smtp_password: str = Field("", validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(True, validation_alias="SMTP_USE_TLS")
    supabase_url: str = Field("", validation_alias="SUPABASE_URL")
    supabase_anon_key: str = Field("", validation_alias="SUPABASE_ANON_KEY")
    supabase_jwt_secret: str = Field("", validation_alias="SUPABASE_JWT_SECRET")
    supabase_service_role_key: str = Field("", validation_alias="SUPABASE_SERVICE_ROLE_KEY")
    ai_ocr_provider: str = Field("mistral", validation_alias="AI_OCR_PROVIDER")
    ai_parser_provider: str = Field("openai", validation_alias="AI_PARSER_PROVIDER")
    ollama_base_url: str = Field("http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    billing_email: str = Field("", validation_alias="BILLING_EMAIL")
    billing_portal_base_url: str = Field(
        "http://localhost:3001",
        validation_alias="BILLING_PORTAL_BASE_URL",
    )
    # Daily checkpoint job (see app/scheduler.py) - off by default so tests/dev don't
    # trigger background alerts/report generation.
    enable_checkpoint_scheduler: bool = Field(False, validation_alias="ENABLE_CHECKPOINT_SCHEDULER")
    checkpoint_cron_hour: int = Field(8, validation_alias="CHECKPOINT_CRON_HOUR")
    checkpoint_grace_any_orb: bool = Field(True, validation_alias="CHECKPOINT_GRACE_ANY_ORB")
    report_output_dir: str = Field("reports", validation_alias="REPORT_OUTPUT_DIR")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3001"])

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


# Module-level singleton - import `settings` rather than instantiating Settings() again.
settings = Settings()
