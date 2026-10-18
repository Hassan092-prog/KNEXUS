from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    # App Information
    APP_NAME: str = "KNEXUS API"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # PostgreSQL & pgvector
    POSTGRES_DB: str = "knexus"
    POSTGRES_USER: str = "knexus_admin"
    POSTGRES_PASSWORD: str = "knexus_password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5435
    DATABASE_URL: str = "postgresql+asyncpg://knexus_admin:knexus_password@localhost:5435/knexus"
    DATABASE_SYNC_URL: str = "postgresql://knexus_admin:knexus_password@localhost:5435/knexus"

    # Ollama LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "llama3.2"

    # Embedding Model
    EMBEDDING_MODEL_NAME: str = "all-MiniLM-L6-v2"

    # Security & Auth
    SECRET_KEY: str = "knexus-super-secret-development-key-change-in-production-123456"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120

    # CORS
    BACKEND_CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
    ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
