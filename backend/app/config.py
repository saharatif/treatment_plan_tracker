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
    jwt_secret: str = Field("", validation_alias="JWT_SECRET")
    access_token_expire_minutes: int = Field(480, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    demo_clinician_password: str = Field("", validation_alias="DEMO_CLINICIAN_PASSWORD")
    demo_billing_password: str = Field("", validation_alias="DEMO_BILLING_PASSWORD")
    demo_patient_password: str = Field("", validation_alias="DEMO_PATIENT_PASSWORD")
    ai_ocr_provider: str = Field("mistral", validation_alias="AI_OCR_PROVIDER")
    ai_parser_provider: str = Field("openai", validation_alias="AI_PARSER_PROVIDER")
    ollama_base_url: str = Field("http://localhost:11434", validation_alias="OLLAMA_BASE_URL")
    billing_email: str = Field("", validation_alias="BILLING_EMAIL")
    billing_portal_base_url: str = Field(
        "http://localhost:3000",
        validation_alias="BILLING_PORTAL_BASE_URL",
    )
    enable_checkpoint_scheduler: bool = Field(False, validation_alias="ENABLE_CHECKPOINT_SCHEDULER")
    checkpoint_cron_hour: int = Field(8, validation_alias="CHECKPOINT_CRON_HOUR")
    checkpoint_grace_any_orb: bool = Field(True, validation_alias="CHECKPOINT_GRACE_ANY_ORB")
    report_output_dir: str = Field("reports", validation_alias="REPORT_OUTPUT_DIR")
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
