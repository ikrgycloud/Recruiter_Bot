from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Recruiter Automation Platform"
    environment: str = "development"
    database_url: str = "postgresql+asyncpg://recruiter:recruiter@localhost:5433/recruiter"
    jwt_secret: str = "change-this-in-production"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    allowed_cors_origins: list[str] = ["http://localhost:5173"]
    company_email_blocklist: list[str] = [
        "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "live.com", "icloud.com", "aol.com"
    ]
    admin_email: str = "vinnuikrgy@gmail.com"
    admin_password: str = "12345678"
    admin_name: str = "System Administrator"
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "http://localhost:8000/api/integrations/google/callback"
    google_frontend_url: str = "http://localhost:5173"
    google_sync_interval_seconds: int = 60
    automation_auto_reschedule: bool = False
    token_encryption_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
