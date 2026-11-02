import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    SUPABASE_DB_URL: str
    GOOGLE_API_KEY: str
    STRATZ_API_KEY: str
    CRON_SECRET: Optional[str] = None
    PORT: int = 8000

    @property
    def sqlalchemy_db_url(self) -> str:
        """Ensure standard postgresql:// URL schema for SQLAlchemy and psycopg2."""
        url = self.SUPABASE_DB_URL
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
