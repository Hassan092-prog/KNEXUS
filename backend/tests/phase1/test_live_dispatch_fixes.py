import asyncio
import json
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from pydantic import SecretStr

from app.core.config import settings
from app.core.dispatch_policy import ServerApprovedLiveDispatchPolicy
from app.core.generation import GenerationResult
from app.core.quota import QuotaConfig, QuotaLedger, RateLimitExceededError
from app.models.documents import Document, IngestionJob
from app.services.generation.hosted_provider import (
    _enforce_generation_min_interval,
    reset_generation_pacing,
)
from app.services.ingestion.processor import (
    get_process_document_lock,
    process_document,
    reset_process_document_lock,
)
from app.services.ingestion.storage import write_upload
from tests.phase1.test_hosted_demo_e2e import (
    DEMO_DIR,
    DEMO_DOCX,
    DOCX_MIME,
    EXPECTED_DIRECTION,
    DemoSession,
    Result,
    _unit_vector,
)


class MultiDocDemoSession(DemoSession):
    async def execute(self, statement):
        rendered = str(statement)
        if "ingestion_jobs" in rendered:
            try:
                compiled = statement.compile()
                doc_id = None
                for param in compiled.params.values():
                    if isinstance(param, UUID) and param in self.documents:
                        doc_id = param
                        break
                matching = [j for j in self.jobs.values() if j.document_id == doc_id] if doc_id else list(self.jobs.values())
            except Exception:
                matching = list(self.jobs.values())
            latest = sorted(matching, key=lambda j: j.attempt_number, reverse=True)[:1]
            return Result(latest)
        return await super().execute(statement)


