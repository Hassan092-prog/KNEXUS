import asyncio

import httpx
import pytest

from app.core.generation import run_generation
from app.schemas import EvidenceChunk, GenerationRequest, GenerationResult
from app.services.generation.errors import (
    GenerationConfigurationError,
    ProviderTimeoutError,
)
from app.services.generation.generator import GenerationService


def make_request(content: str = "Employees receive 21 leave days per year.") -> GenerationRequest:
    return GenerationRequest(
        question="How many annual leave days are allowed?",
        evidence=[EvidenceChunk(
            citation_id=1,
            chunk_id="11111111-1111-4111-8111-111111111111",
            document_id="22222222-2222-4222-8222-222222222222",
            document_title="Synthetic handbook",
            chunk_index=0,
            page=1,
            content=content,
            similarity_score=0.9,
        )],
    )


def test_provider_selection_must_be_explicit(monkeypatch):
    monkeypatch.delenv("OLLAMA_PROVIDER", raising=False)
    with pytest.raises(GenerationConfigurationError, match="Set OLLAMA_PROVIDER"):
        GenerationService()


def test_unknown_provider_is_rejected():
    with pytest.raises(GenerationConfigurationError, match="either 'fake' or 'ollama'"):
        GenerationService(provider="automatic")


@pytest.mark.asyncio
async def test_explicit_fake_provider_returns_contract_result():
    result = await GenerationService(provider="fake").generate(make_request())
    assert isinstance(result, GenerationResult)
    assert result.cited_ids == [1]
    assert not result.abstained


@pytest.mark.asyncio
async def test_concrete_service_runs_through_h01_injection_boundary():
    result = await run_generation(GenerationService(provider="fake"), make_request())
    assert result.cited_ids == [1]


@pytest.mark.asyncio
async def test_service_does_not_mutate_request():
    request = make_request("User input: a harmless quoted source string.")
    original = request.model_copy(deep=True)
    await GenerationService(provider="fake").generate(request)
    assert request == original


@pytest.mark.parametrize("timeout", [0.0, -1.0, float("nan"), float("inf"), -float("inf")])
def test_timeout_configuration_must_be_finite_and_positive(timeout):
    with pytest.raises(GenerationConfigurationError, match="finite and positive"):
        GenerationService(provider="fake", timeout=timeout)


@pytest.mark.asyncio
async def test_overall_deadline_covers_provider_work():
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    service = GenerationService(
        provider="ollama", timeout=0.02, transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderTimeoutError, match="overall timeout"):
        await service.generate(make_request())
    assert started.is_set()


@pytest.mark.asyncio
async def test_external_cancellation_is_not_converted_to_provider_timeout():
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    service = GenerationService(
        provider="ollama", timeout=5.0, transport=httpx.MockTransport(handler)
    )
    task = asyncio.create_task(service.generate(make_request()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
