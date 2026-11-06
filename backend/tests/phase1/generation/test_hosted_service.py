"""Mocked chat-completions tests for the hosted generation adapter.

Selection, configuration, payload composition, typed failures and boundary
behavior mirror the Ollama adapter tests; no live API call is made here.

Hosted dispatch is fail-closed by default: every mocked hosted call in this
module explicitly injects `MockDispatchPolicy` (published interface) — the
injection itself documents that keys, provider selection and flags never
authorize dispatch. Ledger composition tests use the published QuotaLedger
with per-test state paths.
"""
import asyncio
import json
from pathlib import Path

import httpx
import pytest

from app.core.dispatch_policy import (
    BlockedLiveDispatchPolicy,
    LiveInferenceBlockedError,
    MockDispatchPolicy,
)
from app.core.generation import run_generation
from app.core.quota import (
    QuotaConfig,
    QuotaLedger,
    RateLimitExceededError,
)
from app.schemas import EvidenceChunk, GenerationRequest, GenerationResult
from app.services.generation.errors import (
    ContextBudgetExceededError,
    GenerationConfigurationError,
    GenerationSettlementError,
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


def usage_json(prompt_tokens=10, completion_tokens=5, total_tokens=15):
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


def completion_body(content, usage=None, finish_reason="stop"):
    message = {"role": "assistant", "content": content}
    body = {"choices": [{"message": message, "finish_reason": finish_reason}]}
    if usage is not None:
        body["usage"] = usage
    return body


def completion_handler(content, **kwargs):
    def handler(request):
        return httpx.Response(200, json=completion_body(content, **kwargs), request=request)
    return handler


def hosted_service(handler, **kwargs):
    """Hosted test service with an explicitly injected mock dispatch policy.

    Hosted providers are blocked by default; mocked tests inject the
    MockDispatchPolicy explicitly to authorize mocked transport calls.
    """
    kwargs.setdefault("dispatch_policy", MockDispatchPolicy("openai"))
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


def make_ledger(tmp_path, **overrides) -> QuotaLedger:
    """Published QuotaLedger with fast, enabled test-scoped state."""
    defaults = dict(
        enabled=True,
        max_requests_per_minute=100,
        max_requests_per_day=1000,
        max_total_attempts=100,
        min_request_interval_seconds=0.0,
        state_path=tmp_path / "generation-ledger.json",
    )
    return QuotaLedger(QuotaConfig(**{**defaults, **overrides}))


def settled_records(ledger) -> list[dict]:
    state = json.loads(ledger.state_path.read_text())
    return state["settled_requests"]


class FailingSettleLedger:
    """Reserves normally; always fails settlement (published-method shape)."""

    def __init__(self):
        self.reserved = 0

    async def areserve_attempt(self, provider: str, model: str) -> str:
        self.reserved += 1
        return f"attempt-{self.reserved}"

    async def asettle_attempt(
        self, attempt_id, *, usage=None, success=True, error=None, status_code=None
    ) -> None:
        raise ValueError("synthetic ledger write failure")


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
        dispatch_policy=MockDispatchPolicy("openai"),
        transport=httpx.MockTransport(handler),
    )
    result = await run_generation(service, make_request())
    assert observed["url"] == "https://api.openai.com/v1/chat/completions"
    assert observed["headers"]["authorization"] == "Bearer test-secret-key"
    payload = observed["payload"]
    assert payload["model"] == "gpt-test-mini"
    assert payload["temperature"] == 0.25
    # OpenAI documents max_completion_tokens; the deprecated max_tokens name
    # is deliberately absent.
    assert payload["max_completion_tokens"] == 123
    assert "max_tokens" not in payload
    assert payload["seed"] == 7
    assert [m["role"] for m in payload["messages"]] == ["system", "user"]
    assert payload["response_format"]["type"] == "json_schema"
    assert "abstained" in payload["response_format"]["json_schema"]["schema"]["properties"]
    assert "annual leave days" in payload["messages"][1]["content"]
    assert "untrusted quoted data" in payload["messages"][0]["content"]
    assert "num_ctx" not in payload
    assert result.cited_ids == [1]


