# File: app/core/config.py
from typing import Optional
from pydantic import PostgresDsn, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic_core import MultiHostUrl


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", case_sensitive=True, extra="ignore"
    )

    PROJECT_NAME: str = "BOT GPT"
    API_V1_STR: str = "/api/v1"

    DEBUG: bool = True
    BACKEND_CORS_ORIGINS: Optional[list[str]] = [
        "http://localhost",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # Database
    DATABASE_URL: str

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """
        Ensures we use the async driver (postgresql+asyncpg)
        even if the .env just says 'postgresql://'
        """
        if self.DATABASE_URL and self.DATABASE_URL.startswith("postgresql://"):
            return self.DATABASE_URL.replace(
                "postgresql://", "postgresql+asyncpg://", 1
            )
        return self.DATABASE_URL

    # JWT Settings (Optional defaults for dev)
    SECRET_KEY: str = "unsafe_secret_key_for_dev"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Google OAuth (Optional)
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None
    GOOGLE_REDIRECT_URI: Optional[str] = None

    # Celery & Redis
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/0"
    REDIS_URL: Optional[str] = None

    # LLM Settings
    LLM_PROVIDER: str = "groq"  # default to groq for speed/free
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None

    # RAG Settings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    VECTOR_DIMENSION: int = 1536

    LOG_LEVEL: str = "INFO"


settings = Settings()
