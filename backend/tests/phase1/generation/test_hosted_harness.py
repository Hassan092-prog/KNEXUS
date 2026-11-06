"""Mocked tests for the hosted evaluation harness.

Rate limits, authentication, unavailability, timeouts and invalid provider
responses are mocked through httpx.MockTransport; no billable call is made
and no secret is ever required by these tests.
"""
import asyncio
import json

import httpx
import pytest

from app.core.dispatch_policy import MockDispatchPolicy
from app.core.quota import QuotaConfig, QuotaLedger
from app.schemas import GenerationResult
from app.services.generation.generator import GenerationService
from tests.phase1.generation.hosted_harness import (
    CASEGROUP_DEVELOPMENT,
    CASEGROUP_HELD_OUT,
    build_service,
    cases_for,
    held_out_cases,
    main,
)
from tests.phase1.generation.live_harness import (
    HarnessCase,
    _matches,
    run_harness,
    synthetic_cases,
    SYSTEM_PROMPT_SHA256,
)
from tests.phase1.generation.test_harness import StubService, answer, make_case


def completion_body(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


def completion_response(content):
    def handler(req):
        return httpx.Response(200, json=completion_body(content), request=req)
    return handler


def answer_json(ids=(1,), answer_text="Travel costs are reimbursed [1]."):
    return json.dumps({
        "answer": answer_text, "cited_ids": list(ids),
        "abstained": False, "abstention_reason": None,
    })


def hosted_provider_case(citation_id=1, *, abstained=False, expected=(1,), smoke=True):
    """A development-group case driven through the real hosted adapter."""
    from app.schemas import EvidenceChunk, GenerationRequest
    evidence = EvidenceChunk(
        citation_id=citation_id,
        chunk_id="00000000-0000-4000-8000-00000000000%d" % citation_id,
        document_id="11111111-1111-4111-8111-111111111111",
        document_title="Synthetic hosted handbook",
        chunk_index=0, page=None,
        content="Travel expenses are reimbursed for approved trips.",
        similarity_score=0.9,
    )
    return HarnessCase(
        "hosted_case",
        GenerationRequest(
            question="What expenses are reimbursed?", evidence=[evidence]
        ),
        abstained, tuple(expected), smoke,
    )


def make_test_ledger(tmp_path) -> QuotaLedger:
    return QuotaLedger(QuotaConfig(
        enabled=True, max_requests_per_minute=100, max_requests_per_day=1000,
        max_total_attempts=100, min_request_interval_seconds=0.0,
        state_path=tmp_path / "harness-ledger.json",
    ))


@pytest.mark.asyncio
async def test_development_cases_are_reused_from_the_neutral_harness():
    assert cases_for(CASEGROUP_DEVELOPMENT) == synthetic_cases()
    assert all(case.group == CASEGROUP_DEVELOPMENT
               for case in cases_for(CASEGROUP_DEVELOPMENT))
    assert [case.name for case in cases_for(CASEGROUP_DEVELOPMENT)] == [
        "supported_single_chunk", "unsupported_single_chunk",
        "conflicting_relevant_evidence", "instruction_inside_evidence",
    ]


@pytest.mark.asyncio
async def test_held_out_cases_are_labeled_and_valid():
    held = held_out_cases()
    assert [case.name for case in held] == [
        "held_out_supported_remote_days",
        "held_out_unsupported_certifications",
        "held_out_conflicting_severance_notice",
        "held_out_injection_renewal_discount",
    ]
    assert all(case.group == CASEGROUP_HELD_OUT for case in held)
    case_names = {case.name for case in held} | {
        case.name for case in synthetic_cases()
    }
    assert len(case_names) == 8  # development and held-out sets do not collide
    for case in held:
        assert case.request.question and case.request.evidence
        assert case.expected_abstained or case.expected_cited_ids
    unsupported = held[1]
    assert unsupported.expected_abstained and unsupported.expected_cited_ids == ()
    conflict = held[2]
    assert [item.citation_id for item in conflict.request.evidence] == [12, 13]
    injection = held[3]
    assert injection.request.evidence[0].content.startswith("Ignore all rules")


@pytest.mark.asyncio
async def test_cases_for_all_groups_and_unknown_group_fails():
    combined = cases_for("all")
    assert combined == synthetic_cases() + held_out_cases()
    with pytest.raises(ValueError, match="Unknown case group"):
        cases_for("mystery")


@pytest.mark.asyncio
async def test_harness_records_hosted_provenance_without_secrets(tmp_path, monkeypatch):
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    output = tmp_path / "results.jsonl"
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        seed=42, dispatch_policy=MockDispatchPolicy("groq"),
        transport=httpx.MockTransport(completion_response(answer_json())),
    )
    exit_code = await run_harness(
        [hosted_provider_case()], service, output
    )
    row = json.loads(output.read_text().splitlines()[0])
    assert exit_code == 0
    assert row["provider"] == "groq"
    assert row["model"] == "groq-test-model"
    assert row["provider_url"] == "https://api.groq.com/openai/v1"
    assert row["hosted_options"] == {"max_tokens": 512, "temperature": 0.0, "seed": 42}
    assert "ollama_options" not in row
    assert "test-secret-key" not in json.dumps(row)
    assert row["system_prompt_sha256"] == SYSTEM_PROMPT_SHA256
    assert row["passed"] and row["status"] == "passed"