@pytest.mark.asyncio
async def test_groq_and_mistral_use_default_endpoints_and_per_provider_token_keys():
    for provider, expected_url, token_key in (
        ("groq", "https://api.groq.com/openai/v1/chat/completions", "max_completion_tokens"),
        ("mistral", "https://api.mistral.ai/v1/chat/completions", "max_tokens"),
    ):
        observed = {}

        def handler(req, observed=observed):
            observed["url"] = str(req.url)
            observed["payload"] = json.loads(req.content)
            return httpx.Response(
                200, json=completion_body(abstention_json()), request=req
            )

        service = GenerationService(
            provider=provider, model=f"{provider}-test-model",
            api_key="test-secret-key",
            dispatch_policy=MockDispatchPolicy(provider),
            transport=httpx.MockTransport(handler),
        )
        result = await service.generate(make_request())
        assert observed["url"] == expected_url
        assert observed["payload"][token_key] == 512
        assert "max_tokens" not in observed["payload"] or token_key == "max_tokens"
        if token_key == "max_completion_tokens":
            assert "max_tokens" not in observed["payload"]
        assert result.abstained and result.answer is None and result.cited_ids == []
    override_store = {}
    service = GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        api_base_url="https://hosted.example/v7",
        dispatch_policy=MockDispatchPolicy("openai"),
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
        dispatch_policy=MockDispatchPolicy("groq"),
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
        dispatch_policy=MockDispatchPolicy("openai"),
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
async def test_schema_structure_preserves_every_canonical_property():
    """No recursive keyword filtering may drop fields, names or semantics.

    The sent schema is byte-for-byte (object-for-object) the canonical strict
    schema: property names, anyOf null-unions and the required list are all
    preserved, and no batch/schema projection exists.
    """
    from app.services.generation.hosted_provider import strict_generation_schema

    captured = {}

    def handler(req):
        captured["schema"] = json.loads(req.content)["response_format"]["json_schema"]
        return httpx.Response(200, json=completion_body(answer_json()), request=req)

    await hosted_service(handler).generate(make_request())
    assert captured["schema"]["schema"] == strict_generation_schema()
    properties = captured["schema"]["schema"]["properties"]
    assert list(properties) == ["answer", "cited_ids", "abstained", "abstention_reason"]
    answer_spec = properties["answer"]
    # Documented-subset keywords and local constraints stay intact; structure
    # (including anyOf null unions) is never silently dropped.
    assert {"minLength": 1, "type": "string"} in answer_spec["anyOf"]
    assert {"type": "null"} in answer_spec["anyOf"]
    assert properties["abstained"]["type"] == "boolean"
    assert properties["cited_ids"]["items"]["minimum"] == 1
    assert properties["cited_ids"]["maxItems"] == 20
    union = properties["abstention_reason"]["anyOf"]
    assert {"type": "null"} in union


@pytest.mark.asyncio
async def test_api_key_env_fallback_is_used(monkeypatch):
    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    observed = {}

    def handler(req):
        observed["auth"] = req.headers.get("authorization")
        return httpx.Response(200, json=completion_body(answer_json()), request=req)

    service = GenerationService(
        provider="openai", model="gpt-test-mini",
        dispatch_policy=MockDispatchPolicy("openai"),
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
        dispatch_policy=MockDispatchPolicy("openai"),
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
        dispatch_policy=MockDispatchPolicy("openai"),
        transport=httpx.MockTransport(capture(without_seed)),
    ).generate(make_request())
    assert "seed" not in without_seed["payload"]
    with_seed = {}
    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("openai"),
        seed=42, transport=httpx.MockTransport(capture(with_seed)),
    ).generate(make_request())
    assert with_seed["payload"]["seed"] == 42


@pytest.mark.asyncio
async def test_reasoning_controls_reach_payload_only_when_configured():
    store = {}

    def capture(store):
        def handler(req):
            store["payload"] = json.loads(req.content)
            return httpx.Response(200, json=completion_body(answer_json()), request=req)
        return handler

    dispatch = MockDispatchPolicy("openai")
    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        dispatch_policy=dispatch,
        transport=httpx.MockTransport(capture(store)),
    ).generate(make_request())
    assert "reasoning_effort" not in store["payload"]
    assert "include_reasoning" not in store["payload"]
    store = {}
    await GenerationService(
        provider="openai", model="gpt-test-mini", api_key="test-secret-key",
        dispatch_policy=dispatch,
        reasoning_effort="low", include_reasoning=False,
        transport=httpx.MockTransport(capture(store)),
    ).generate(make_request())
    assert store["payload"]["reasoning_effort"] == "low"
    assert store["payload"]["include_reasoning"] is False