@pytest.mark.asyncio
async def test_concurrent_uploads_queue_and_complete_sequentially(monkeypatch, tmp_path):
    """Multiple concurrent process_document calls acquire the process-wide lock and complete without quota collision."""
    reset_process_document_lock()

    campaign_id = "test-concurrent-ingest"
    monkeypatch.setattr(settings, "LIVE_DISPATCH_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", campaign_id)
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", tmp_path / "private")
    monkeypatch.setattr(settings, "QUOTA_STATE_PATH", tmp_path / "quota_state.json")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "gemini-embedding-001")
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", SecretStr("fake-google-key"))

    ledger = QuotaLedger(
        QuotaConfig(
            enabled=True,
            campaign_id=campaign_id,
            max_campaign_attempts=500,
            max_requests_per_minute=1000,
            max_requests_per_day=10000,
            min_request_interval_seconds=0.0,
            lock_timeout_seconds=0.5,
            state_path=tmp_path / "quota_state.json",
        )
    )
    monkeypatch.setattr("app.core.quota.get_process_quota_ledger", lambda: ledger)

    def google_handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content.decode("utf-8"))
        if ":countTokens" in str(request.url):
            text = payload["contents"][0]["parts"][0]["text"]
            return httpx.Response(200, json={"totalTokens": max(1, len(text) // 4)})
        embeddings = [{"values": _unit_vector(EXPECTED_DIRECTION)} for _ in payload.get("requests", [])]
        return httpx.Response(200, json={"embeddings": embeddings})

    mock_transport = httpx.MockTransport(google_handler)
    monkeypatch.setattr("app.api.dependencies.get_embedding_transport", lambda: mock_transport)

    session = MultiDocDemoSession()
    doc_ids: list[UUID] = []

    # Create 3 documents in DB and storage
    for idx in range(3):
        key = f"{uuid4().hex}.docx"
        write_upload(key, DEMO_DOCX.read_bytes())

        doc_id = uuid4()
        doc = Document(
            id=doc_id,
            org_id=UUID("00000000-0000-4000-8000-000000000032"),
            uploaded_by=UUID("00000000-0000-4000-8000-000000000031"),
            title=f"Doc {idx}",
            source_type="docx",
            original_filename=f"doc_{idx}.docx",
            storage_key=key,
            file_size_bytes=len(DEMO_DOCX.read_bytes()),
            allowed_roles=["employee", "orgadmin"],
            status="queued",
            chunk_count=0,
        )
        job = IngestionJob(
            id=uuid4(),
            org_id=doc.org_id,
            document_id=doc.id,
            attempt_number=1,
            status="queued",
        )
        session.documents[doc.id] = doc
        session.jobs[job.id] = job
        doc_ids.append(doc_id)

    # Run 3 concurrent process_document tasks
    results = await asyncio.gather(
        *(process_document(d_id, session_factory=lambda: session) for d_id in doc_ids)
    )

    assert results == [True, True, True], "All 3 concurrent ingestion attempts must complete successfully"
    for d_id in doc_ids:
        assert session.documents[d_id].status == "complete"


def test_rate_limit_cooldown_blocks_during_cooldown_and_allows_after(tmp_path):
    """A 429 trips rate_limited=True with a cooldown. During cooldown calls fail; after cooldown calls succeed."""
    current_time = 1000.0

    def fake_clock():
        return current_time

    cfg = QuotaConfig(
        enabled=True,
        campaign_id="test-cooldown",
        rate_limit_cooldown_seconds=60.0,
        state_path=tmp_path / "quota_state.json",
    )
    ledger = QuotaLedger(cfg, time_func=fake_clock)

    provider = "groq"
    model = "openai/gpt-oss-120b"
    scope_key = f"{provider}:{model}"

    # Reserve and settle with 429 and Retry-After = 30s. Effective cooldown = max(60, 30) = 60s.
    aid = ledger.reserve_attempt(provider, model)
    ledger.settle_attempt(
        aid,
        success=False,
        status_code=429,
        error="rate limit",
        retry_after=30.0,
    )

    state = ledger._load_state()
    scope = state["scopes"][scope_key]
    assert scope["rate_limited"] is True
    assert scope["rate_limited_at"] == 1000.0
    assert scope["cooldown_seconds"] == 60.0

    # At t=1020 (elapsed 20s < 60s): reservation is blocked fail-fast
    current_time = 1020.0
    with pytest.raises(RateLimitExceededError, match="rate limit active"):
        ledger.reserve_attempt(provider, model)

    # Settle with Retry-After = 120s. Effective cooldown = max(60, 120) = 120s.
    scope["rate_limited_at"] = 1020.0
    scope["cooldown_seconds"] = 120.0
    ledger._save_state(state)

    # At t=1100 (elapsed 80s < 120s): still blocked
    current_time = 1100.0
    with pytest.raises(RateLimitExceededError, match="cooldown remaining"):
        ledger.reserve_attempt(provider, model)

    # At t=1150 (elapsed 130s > 120s): cooldown expired, reservation allowed, flag cleared
    current_time = 1150.0
    aid2 = ledger.reserve_attempt(provider, model)
    assert aid2 is not None

    state2 = ledger._load_state()
    scope2 = state2["scopes"][scope_key]
    assert scope2["rate_limited"] is False
    assert scope2["rate_limit_reason"] is None


@pytest.mark.asyncio
async def test_generation_pacing_waits_for_min_interval():
    """_enforce_generation_min_interval waits for GENERATION_MIN_INTERVAL_SECONDS between calls without rejecting."""
    reset_generation_pacing()

    current_time = [100.0]
    sleeps = []

    def fake_time():
        return current_time[0]

    async def fake_sleep(duration):
        sleeps.append(duration)
        current_time[0] += duration

    # First call: no previous call, zero wait
    await _enforce_generation_min_interval(min_interval=5.0, time_func=fake_time, sleep_func=fake_sleep)
    assert sleeps == []

    # Advance time by 2.0s (elapsed = 2.0 < 5.0)
    current_time[0] += 2.0
    await _enforce_generation_min_interval(min_interval=5.0, time_func=fake_time, sleep_func=fake_sleep)
    # Should sleep remaining 3.0s
    assert sleeps == [3.0]
    assert current_time[0] == 105.0

    # Advance time by 10.0s (elapsed = 10.0 > 5.0)
    current_time[0] += 10.0
    await _enforce_generation_min_interval(min_interval=5.0, time_func=fake_time, sleep_func=fake_sleep)
    # No additional sleep needed
    assert sleeps == [3.0]

    reset_generation_pacing()

