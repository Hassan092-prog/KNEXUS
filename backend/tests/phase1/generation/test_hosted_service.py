"""Mocked chat-completions tests for the hosted generation adapter.

Selection, configuration, payload composition, typed failures and boundary
behavior mirror the Ollama adapter tests; no live API call is made here.
"""
import asyncio
import json

import httpx
import pytest

from app.core.generation import run_generation
from app.schemas import EvidenceChunk, GenerationRequest, GenerationResult
from app.services.generation.errors import (
    ContextBudgetExceededError,
    GenerationConfigurationError,
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


def completion_body(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def completion_handler(content):
    def handler(request):
        return httpx.Response(
            200, json=completion_body(content), headers={"x-request-id": "t"}, request=request
        )
    return handler


def hosted_service(handler, **kwargs):
    return GenerationService(
        provider="openai",
        model="gpt-test-mini",
        api_key="test-secret-key",
        transport=httpx.MockTransport(handler),
        **kwargs
    )


def recording_handler(store):  # captures request details and answers normally
    def handler(req):
        store["url"] = str(req.url)
        store["headers"] = dict(req.headers)
        store["payload"] = json.loads(req.content)
        store["raw"] = req.content.decode("utf-8")
        return httpx.Response(
            200, json=completion_body(answer_json()), request=req
        )
    return handler


@pytest.mark.asyncio
async def test_hosted_selection_reaches_chat_completions_with_config():
    observed = {}

    def handler(req):
        observed["url"] = str(req.url)
        observed["headers"] = dict(req.headers)
        observed["payload"] = json.loads(req.content)
        return httpx.Response(
            200, json=completion_body(answer_json((1,), "21 days [1].")), request=req
        )

    service = GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        timeout=12.5, num_predict=123, temperature=0.25, seed=7,
        transport=httpx.MockTransport(handler),
    )
    result = await run_generation(service, make_request())
    assert observed["url"] == "https://api.openai.com/v1/chat/completions"
    assert observed["headers"]["authorization"] == "Bearer test-secret-key"
    payload = observed["payload"]
    assert payload["model"] == "gpt-test-mini"
    assert payload["temperature"] == 0.25
    assert payload["max_tokens"] == 123
    assert payload["seed"] == 7
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]
    assert payload["response_format"]["type"] == "json_schema"
    assert "abstained" in payload["response_format"]["json_schema"]["schema"]["properties"]
    assert "annual leave days" in payload["messages"][1]["content"]
    assert "untrusted quoted data" in payload["messages"][0]["content"]
    assert "num_ctx" not in payload
    assert result.cited_ids == [1]


@pytest.mark.asyncio
async def test_groq_and_mistral_use_default_endpoints_and_overrides_apply():
    for provider, expected in (
        ("groq", "https://api.groq.com/openai/v1/chat/completions"),
        ("mistral", "https://api.mistral.ai/v1/chat/completions"),
    ):
        observed = {}

        def handler(req, expected=expected, observed=observed):
            observed["url"] = str(req.url)
            return httpx.Response(
                200, json=completion_body(abstention_json()), request=req
            )

        service = GenerationService(
            provider=provider, model=f"{provider}-test-model",
            api_key="test-secret-key", transport=httpx.MockTransport(handler),
        )
        result = await service.generate(make_request())
        assert observed["url"] == expected
        assert result.abstained and result.answer is None and result.cited_ids == []
    override_store = {}
    service = GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        api_base_url="https://hosted.example/v7",
        transport=httpx.MockTransport(recording_handler(override_store)),
    )
    await service.generate(make_request())
    assert override_store["url"] == "https://hosted.example/v7/chat/completions"


@pytest.mark.asyncio
async def test_missing_api_key_fails_configuration_before_any_provider_call(monkeypatch):
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    called = []

    def handler(req):
        called.append(True)
        return httpx.Response(200, json=completion_body(answer_json()), request=req)

    service = GenerationService(
        provider="groq", model="groq-test-model",
        transport=httpx.MockTransport(handler),
    )
    assert service.api_key is None
    with pytest.raises(GenerationConfigurationError, match="GENERATION_API_KEY"):
        await service.generate(make_request())
    assert not called
    assert service.provider == "groq" and service.model == "groq-test-model"


@pytest.mark.asyncio
async def test_strict_response_schema_is_provider_compliant():
    captured = {}

    def handler(req):
        captured["schema"] = json.loads(req.content)["response_format"]["json_schema"]
        return httpx.Response(200, json=completion_body(answer_json()), request=req)

    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        transport=httpx.MockTransport(handler),
    ).generate(make_request())
    schema = captured["schema"]
    assert schema["name"] == "generation_result" and schema["strict"] is True
    body = schema["schema"]
    assert body["additionalProperties"] is False
    assert set(body["required"]) == set(body["properties"])
    for spec in body["properties"].values():
        assert "default" not in spec


@pytest.mark.asyncio
async def test_api_key_env_fallback_is_used(monkeypatch):
    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    observed = {}

    def handler(req):
        observed["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json=completion_body(answer_json()), request=req)

    service = GenerationService(
        provider="openai", model="gpt-test-mini",
        transport=httpx.MockTransport(handler),
    )
    await service.generate(make_request())
    assert observed["auth"] == "Bearer env-secret-key"


@pytest.mark.asyncio
async def test_api_key_is_not_leaked_into_payload():
    observed = {}

    def handler(req):
        observed["payload"] = json.loads(req.content)
        observed["raw"] = req.content.decode("utf-8")
        return httpx.Response(200, json=completion_body(answer_json()), request=req)

    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        transport=httpx.MockTransport(handler),
    ).generate(make_request())
    assert "test-secret-key" not in observed["raw"]
    assert "test-secret-key" not in json.dumps(observed["payload"])


