from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = "development"
    app_name: str = "WhatsApp Clinic Suite"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://winzapp:winzapp@localhost:55432/winzapp"
    test_database_url: str = "postgresql+asyncpg://winzapp:winzapp@localhost:55432/winzapp"
    redis_url: str = "redis://localhost:6379/0"

    wa_app_secret: str = ""
    wa_verify_token: str = ""
    wa_access_token: str = ""

    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"
    groq_api_key: str = Field(default="", repr=False)
    llm_timeout_seconds: int = 10

    supabase_url: str = ""
    supabase_service_key: str = Field(default="", repr=False)
    supabase_storage_bucket: str = "reports"

    jwt_secret: str = Field(default="change-me-in-local-dev", repr=False)
    jwt_access_token_minutes: int = 30


@lru_cache
def get_settings() -> Settings:
    return Settings()