def test_hosted_constructor_defaults_are_fail_closed(monkeypatch):
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    # Hosted providers default to the blocked policy: no injected policy,
    # no authorization. Keys, provider selection, or flags never change it.
    service = GenerationService(provider="groq", model="groq-test-model")
    assert isinstance(service.dispatch_policy, BlockedLiveDispatchPolicy)
    assert service.quota_ledger is None
    # Explicitly injected overrides are honored and passed through.
    ledger = QuotaLedger(QuotaConfig(enabled=False, state_path=Path("unused.json")))
    authorized = GenerationService(
        provider="groq", model="groq-test-model",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
    )
    assert isinstance(authorized.dispatch_policy, MockDispatchPolicy)
    assert authorized.quota_ledger is ledger
    # Ollama/fake legacy paths never carry a dispatch policy or ledger.
    legacy = GenerationService(provider="ollama", model="llama3.2:3b")
    assert legacy.dispatch_policy is None and legacy.quota_ledger is None


def test_hosted_constructor_reasoning_and_ledger_validation():
    with pytest.raises(GenerationConfigurationError, match="reasoning_effort"):
        GenerationService(
            provider="groq", model="m", reasoning_effort="maximum"
        )
    with pytest.raises(GenerationConfigurationError, match="include_reasoning"):
        GenerationService(
            provider="groq", model="m", include_reasoning="false"
        )
    # Valid documented values are accepted.
    GenerationService(
        provider="groq", model="m", reasoning_effort="low", include_reasoning=False
    )


@pytest.mark.asyncio
async def test_default_dispatch_is_blocked_before_any_http_or_client_creation():
    """Blocked by default: no HTTP client, no call, no key usage needed."""
    called = []

    def handler(req):
        called.append(True)
        return httpx.Response(200, json=completion_body(answer_json()), request=req)

    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LiveInferenceBlockedError, match="blocked"):
        await service.generate(make_request())
    assert not called
    # MockDispatchPolicy scoped to another provider stays blocked for groq.
    scoped = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("openai"),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(LiveInferenceBlockedError):
        await scoped.generate(make_request())
    assert not called


@pytest.mark.asyncio
async def test_authorized_mock_dispatch_reserves_and_settles_success(tmp_path):
    ledger = make_ledger(tmp_path)
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        transport=httpx.MockTransport(
            completion_handler(answer_json(), usage=usage_json())
        ),
    )
    result = await service.generate(make_request())
    assert result.cited_ids == [1]
    records = settled_records(ledger)
    assert len(records) == 1
    record = records[0]
    assert record["success"] is True
    assert record["provider"] == "groq"
    assert record["usage"] == {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
    }
    assert record["tokens_unresolved"] is False
    # A single attempt was reserved; no duplicate settlement is possible.
    assert len(record["attempt_id"]) > 0


@pytest.mark.asyncio
async def test_usage_is_captured_even_when_output_is_invalid(tmp_path):
    """Usage is settled before parsing/validation, never after legality."""
    ledger = make_ledger(tmp_path)
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        transport=httpx.MockTransport(
            completion_handler(answer_json((99,), "Invented source [99]."),
                               usage=usage_json())
        ),
    )
    with pytest.raises(MalformedOutputError, match="generation contract"):
        await service.generate(make_request())
    records = settled_records(ledger)
    assert len(records) == 1
    record = records[0]
    assert record["success"] is False
    assert record["error"] == "citation_contract_violation"
    assert record["usage"] == {
        "prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15,
    }
    assert record["tokens_unresolved"] is False


@pytest.mark.asyncio
async def test_settlement_failures_are_typed_and_never_swallowed(tmp_path):
    failing = FailingSettleLedger()
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=failing,
        transport=httpx.MockTransport(completion_handler(answer_json())),
    )
    with pytest.raises(GenerationSettlementError, match="outstanding reservation preserved"):
        await service.generate(make_request())
    # The attempt was still reserved before dispatch.
    assert failing.reserved == 1

    # On a failing output path the settlement error preserves the original
    # provider-failure classification instead of masking it.
    failing2 = FailingSettleLedger()
    service2 = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=failing2,
        transport=httpx.MockTransport(
            completion_handler(answer_json((99,), "Invented source [99]."))
        ),
    )
    with pytest.raises(GenerationSettlementError, match="citation_contract_violation"):
        await service2.generate(make_request())
    assert failing2.reserved == 1


@pytest.mark.asyncio
async def test_missing_or_malformed_usage_stays_unknown_never_zero(tmp_path):
    ledger = make_ledger(tmp_path)
    # No usage object in the body at all.
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        transport=httpx.MockTransport(completion_handler(answer_json())),
    )
    await service.generate(make_request())
    record = settled_records(ledger)[0]
    assert record["usage"] is None
    assert record["tokens_unresolved"] is True
    assert record["success"] is True

    # Malformed usage is likewise unresolved; zero is never invented.
    ledger2 = make_ledger(tmp_path, state_path=tmp_path / "malformed.json")
    service2 = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger2,
        transport=httpx.MockTransport(
            completion_handler(answer_json(),
                               usage={"prompt_tokens": -1, "total_tokens": "x"})
        ),
    )
    await service2.generate(make_request())
    record = settled_records(ledger2)[0]
    assert record["usage_valid"] is False
    assert record["tokens_unresolved"] is True


