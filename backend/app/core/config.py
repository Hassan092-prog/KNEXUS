from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_ENV_FILE = REPOSITORY_ROOT / ".env"
DEFAULT_STORAGE_ROOT = (REPOSITORY_ROOT / ".knexus-private-storage").resolve()


APPROVED_GOOGLE_EMBEDDING_MODELS: tuple[str, ...] = (
    "gemini-embedding-001",
    "models/gemini-embedding-001",
    "text-embedding-004",
    "models/text-embedding-004",
)

def canonicalize_embedding_model_name(name: str | None) -> str:
    """Return the canonical unprefixed embedding model name.

    Strips redundant 'models/' prefix so both 'models/gemini-embedding-001'
    and 'gemini-embedding-001' map to the same persisted and queried identifier.
    Model names without 'models/' (such as MiniLM) are returned unchanged.
    """
    trimmed = (name or "").strip()
    if trimmed.startswith("models/"):
        return trimmed[len("models/"):]
    return trimmed



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

    # Generation provider configuration.
    # GENERATION_PROVIDER takes precedence over legacy OLLAMA_PROVIDER when set.
    GENERATION_PROVIDER: str | None = None
    GENERATION_MODEL: str | None = None
    GENERATION_API_KEY: SecretStr | None = None
    GENERATION_BASE_URL: str | None = None
    GENERATION_TIMEOUT: float = Field(default=30.0, gt=0)
    GENERATION_MAX_TOKENS: int = Field(default=1024, gt=0)
    GENERATION_TEMPERATURE: float = Field(default=0.0, ge=0.0)
    # Fail-closed prompt character boundary (~4,000-5,300 tokens); not a guaranteed token count.
    GENERATION_MAX_PROMPT_CHARS: int = Field(default=16000, gt=0)
    GENERATION_SEED: int | None = None

    # Deprecated: Local Ollama provider is refused in Phase 1 (hosted providers only).
    # Preserved for backward compatibility in environment definitions; refused at query execution.
    OLLAMA_PROVIDER: str | None = None
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"
    OLLAMA_MODEL: str = "llama3.2:3b"
    OLLAMA_TIMEOUT: float = Field(default=30.0, gt=0)
    OLLAMA_NUM_CTX: int = Field(default=8192, gt=0)
    OLLAMA_NUM_PREDICT: int = Field(default=512, gt=0)

    # Durable Quota & Metering Configuration
    QUOTA_ENABLED: bool = True
    QUOTA_CAMPAIGN_ID: str = Field(default="")
    QUOTA_CAMPAIGN_MAX_ATTEMPTS: int = Field(default=500, gt=0)
    QUOTA_MAX_REQUESTS_PER_MINUTE: int = Field(default=30, gt=0)
    QUOTA_MAX_REQUESTS_PER_DAY: int = Field(default=1000, gt=0)
    QUOTA_MAX_TOTAL_ATTEMPTS: int | None = Field(default=None, ge=0)

    @field_validator("QUOTA_MAX_TOTAL_ATTEMPTS", mode="before")
    @classmethod
    def _parse_optional_int(cls, v: Any) -> int | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v
    QUOTA_MIN_REQUEST_INTERVAL_SECONDS: float = Field(default=2.0, ge=0.0)
    QUOTA_IN_FLIGHT_TIMEOUT_SECONDS: float = Field(default=60.0, gt=0)
    QUOTA_LOCK_TIMEOUT_SECONDS: float = Field(default=10.0, gt=0)
    QUOTA_STATE_PATH: Path = Field(default_factory=lambda: (DEFAULT_STORAGE_ROOT / "quota_state.json").resolve())

    # Embedding and ingestion configuration
    # Supported providers: 'local' (sentence-transformers), 'google', 'fake'
    EMBEDDING_PROVIDER: str = "local"
    EMBEDDING_MODEL_NAME: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_MODEL_REVISION: str = "main"
    EMBEDDING_DIMENSIONS: int = Field(default=384, gt=0)
    EMBEDDING_API_KEY: SecretStr | None = None
    EMBEDDING_BASE_URL: str | None = None
    EMBEDDING_TIMEOUT: float = Field(default=20.0, gt=0)
    EMBEDDING_TASK_TYPE: str = "RETRIEVAL_DOCUMENT"
    EMBEDDING_COUNTING_OVERHEAD_TOKENS: int = Field(default=8, ge=0)
    EMBEDDING_MAX_INPUT_TOKENS: int = Field(default=2048, gt=0)
    EMBEDDING_MAX_VALIDATION_CALLS_PER_DOC: int = Field(default=50, gt=0)
    EMBEDDING_VALIDATION_DEADLINE_SECONDS: float = Field(default=30.0, gt=0)

    @field_validator("GENERATION_PROVIDER", mode="before")
    @classmethod
    def _validate_generation_provider(cls, v: Any) -> str | None:
        if v is None:
            return None
        val = str(v).strip().lower()
        if val == "ollama":
            raise ValueError(
                "Local Ollama provider is deprecated and refused. KNEXUS Phase 1 uses hosted providers only."
            )
        return val

    @field_validator("QUOTA_STATE_PATH", mode="after")
    @classmethod
    def _validate_quota_state_path(cls, v: Path) -> Path:
        if not v.is_absolute():
            raise ValueError(
                f"QUOTA_STATE_PATH must be an absolute path (got {v!r}); "
                "relative paths are refused to prevent split ledgers across worker working directories."
            )
        return v.resolve()

    @field_validator(
        "EMBEDDING_TIMEOUT",
        "EMBEDDING_VALIDATION_DEADLINE_SECONDS",
        "GENERATION_TIMEOUT",
        mode="before",
    )
    @classmethod
    def _validate_finite_positive_float(cls, v: Any) -> float:
        import math
        if isinstance(v, bool) or not isinstance(v, (int, float, str)):
            raise ValueError("Must be a finite positive number")
        try:
            val = float(v)
        except (ValueError, TypeError):
            raise ValueError("Must be a finite positive number")
        if not math.isfinite(val) or val <= 0:
            raise ValueError("Must be a finite positive number")
        return val

    @model_validator(mode="after")
    def _validate_quota_in_flight_timeout(self) -> "Settings":
        max_deadline = max(
            float(self.GENERATION_TIMEOUT),
            float(self.EMBEDDING_TIMEOUT),
            float(self.EMBEDDING_VALIDATION_DEADLINE_SECONDS),
        )
        # Margin justification: 5.0s safety margin accommodates socket teardown, async cancellation,
        # disk flush, and cross-process file-lock acquisition so an active request is never
        # prematurely expired and duplicated while legitimately in flight.
        safety_margin = 5.0
        min_required = max_deadline + safety_margin
        if float(self.QUOTA_IN_FLIGHT_TIMEOUT_SECONDS) <= min_required:
            raise ValueError(
                f"QUOTA_IN_FLIGHT_TIMEOUT_SECONDS ({self.QUOTA_IN_FLIGHT_TIMEOUT_SECONDS}s) must be "
                f"strictly greater than longest provider deadline ({max_deadline}s) + safety margin ({safety_margin}s) = {min_required}s "
                f"to prevent concurrent dispatches while an active request is legitimately in flight."
            )
        return self

    @model_validator(mode="after")
    def _validate_embedding_provider_and_model(self) -> "Settings":
        provider = (self.EMBEDDING_PROVIDER or "").strip().lower()
        if provider == "google":
            raw_model = (self.EMBEDDING_MODEL_NAME or "").strip()
            if raw_model not in APPROVED_GOOGLE_EMBEDDING_MODELS:
                raise ValueError(
                    f"When EMBEDDING_PROVIDER is 'google', EMBEDDING_MODEL_NAME must be explicitly configured "
                    f"to an approved Google embedding model ({sorted(APPROVED_GOOGLE_EMBEDDING_MODELS)}), "
                    f"got {self.EMBEDDING_MODEL_NAME!r}."
                )
            self.EMBEDDING_MODEL_NAME = canonicalize_embedding_model_name(raw_model)
        return self

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
