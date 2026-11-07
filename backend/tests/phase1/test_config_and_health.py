"""Tests for settings secret masking, provider rejection, tokenizer fails, and health diagnostics."""
import pytest
from pydantic import SecretStr

from app.api.v1.endpoints.health import health_check
from app.core.config import Settings
from app.services.ingestion.chunking import load_embedding_tokenizer
from app.services.ingestion.embedding import get_default_embedder
from app.services.ingestion.errors import TokenizerUnavailableError


def test_settings_secret_masking():
    s = Settings(
        GENERATION_API_KEY=SecretStr("gsk_secret_12345"),
        EMBEDDING_API_KEY=SecretStr("goog_secret_67890"),
    )
    repr_str = repr(s)
    str_gen = str(s.GENERATION_API_KEY)
    str_emb = str(s.EMBEDDING_API_KEY)

    assert "gsk_secret_12345" not in repr_str
    assert "goog_secret_67890" not in repr_str
    assert str_gen == "**********"
    assert str_emb == "**********"
    assert s.GENERATION_API_KEY.get_secret_value() == "gsk_secret_12345"
    assert s.EMBEDDING_API_KEY.get_secret_value() == "goog_secret_67890"


def test_unknown_embedding_provider_rejected():
    with pytest.raises(ValueError, match="Unsupported embedding provider: 'unknown_provider'"):
        get_default_embedder(provider="unknown_provider")


def test_unsupported_hosted_tokenizer_fails_before_provider_calls():
    # Prove that hosted token counting fails closed without unverified character approximations
    with pytest.raises(TokenizerUnavailableError, match="Token counting for hosted model 'gemini-embedding-001' is not supported"):
        load_embedding_tokenizer("gemini-embedding-001", "001")


@pytest.mark.asyncio
async def test_passive_health_endpoint_no_outbound_calls():
    class MockScalarResult:
        def __init__(self, val):
            self._val = val

        def scalar(self):
            return self._val

    class MockAsyncSession:
        async def execute(self, statement):
            stmt_str = str(statement)
            if "SELECT 1" in stmt_str:
                return MockScalarResult(1)
            if "extname" in stmt_str:
                return MockScalarResult("vector")
            return MockScalarResult(None)

    session = MockAsyncSession()
    health_result = await health_check(db=session)

    assert health_result["status"] == "healthy"
    assert health_result["database"] == "connected"
    assert health_result["pgvector_extension"] == "installed"
    assert "generation" in health_result
    assert "embedding" in health_result


def test_quota_state_path_anchored_absolute_and_refuses_relative():
    """V4: QUOTA_STATE_PATH must be absolute; relative overrides are refused with ValueError."""
    from pydantic import ValidationError
    from pathlib import Path

    # 1. Default is absolute and anchored to repository/storage root
    s = Settings()
    assert s.QUOTA_STATE_PATH.is_absolute()
    assert s.QUOTA_STATE_PATH.name == "quota_state.json"
    assert ".knexus-private-storage" in str(s.QUOTA_STATE_PATH)

    # 2. Absolute override is accepted
    abs_path = Path("/tmp/absolute_quota.json").resolve()
    s2 = Settings(QUOTA_STATE_PATH=abs_path)
    assert s2.QUOTA_STATE_PATH == abs_path

    # 3. Relative override is strictly refused to prevent split ledgers
    with pytest.raises(ValidationError) as exc_info:
        Settings(QUOTA_STATE_PATH="relative/path/quota.json")
    assert "must be an absolute path" in str(exc_info.value)


def test_embedding_model_coherence_under_google_provider():
    """Embedding model name must be an approved Google model when EMBEDDING_PROVIDER is 'google'."""
    from pydantic import ValidationError

    # 1. Default settings: provider='local', model='sentence-transformers/all-MiniLM-L6-v2' succeeds
    s_default = Settings()
    assert s_default.EMBEDDING_PROVIDER == "local"
    assert s_default.EMBEDDING_MODEL_NAME == "sentence-transformers/all-MiniLM-L6-v2"

    # 2. Overriding EMBEDDING_PROVIDER='google' without overriding EMBEDDING_MODEL_NAME fails
    with pytest.raises(ValidationError) as exc_info:
        Settings(EMBEDDING_PROVIDER="google")
    assert "must be explicitly configured to an approved Google embedding model" in str(exc_info.value)

    # 3. Overriding EMBEDDING_PROVIDER='google' with an unapproved/local model name fails
    with pytest.raises(ValidationError) as exc_info:
        Settings(EMBEDDING_PROVIDER="google", EMBEDDING_MODEL_NAME="sentence-transformers/all-MiniLM-L6-v2")
    assert "must be explicitly configured to an approved Google embedding model" in str(exc_info.value)

    # 4. Overriding EMBEDDING_PROVIDER='google' with approved models succeeds
    s_text004 = Settings(EMBEDDING_PROVIDER="google", EMBEDDING_MODEL_NAME="text-embedding-004")
    assert s_text004.EMBEDDING_MODEL_NAME == "text-embedding-004"

    s_gemini = Settings(EMBEDDING_PROVIDER="google", EMBEDDING_MODEL_NAME="gemini-embedding-001")
    assert s_gemini.EMBEDDING_MODEL_NAME == "gemini-embedding-001"

    s_prefixed = Settings(EMBEDDING_PROVIDER="google", EMBEDDING_MODEL_NAME="models/text-embedding-004")
    # Settings validator canonicalizes prefixed model names to unprefixed canonical tag
    assert s_prefixed.EMBEDDING_MODEL_NAME == "text-embedding-004"


def test_token_counter_and_embedder_model_congruence(monkeypatch):
    """When EMBEDDING_PROVIDER is 'google', embedder and token counter share the coherent Google model."""
    from app.core.config import settings
    from app.core.token_counter import get_default_token_counter
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-004")

    embedder = get_default_embedder(provider="google")
    counter = get_default_token_counter()

    assert embedder.model_name == "text-embedding-004"
    assert counter.model_name == "text-embedding-004"
    assert embedder.model_name == counter.model_name


def test_quota_max_total_attempts_parsing():
    """QUOTA_MAX_TOTAL_ATTEMPTS parses None, empty string and integer strings cleanly."""
    from app.core.config import Settings
    s_unset = Settings()
    assert s_unset.QUOTA_MAX_TOTAL_ATTEMPTS is None

    s_empty = Settings(QUOTA_MAX_TOTAL_ATTEMPTS="")
    assert s_empty.QUOTA_MAX_TOTAL_ATTEMPTS is None

    s_ws = Settings(QUOTA_MAX_TOTAL_ATTEMPTS="   ")
    assert s_ws.QUOTA_MAX_TOTAL_ATTEMPTS is None

    s_ten = Settings(QUOTA_MAX_TOTAL_ATTEMPTS="10")
    assert s_ten.QUOTA_MAX_TOTAL_ATTEMPTS == 10
