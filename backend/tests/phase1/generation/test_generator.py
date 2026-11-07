from pathlib import Path
from app.core.dispatch_policy import MockDispatchPolicy
from app.core.quota import QuotaConfig, QuotaLedger
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
    with pytest.raises(
        GenerationConfigurationError,
        match=r"must be one of: fake, groq, mistral, ollama, openai",
    ):
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
async def test_overall_deadline_covers_provider_work(tmp_path):
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q1.json", min_request_interval_seconds=0.0))
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="mock-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        timeout=0.02, transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderTimeoutError, match="overall timeout"):
        await service.generate(make_request())
    assert started.is_set()


@pytest.mark.asyncio
async def test_external_cancellation_is_not_converted_to_provider_timeout(tmp_path):
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q2.json", min_request_interval_seconds=0.0))
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="mock-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        timeout=5.0, transport=httpx.MockTransport(handler),
    )
    task = asyncio.create_task(service.generate(make_request()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.parametrize("seed", [True, 1.5, "3"])
def test_seed_configuration_must_be_an_integer(seed):
    with pytest.raises(GenerationConfigurationError, match="integer"):
        GenerationService(provider="fake", seed=seed)


@pytest.mark.asyncio
async def test_seed_is_optional_and_accepted_when_integer():
    service = GenerationService(provider="fake", seed=42)
    result = await service.generate(make_request())
    assert result.cited_ids == [1]


@pytest.mark.asyncio
async def test_prompt_assembly_is_deterministic():
    request = make_request()
    service = GenerationService(provider="fake")
    assert service._build_prompt(request) == service._build_prompt(request)
    system_prompt, prompt = service._build_prompt(request)
    assert '"question":"How many annual leave days are allowed?"' in prompt
    assert '"content":"Employees receive 21 leave days per year."' in prompt
    assert system_prompt.startswith("You answer questions using only the supplied evidence")


def test_prompt_requires_inline_citation_markers():
    from app.services.generation.generator import _SYSTEM_PROMPT, _GENERATION_PROMPT_VERSION
    assert '"cited_ids": [1]' in _SYSTEM_PROMPT
    assert '"abstained": false' in _SYSTEM_PROMPT and '"abstained": true' in _SYSTEM_PROMPT
    assert _GENERATION_PROMPT_VERSION.startswith("v")

def test_ollama_provider_is_deprecated_and_refused():
    with pytest.raises(GenerationConfigurationError, match="Local Ollama provider is deprecated and refused"):
        GenerationService(provider="ollama")