@pytest.mark.asyncio
async def test_seed_only_reaches_the_payload_when_explicitly_set():
    without_seed = {}

    def capture(store):
        def handler(req):
            store["payload"] = json.loads(req.content)
            return httpx.Response(200, json=completion_body(answer_json()), request=req)
        return handler

    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        transport=httpx.MockTransport(capture(without_seed)),
    ).generate(make_request())
    assert "seed" not in without_seed["payload"]
    with_seed = {}
    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        seed=42, transport=httpx.MockTransport(capture(with_seed)),
    ).generate(make_request())
    assert with_seed["payload"]["seed"] == 42


@pytest.mark.asyncio
async def test_valid_answer_and_abstention_are_canonical():
    result = await hosted_service(
        completion_handler(answer_json())
    ).generate(make_request())
    assert result.model_dump() == {
        "answer": "Employees receive 21 days [1].",
        "cited_ids": [1], "abstained": False, "abstention_reason": None,
    }
    abstained = await hosted_service(
        completion_handler(abstention_json())
    ).generate(make_request(question="Unrelated question?"))
    assert abstained.abstained and abstained.cited_ids == []


@pytest.mark.asyncio
async def test_malformed_provider_body_shapes_fail_typed():
    bodies = [
        "not JSON at all",
        {"object": "chat.response"},
        {},  # no choices
        {"choices": []},
        {"choices": [{"message": {}}]},
        {"choices": [{"message": {"content": 42}}]},
        {"choices": [{"role": "assistant", "text": answer_json()}]},
    ]
    for body in bodies:
        def handler(req, body=body):
            return (
                httpx.Response(200, json=body, request=req)
                if not isinstance(body, str)
                else httpx.Response(200, text=body, request=req)
            )
        with pytest.raises(MalformedOutputError):
            await GenerationService(
                provider="openai", model="gpt-test-mini", api_key="test-secret-key",
                transport=httpx.MockTransport(handler),
            ).generate(make_request())


@pytest.mark.asyncio
async def test_contract_violating_content_fails_typed():
    violations = [
        "not JSON",  # schema-invalid content
        answer_json((99,), "Invented source [99]."),  # unknown citation
        '{"answer":"Answer has no marker.","cited_ids":[1],"abstained":false,"abstention_reason":null}',
    ]
    for content in violations:
        with pytest.raises(MalformedOutputError):
            await hosted_service(completion_handler(content)).generate(make_request())


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 429, 500, 503])
async def test_http_error_statuses_are_typed_unavailable_with_status(status):
    def handler(req):
        return httpx.Response(status, json={"error": {"message": "x"}}, request=req)

    with pytest.raises(ProviderUnavailableError, match=f"HTTP {status}"):
        await hosted_service(handler).generate(make_request())


@pytest.mark.asyncio
async def test_provider_read_timeout_is_typed_timeout():
    def handler(request):
        raise httpx.ReadTimeout("synthetic timeout", request=request)

    with pytest.raises(ProviderTimeoutError):
        await hosted_service(handler).generate(make_request())


@pytest.mark.asyncio
async def test_connect_error_is_typed_unavailable():
    def handler(request):
        raise httpx.ConnectError("synthetic connection failure", request=request)

    with pytest.raises(ProviderUnavailableError):
        await hosted_service(handler).generate(make_request())


@pytest.mark.asyncio
async def test_overall_deadline_covers_hosted_provider_work():
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    service = GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        timeout=0.02, transport=httpx.MockTransport(handler),
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
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        timeout=5.0, transport=httpx.MockTransport(handler),
    )
    task = asyncio.create_task(service.generate(make_request()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_evidence_is_supplied_verbatim_and_request_not_mutated():
    request = make_request(evidence=[make_evidence(3, "User input: source label.")])
    original = request.model_copy(deep=True)
    captured = {}

    def handler(req):
        captured["prompt"] = json.loads(req.content)["messages"][1]["content"]
        return httpx.Response(200, json=completion_body(answer_json((3,), "3 days [3].")), request=req)

    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        transport=httpx.MockTransport(handler),
    ).generate(request)
    assert '"content":"User input: source label."' in captured["prompt"]
    assert '"citation_id":3' in captured["prompt"]
    assert request == original


@pytest.mark.asyncio
async def test_context_guard_fails_before_any_hosted_call():
    called = []

    def handler(request):
        called.append(True)
        return httpx.Response(200, json=completion_body(answer_json()), request=request)

    service = GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        max_prompt_chars=32, transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ContextBudgetExceededError):
        await service.generate(make_request())
    assert not called


def test_hosted_constructor_configuration_validation(monkeypatch):
    monkeypatch.delenv("GENERATION_MODEL", raising=False)
    # missing model without env fallback fails construction
    with pytest.raises(GenerationConfigurationError, match="model"):
        GenerationService(provider="openai")
    with pytest.raises(GenerationConfigurationError, match="temperature"):
        GenerationService(provider="openai", model="m", temperature=-1)
    with pytest.raises(GenerationConfigurationError, match="positive"):
        GenerationService(provider="openai", model="m", num_predict=0)
    # fake/ollama keep the OLLAMA_* env names; hosted uses GENERATION_*
    confirmed = GenerationService(provider="ollama", model="llama3.2:3b")
    assert confirmed.temperature == 0.0 and confirmed.api_key is None