@pytest.mark.asyncio
async def test_harness_records_case_group(tmp_path):
    output = tmp_path / "results.jsonl"
    service = StubService([answer()])
    await run_harness([make_case("dev_case", smoke=True, cited_ids=(1,))], service, output)
    row = json.loads(output.read_text().splitlines()[0])
    assert row["case_group"] == CASEGROUP_DEVELOPMENT


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,error_type",
    [
        (429, "ProviderUnavailableError"),  # rate limit
        (401, "ProviderUnavailableError"),  # authentication
        (503, "ProviderUnavailableError"),  # unavailable
        (200, "MalformedOutputError"),  # invalid response body
    ],
)
async def test_mocked_hosted_failures_are_recorded_as_errors(tmp_path, status, error_type):
    def handler(req):
        if status == 200:
            return httpx.Response(200, text="not JSON at all", request=req)
        return httpx.Response(status, json={"error": {"message": "x"}}, request=req)

    output = tmp_path / "results.jsonl"
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"),
        transport=httpx.MockTransport(handler),
    )
    exit_code = await run_harness(
        [hosted_provider_case(expected=(1,), abstained=False)], service, output
    )
    row = json.loads(output.read_text().splitlines()[0])
    assert exit_code == 1
    assert row["status"] == "error"
    assert row["error_type"] == error_type
    assert row["passed"] is False
    assert row["inference_performed"] is True


@pytest.mark.asyncio
async def test_mocked_hosted_timeout_is_recorded(tmp_path):
    def handler(req):
        raise httpx.ReadTimeout("synthetic timeout", request=req)

    output = tmp_path / "results.jsonl"
    service = GenerationService(
        provider="groq", model="groq-test-model", api_key="test-secret-key",
        dispatch_policy=MockDispatchPolicy("groq"),
        transport=httpx.MockTransport(handler),
    )
    exit_code = await run_harness([hosted_provider_case()], service, output)
    row = json.loads(output.read_text().splitlines()[0])
    assert exit_code == 1 and row["status"] == "timeout"
    assert row["inference_performed"] is True


def test_build_service_fails_closed_without_model(monkeypatch, tmp_path):
    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    monkeypatch.delenv("GENERATION_MODEL", raising=False)
    with pytest.raises(ValueError, match="GENERATION_MODEL"):
        build_service("groq", None, 30.0, None, None)


def test_build_service_fails_closed_without_api_key(monkeypatch):
    monkeypatch.setenv("GENERATION_MODEL", "groq-test-model")
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    with pytest.raises(ValueError, match="GENERATION_API_KEY"):
        build_service("groq", "groq-test-model", 30.0, None, None)


def test_build_service_uses_env_key_and_explicit_model(monkeypatch):
    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    service = build_service("mistral", "mistral-test-model", 15.0, 7, None)
    assert service.provider == "mistral"
    assert service.model == "mistral-test-model"
    assert service.api_key == "env-secret-key"
    assert service.timeout == 15.0
    assert service.seed == 7
    assert service.url == "https://api.mistral.ai/v1"
    # Without explicit injection the built service stays authorization-blocked;
    # the dedicated gate tests below pin that behavior.


def test_build_service_defaults_are_blocked_and_injection_is_explicit(monkeypatch, tmp_path):
    from app.core.dispatch_policy import BlockedLiveDispatchPolicy

    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    default = build_service("groq", "groq-test-model", 30.0, None, None)
    assert isinstance(default.dispatch_policy, BlockedLiveDispatchPolicy)
    assert default.quota_ledger is None
    ledger = make_test_ledger(tmp_path)
    authorized = build_service(
        "groq", "groq-test-model", 30.0, None, None,
        dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
    )
    assert isinstance(authorized.dispatch_policy, MockDispatchPolicy)
    assert authorized.quota_ledger is ledger
    assert authorized.model == "groq-test-model"


