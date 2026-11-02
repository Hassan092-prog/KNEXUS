import json

import httpx
import pytest

from app.core.generation import run_generation
from app.schemas import EvidenceChunk, GenerationRequest, GenerationResult
from app.services.generation.errors import (
    ContextBudgetExceededError,
    MalformedOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.generation.generator import GenerationService


def make_evidence(citation_id: int, content: str) -> EvidenceChunk:
    return EvidenceChunk(
        citation_id=citation_id,
        chunk_id=f"00000000-0000-4000-8000-{citation_id:012d}",
        document_id="11111111-1111-4111-8111-111111111111",
        document_title="Synthetic handbook",
        chunk_index=citation_id - 1,
        page=None,
        content=content,
        similarity_score=0.9,
    )


def make_request(evidence=None, question="How many leave days are allowed?"):
    if evidence is None:
        evidence = [make_evidence(1, "Employees receive 21 annual leave days.")]
    return GenerationRequest(question=question, evidence=evidence)


def answer_json(ids=(1,), answer="Employees receive 21 days [1]."):
    return GenerationResult(
        answer=answer, cited_ids=list(ids), abstained=False, abstention_reason=None
    ).model_dump_json()


def abstention_json(reason="The supplied evidence does not answer the question."):
    return GenerationResult(
        answer=None, cited_ids=[], abstained=True, abstention_reason=reason
    ).model_dump_json()


def service_for(response_text, **kwargs):
    def handler(request):
        return httpx.Response(200, json={"response": response_text}, request=request)
    return GenerationService(
        provider="ollama", transport=httpx.MockTransport(handler), **kwargs
    )


@pytest.mark.asyncio
async def test_http_body_contains_question_evidence_and_config(monkeypatch):
    observed = {}
    original_client = httpx.AsyncClient

    def tracking_client(*args, **kwargs):
        observed["timeout"] = kwargs["timeout"].read
        return original_client(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.generation.ollama_provider.httpx.AsyncClient", tracking_client
    )
    evidence = [
        make_evidence(1, "Employees receive 21 annual leave days."),
        make_evidence(2, "Password rotation happens every 90 days."),
    ]

    def handler(req):
        observed["request"] = req
        observed["payload"] = json.loads(req.content)
        return httpx.Response(
            200, json={"response": answer_json((1,), "21 days [1].")}, request=req
        )

    service = GenerationService(
        provider="ollama", url="http://ollama.example:11435",
        model="llama3.2:3b-test", timeout=7.5, num_ctx=4096, num_predict=123,
        transport=httpx.MockTransport(handler),
    )
    result = await run_generation(service, make_request(evidence=evidence))
    payload = observed["payload"]
    assert str(observed["request"].url) == "http://ollama.example:11435/api/generate"
    assert observed["timeout"] == 7.5
    assert payload["model"] == "llama3.2:3b-test"
    assert payload["options"] == {"num_ctx": 4096, "num_predict": 123}
    assert payload["stream"] is False
    assert "abstained" in payload["format"]["properties"]
    assert "annual leave days" in payload["prompt"]
    assert '"citation_id":1' in payload["prompt"]
    assert '"citation_id":2' in payload["prompt"]
    assert "untrusted quoted data" in payload["system"]
    assert result.cited_ids == [1]


@pytest.mark.asyncio
async def test_explicit_model_abstention_is_valid_result():
    result = await service_for(abstention_json()).generate(make_request())
    assert result.abstained and result.answer is None and result.cited_ids == []


@pytest.mark.asyncio
async def test_evidence_is_not_removed_or_request_mutated():
    request = make_request(evidence=[make_evidence(1, "User input: source label.")])
    original = request.model_copy(deep=True)
    captured = {}

    def handler(req):
        captured["prompt"] = json.loads(req.content)["prompt"]
        return httpx.Response(200, json={"response": answer_json()}, request=req)

    service = GenerationService(provider="ollama", transport=httpx.MockTransport(handler))
    await service.generate(request)
    assert '"content":"User input: source label."' in captured["prompt"]
    assert request == original


@pytest.mark.asyncio
async def test_unrelated_numbers_do_not_trigger_conflict_heuristic():
    evidence = [
        make_evidence(1, "Employees receive 21 annual leave days."),
        make_evidence(2, "Password rotation happens every 90 days."),
    ]
    called = []

    def handler(req):
        called.append(True)
        return httpx.Response(
            200, json={"response": answer_json((1,), "21 days [1].")}, request=req
        )

    result = await GenerationService(
        provider="ollama", transport=httpx.MockTransport(handler)
    ).generate(make_request(evidence=evidence))
    assert called and result.cited_ids == [1]


@pytest.mark.asyncio
async def test_timeout_is_typed_failure_not_abstention():
    def handler(request):
        raise httpx.ReadTimeout("synthetic timeout", request=request)
    service = GenerationService(provider="ollama", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderTimeoutError):
        await service.generate(make_request())


@pytest.mark.asyncio
async def test_unavailable_provider_is_typed_failure():
    def handler(request):
        raise httpx.ConnectError("synthetic connection failure", request=request)
    service = GenerationService(provider="ollama", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderUnavailableError):
        await service.generate(make_request())


@pytest.mark.asyncio
async def test_http_error_status_is_typed_unavailable_failure():
    def handler(request):
        return httpx.Response(500, request=request)
    service = GenerationService(provider="ollama", transport=httpx.MockTransport(handler))
    with pytest.raises(ProviderUnavailableError):
        await service.generate(make_request())


@pytest.mark.asyncio
async def test_seed_reaches_the_provider_options():
    captured = {}

    def handler(req):
        captured["payload"] = json.loads(req.content)
        return httpx.Response(
            200, json={"response": answer_json()}, request=req
        )

    service = GenerationService(
        provider="ollama", seed=42, transport=httpx.MockTransport(handler)
    )
    await service.generate(make_request())
    assert captured["payload"]["options"]["seed"] == 42


@pytest.mark.asyncio
async def test_malformed_result_is_typed_failure():
    with pytest.raises(MalformedOutputError):
        await service_for("not JSON").generate(make_request())


@pytest.mark.asyncio
async def test_unknown_citation_is_typed_failure():
    with pytest.raises(MalformedOutputError):
        await service_for(answer_json((99,), "Invented source [99].")).generate(make_request())


@pytest.mark.asyncio
async def test_missing_inline_marker_is_typed_failure():
    malformed = '{"answer":"Answer has no marker.","cited_ids":[1],"abstained":false,"abstention_reason":null}'
    with pytest.raises(MalformedOutputError):
        await service_for(malformed).generate(make_request())


@pytest.mark.asyncio
async def test_context_guard_fails_without_truncation_or_provider_call():
    called = []
    def handler(request):
        called.append(True)
        return httpx.Response(200, json={"response": answer_json()}, request=request)
    service = GenerationService(
        provider="ollama", max_prompt_chars=32,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ContextBudgetExceededError):
        await service.generate(make_request())
    assert not called