@pytest.mark.asyncio
async def test_http_429_settles_the_tripwire_without_retry_or_fallback(tmp_path):
    calls = []

    def handler(req):
        calls.append(True)
        return httpx.Response(429, json={"error": {"message": "x"}}, request=req)

    ledger = make_ledger(tmp_path)
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderUnavailableError, match="HTTP 429"):
        await service.generate(make_request())
    assert len(calls) == 1  # exactly one attempt; no automatic retry
    record = settled_records(ledger)[0]
    assert record["status_code"] == 429 and record["success"] is False

    # The published 429 scope tripwire is now permanent for this scope.
    with pytest.raises(RateLimitExceededError, match="rate limit active"):
        ledger.reserve_attempt("groq", "groq-test-model")


@pytest.mark.asyncio
async def test_external_cancellation_settles_without_usage_and_propagates(tmp_path):
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    ledger = make_ledger(tmp_path)
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        timeout=5.0, transport=httpx.MockTransport(handler),
    )
    task = asyncio.create_task(service.generate(make_request()))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    records = settled_records(ledger)
    assert len(records) == 1
    record = records[0]
    assert record["success"] is False
    assert record["error"] == "cancelled"
    assert record["usage"] is None and record["tokens_unresolved"] is True


@pytest.mark.asyncio
async def test_overall_deadline_cancellation_settles_and_maps_to_timeout(tmp_path):
    started = asyncio.Event()

    async def handler(request):
        started.set()
        await asyncio.Event().wait()

    ledger = make_ledger(tmp_path)
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        timeout=0.05, transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderTimeoutError, match="overall timeout"):
        await service.generate(make_request())
    record = settled_records(ledger)[0]
    assert record["success"] is False
    assert record["usage"] is None


@pytest.mark.asyncio
async def test_truncated_finish_reason_fails_deliberately(tmp_path):
    ledger = make_ledger(tmp_path)
    truncated_answer = 'Truncated before completion'  # valid HTTP body, cut output
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
        transport=httpx.MockTransport(
            lambda req: httpx.Response(
                200,
                json=completion_body(
                    truncated_answer, usage=usage_json(), finish_reason="length"
                ),
                request=req,
            )
        ),
    )
    with pytest.raises(MalformedOutputError, match="truncated"):
        await service.generate(make_request())
    record = settled_records(ledger)[0]
    assert record["error"] == "finish_reason_length"
    assert record["success"] is False and record["tokens_unresolved"] is False


@pytest.mark.asyncio
async def test_reasoning_only_and_prose_refusal_fail_distinctly():
    # Reasoning present but no content: never parsed as an answer.
    with pytest.raises(MalformedOutputError, match="reasoning without the required content"):
        await hosted_service(
            lambda req: httpx.Response(
                200,
                json={
                    "choices": [
                        {"message": {"role": "assistant", "reasoning": "thinking..."},
                         "finish_reason": "stop"}
                    ]
                },
                request=req,
            )
        ).generate(make_request())

    # Prose refusal content is typed and never copied into the error text.
    refusal = "I cannot comply with that request."
    with pytest.raises(MalformedOutputError, match="required JSON result") as excinfo:
        await hosted_service(completion_handler(refusal)).generate(make_request())
    assert refusal not in str(excinfo.value)


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
                dispatch_policy=MockDispatchPolicy("openai"),
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
        timeout=0.02, dispatch_policy=MockDispatchPolicy("openai"),
        transport=httpx.MockTransport(handler),
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
        timeout=5.0, dispatch_policy=MockDispatchPolicy("openai"),
        transport=httpx.MockTransport(handler),
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
        dispatch_policy=MockDispatchPolicy("openai"),
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
        max_prompt_chars=32, dispatch_policy=MockDispatchPolicy("openai"),
        transport=httpx.MockTransport(handler),
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


def test_prompt_char_fallback_matches_settings_default(monkeypatch):
    """Reconciled fallback: constructor default matches Settings (16000)."""
    monkeypatch.delenv("GENERATION_MAX_PROMPT_CHARS", raising=False)
    service = GenerationService(provider="ollama", model="llama3.2:3b")
    assert service.max_prompt_chars == 16000
