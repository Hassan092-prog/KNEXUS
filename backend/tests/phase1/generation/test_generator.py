import os
import pytest
import anyio
from unittest import mock

from backend.app.services.generation.generator import generate
from contracts.phase1.models import GenerationRequest, EvidenceChunk, GenerationResult

# Helper to build a minimal GenerationRequest
def make_request() -> GenerationRequest:
    evidence = [
        EvidenceChunk(
            citation_id=1,
            chunk_id="11111111-1111-1111-1111-111111111111",
            document_id="22222222-2222-2222-2222-222222222222",
            document_title="Test Document",
            chunk_index=0,
            page=1,
            content="Some evidence content",
            similarity_score=0.99,
        )
    ]
    return GenerationRequest(question="What is the answer?", evidence=evidence)

@pytest.mark.anyio
async def test_generate_uses_fake_provider_by_default():
    # Ensure env var is not set to ollama
    os.environ.pop("OLLAMA_PROVIDER", None)
    request = make_request()
    result: GenerationResult = await generate(request)
    assert isinstance(result, GenerationResult)
    assert result.answer.startswith("Generated answer based on evidence")
    assert result.cited_ids == [1]
    assert not result.abstained

@pytest.mark.anyio
async def test_generate_switches_to_ollama_when_env_set(monkeypatch):
    # Patch the ollama_generate function to a dummy coroutine
    async def dummy_ollama(request: GenerationRequest) -> GenerationResult:
        answer = f"Ollama response [{request.evidence[0].citation_id}]"
        return GenerationResult(
            answer=answer,
            cited_ids=[request.evidence[0].citation_id],
            abstained=False,
            abstention_reason=None,
        )

    # Monkeypatch the provider in the generator module
    monkeypatch.setattr(
        "backend.app.services.generation.generator.ollama_generate",
        dummy_ollama,
    )
    # Set env var to trigger ollama path
    monkeypatch.setenv("OLLAMA_PROVIDER", "ollama")
    request = make_request()
    result = await generate(request)
    assert result.answer == f"Ollama response [{request.evidence[0].citation_id}]"
    assert result.cited_ids == [1]
