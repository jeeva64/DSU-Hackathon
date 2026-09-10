from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    # ---- Database ----
    DATABASE_URL: str = "postgresql://postgres:password@localhost:5432/nelsync_ai"

    # ---- Application ----
    APP_ENV: str = "development"
    APP_NAME: str = "NelSync AI"
    APP_VERSION: str = "0.1.0"
    LOG_LEVEL: str = "INFO"

    # ---- CORS ----
    CORS_ORIGINS: str = "http://localhost:8501,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # ---- LLM (Optional) ----
    LLM_API_KEY: str | None = None
    LLM_PROVIDER: str | None = None

    @property
    def llm_enabled(self) -> bool:
        return bool(self.LLM_API_KEY)

    # ---- ML ----
    ML_ARTIFACTS_DIR: str = "backend/app/ml/artifacts"
    ML_VALIDATION_DAYS: int = 14

    # ---- Server ----
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


settings = Settings()
