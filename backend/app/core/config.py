from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ENV_FILE = REPOSITORY_ROOT / ".env"
DEFAULT_STORAGE_ROOT = REPOSITORY_ROOT / ".knexus-private-storage"


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

    # LLM provider configuration. OLLAMA_PROVIDER must be explicit for answers.
    OLLAMA_PROVIDER: str | None = None
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT: float = Field(default=30.0, gt=0)
    OLLAMA_NUM_CTX: int = Field(default=8192, gt=0)
    OLLAMA_NUM_PREDICT: int = Field(default=512, gt=0)
    GENERATION_MAX_PROMPT_CHARS: int = Field(default=12000, gt=0)

    # Embedding and ingestion configuration
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_MODEL_REVISION: str = "main"
    DOCUMENT_STORAGE_ROOT: Path = DEFAULT_STORAGE_ROOT
    MAX_UPLOAD_BYTES: int = Field(default=10 * 1024 * 1024, gt=0, le=10 * 1024 * 1024)
    MAX_PDF_PAGES: int = Field(default=1000, gt=0)
    MAX_EXTRACTED_CHARS: int = Field(default=5_000_000, gt=0)
    CHUNK_TOKEN_LIMIT: int = Field(default=240, gt=33)
    CHUNK_TOKEN_OVERLAP: int = Field(default=32, ge=0, lt=240)
    RETRIEVAL_MIN_SIMILARITY: float = Field(default=0.35, ge=-1, le=1)

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
        env_file=REPOSITORY_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
