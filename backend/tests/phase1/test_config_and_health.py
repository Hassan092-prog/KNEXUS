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