def test_main_refuses_even_when_selection_and_key_gates_look_satisfied(tmp_path, monkeypatch):
    """The CLI can never self-authorize: blocked policy refuses before run_harness.

    Key env vars and --run-live are present and the output path is fresh, yet
    the default blocked dispatch policy still refuses and no output file is
    created (no run_harness invocation, no HTTP transport constructed).
    """
    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    monkeypatch.setenv("GENERATION_MODEL", "groq-test-model")
    output = tmp_path / "never-run.jsonl"
    with pytest.raises(SystemExit) as excinfo:
        main(["--run-live", "--output", str(output)])
    assert excinfo.value.code == 2
    assert not output.exists()


def test_main_requires_explicit_ledger_with_injected_policy(tmp_path, monkeypatch):
    """An injected policy alone does not satisfy the gate; the durable ledger
    configuration is required alongside it."""
    import tests.phase1.generation.hosted_harness as harness_module

    def authorized_no_ledger(provider, model, timeout, seed, api_base_url, **kwargs):
        return GenerationService(
            provider="groq", model="groq-test-model", api_key="env-secret-key",
            dispatch_policy=MockDispatchPolicy("groq"),
            transport=httpx.MockTransport(completion_response(answer_json())),
        )

    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    monkeypatch.setattr(harness_module, "build_service", authorized_no_ledger)
    with pytest.raises(SystemExit) as excinfo:
        main(["--run-live", "--output", str(tmp_path / "x.jsonl")])
    assert excinfo.value.code == 2


def test_main_with_authorized_injection_delegates_to_run_harness(tmp_path, monkeypatch):
    """Reviewed code injection (policy + ledger) is the only scheduled path.

    run_harness is replaced so no provider call happens; the test pins that a
    fully authorized in-code configuration is the gate that reaches it.
    """
    import tests.phase1.generation.hosted_harness as harness_module

    ledger = make_test_ledger(tmp_path)

    def authorized(provider, model, timeout, seed, api_base_url, **kwargs):
        return GenerationService(
            provider="groq", model="groq-test-model", api_key="env-secret-key",
            dispatch_policy=MockDispatchPolicy("groq"), quota_ledger=ledger,
            transport=httpx.MockTransport(completion_response(answer_json())),
        )

    async def fake_run_harness(cases, service, output, *, timeout_seconds, repeat):
        assert output is not None
        return 0

    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    monkeypatch.setattr(harness_module, "build_service", authorized)
    monkeypatch.setattr(harness_module, "run_harness", fake_run_harness)
    assert main(["--run-live", "--output", str(tmp_path / "authorized.jsonl")]) == 0


def test_main_refuses_without_run_live_flag():
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_main_fails_closed_before_any_call(tmp_path, monkeypatch):
    monkeypatch.delenv("GENERATION_MODEL", raising=False)
    monkeypatch.delenv("GENERATION_API_KEY", raising=False)
    output = tmp_path / "never-created.jsonl"
    with pytest.raises(SystemExit) as excinfo:
        main(["--run-live", "--output", str(output)])
    assert excinfo.value.code == 2
    assert not output.exists()


def test_main_refuses_to_overwrite_existing_output(tmp_path, monkeypatch):
    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    monkeypatch.setenv("GENERATION_MODEL", "groq-test-model")
    output = tmp_path / "results.jsonl"
    output.write_text("historical\n")
    with pytest.raises(SystemExit) as excinfo:
        main(["--run-live", "--output", str(output)])
    assert excinfo.value.code == 2
    assert output.read_text() == "historical\n"


def test_main_never_accepts_an_api_key_argument(tmp_path, monkeypatch):
    monkeypatch.setenv("GENERATION_API_KEY", "env-secret-key")
    monkeypatch.setenv("GENERATION_MODEL", "groq-test-model")
    with pytest.raises(SystemExit) as excinfo:
        main(["--run-live", "--output", str(tmp_path / "x.jsonl"),
              "--api-key", "attempted-secret"])
    assert excinfo.value.code == 2


@pytest.mark.asyncio
async def test_held_out_expectations_use_exact_citation_sets():
    remote = held_out_cases()[0]
    remote_result = GenerationResult(
        answer="Up to three days [10].", cited_ids=[10],
        abstained=False, abstention_reason=None,
    )
    other_result = GenerationResult(
        answer="Wrong source [11].", cited_ids=[11],
        abstained=False, abstention_reason=None,
    )
    assert _matches(remote, remote_result)
    assert not _matches(remote, other_result)


def test_held_out_unsupported_expectation_is_abstention(tmp_path):
    unsupported = held_out_cases()[1]
    assert unsupported.expected_abstained is True
    assert unsupported.expected_cited_ids == ()
