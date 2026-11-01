import asyncio
import json

import pytest

from app.schemas import EvidenceChunk, GenerationRequest, GenerationResult
from app.services.generation.errors import ProviderTimeoutError, ProviderUnavailableError
from tests.phase1.generation.live_harness import HarnessCase, _matches, run_harness

class StubService:
    def __init__(self, outcomes, output_path=None):
        self.outcomes = iter(outcomes)
        self.output_path = output_path
        self.calls = 0
        self.lines_seen_at_second_call = None
    async def generate(self, request):
        self.calls += 1
        if self.calls == 2 and self.output_path is not None:
            self.lines_seen_at_second_call = len(self.output_path.read_text().splitlines())
        outcome = next(self.outcomes)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

def make_case(name, *, smoke, abstained=False, cited_ids=()):
    request = GenerationRequest(
        question="What does the synthetic handbook say?",
        evidence=[EvidenceChunk(
            citation_id=1, chunk_id="11111111-1111-4111-8111-111111111111",
            document_id="22222222-2222-4222-8222-222222222222",
            document_title="Synthetic handbook", chunk_index=0, page=1,
            content="Synthetic evidence.", similarity_score=0.9,
        )],
    )
    return HarnessCase(name, request, abstained, tuple(cited_ids), smoke)

def answer(cited=(1,)):
    ids = list(cited)
    markers = " ".join(f"[{i}]" for i in ids)
    return GenerationResult(answer=f"Synthetic answer {markers}.", cited_ids=ids,
                            abstained=False, abstention_reason=None)

def abstention():
    return GenerationResult(answer=None, cited_ids=[], abstained=True,
                            abstention_reason="No supporting evidence.")

@pytest.mark.asyncio
async def test_harness_persists_each_case_before_next_call(tmp_path):
    output = tmp_path / "results.jsonl"
    service = StubService([answer(), abstention(), answer()], output)
    cases = [make_case("supported", smoke=True, cited_ids=(1,)),
             make_case("unsupported", smoke=True, abstained=True),
             make_case("followup", smoke=False, cited_ids=(1,))]
    exit_code = await run_harness(cases, service, output)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert exit_code == 0
    assert service.lines_seen_at_second_call == 1
    assert [row["status"] for row in rows] == ["passed"] * 3
    assert all(row["inference_performed"] for row in rows)
    assert all(isinstance(row["elapsed_seconds"], (int, float)) for row in rows)

@pytest.mark.asyncio
async def test_harness_records_errors_and_skips_full_cases_after_smoke_failure(tmp_path):
    output = tmp_path / "results.jsonl"
    service = StubService([ProviderUnavailableError("unavailable"), abstention()])
    cases = [make_case("supported", smoke=True, cited_ids=(1,)),
             make_case("unsupported", smoke=True, abstained=True),
             make_case("followup", smoke=False, cited_ids=(1,))]
    exit_code = await run_harness(cases, service, output)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert exit_code == 1
    assert rows[0]["status"] == "error"
    assert rows[0]["error_type"] == "ProviderUnavailableError"
    assert rows[1]["status"] == "passed"
    assert rows[2]["status"] == "skipped"
    assert rows[0]["elapsed_seconds"] is not None
    assert rows[1]["elapsed_seconds"] is not None
    assert rows[2]["inference_performed"] is False
    assert rows[2]["elapsed_seconds"] is None
    assert service.calls == 2

@pytest.mark.asyncio
async def test_harness_records_elapsed_time_for_failed_expectation(tmp_path):
    output = tmp_path / "failed.jsonl"
    exit_code = await run_harness(
        [make_case("unexpected_abstention", smoke=True, cited_ids=(1,))],
        StubService([abstention()]), output,
    )
    row = json.loads(output.read_text().splitlines()[0])
    assert exit_code == 1 and row["status"] == "failed"
    assert row["inference_performed"] and row["elapsed_seconds"] >= 0

@pytest.mark.asyncio
async def test_harness_classifies_provider_timeout_and_records_elapsed_time(tmp_path):
    output = tmp_path / "provider-timeout.jsonl"
    exit_code = await run_harness(
        [make_case("provider_timeout", smoke=True, cited_ids=(1,))],
        StubService([ProviderTimeoutError("synthetic provider timeout")]), output,
    )
    row = json.loads(output.read_text().splitlines()[0])
    assert exit_code == 1 and row["status"] == "timeout" and row["passed"] is False
    assert row["inference_performed"] and isinstance(row["elapsed_seconds"], (int, float))

@pytest.mark.asyncio
async def test_harness_classifies_its_own_deadline_timeout(tmp_path):
    output = tmp_path / "deadline.jsonl"
    started = asyncio.Event()
    class BlockingService:
        async def generate(self, request):
            started.set()
            await asyncio.Event().wait()
    exit_code = await run_harness(
        [make_case("deadline", smoke=True, cited_ids=(1,))],
        BlockingService(), output, timeout_seconds=0.01,
    )
    row = json.loads(output.read_text().splitlines()[0])
    assert exit_code == 1 and started.is_set() and row["status"] == "timeout"
    assert row["inference_performed"] and row["elapsed_seconds"] >= 0

@pytest.mark.asyncio
async def test_harness_preserves_external_cancellation(tmp_path):
    started = asyncio.Event()
    class BlockingService:
        async def generate(self, request):
            started.set()
            await asyncio.Event().wait()
    task = asyncio.create_task(run_harness(
        [make_case("cancelled", smoke=True, cited_ids=(1,))],
        BlockingService(), tmp_path / "cancelled.jsonl", timeout_seconds=5.0,
    ))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

@pytest.mark.asyncio
async def test_harness_rejects_empty_case_list(tmp_path):
    with pytest.raises(ValueError, match="At least one harness case"):
        await run_harness([], StubService([]), tmp_path / "empty.jsonl")


def test_harness_requires_exact_citation_set():
    case = make_case("citation_exactness", smoke=True, cited_ids=(6,))
    result = GenerationResult(answer="Answer cites both [5] and [6].", cited_ids=[5, 6],
                              abstained=False, abstention_reason=None)
    assert not _matches(case, result)

@pytest.mark.parametrize("timeout", [0.0, -1.0, float("nan"), float("inf"), -float("inf")])
@pytest.mark.asyncio
async def test_harness_timeout_must_be_finite_and_positive(tmp_path, timeout):
    with pytest.raises(ValueError, match="finite and positive"):
        await run_harness([make_case("supported", smoke=True, cited_ids=(1,))],
                          StubService([answer()]), tmp_path / "invalid.jsonl",
                          timeout_seconds=timeout)
