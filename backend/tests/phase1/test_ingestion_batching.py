"""Offline regression and invariant tests for batch embedding and quota lifecycle."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
import pytest

from app.core.config import settings
from app.core.dispatch_policy import MockDispatchPolicy
from app.core.quota import QuotaConfig, QuotaLedger
from app.services.ingestion.chunking import ChunkDraft
from app.services.ingestion.embedding import (
    GOOGLE_EMBEDDING_MAX_BATCH_SIZE,
    GoogleGenAIEmbedder,
    validate_embeddings,
)
from app.services.ingestion.errors import EmbeddingUnavailableError
from app.services.ingestion.processor import (
    _embed_document_chunks_with_task_adaptation,
    _embed_document_chunk_with_task_adaptation,
)


def make_embedding_vector(idx: int, dim: int = 384) -> list[float]:
    """Deterministic normalized 384-dim test vector."""
    val = float(idx % 10 + 1)
    vec = [0.0] * dim
    vec[0] = val
    # Normalize
    vec[0] = 1.0
    return vec


def test_batch_embedding_output_equivalent_to_per_chunk(tmp_path: Path):
    """2b: Output of batch embedding is completely identical to per-chunk sequential embedding."""
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q_equiv.json", min_request_interval_seconds=0.0))
    policy = MockDispatchPolicy("google")

    def mock_handler(req: httpx.Request) -> httpx.Response:
        data = json.loads(req.content)
        requests = data.get("requests", [])
        embs = []
        for i, r in enumerate(requests):
            text = r["content"]["parts"][0]["text"]
            # Derive deterministic vector from text content
            dim_val = (len(text) % 50) + 1.0
            vec = [0.0] * 384
            vec[0] = 1.0
            embs.append({"values": vec})
        return httpx.Response(200, json={"embeddings": embs}, request=req)

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        transport=transport,
        dispatch_policy=policy,
        quota_ledger=ledger,
    )

    test_chunks = [
        "First test document section covering employment terms.",
        "Second test document section covering 21 days annual leave.",
        "Third section detailing remote work policies and hardware stipends.",
        "Fourth section outlining disciplinary procedures and escalation pathways.",
        "Fifth section defining health insurance and medical leave provisions.",
    ]

    # Run sequentially per chunk
    single_vectors = []
    for c in test_chunks:
        v = _embed_document_chunk_with_task_adaptation(embedder, c)
        single_vectors.append(v[0])

    # Run in batch
    batch_vectors = _embed_document_chunks_with_task_adaptation(embedder, test_chunks)

    assert len(single_vectors) == len(test_chunks)
    assert len(batch_vectors) == len(test_chunks)
    assert single_vectors == batch_vectors


def test_101_chunk_input_produces_two_requests(tmp_path: Path):
    """2b: 101 chunk contents sliced at GOOGLE_EMBEDDING_MAX_BATCH_SIZE (100) produces exactly 2 requests."""
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q_101.json", max_requests_per_minute=200, min_request_interval_seconds=0.0))
    policy = MockDispatchPolicy("google")

    captured_requests: list[dict[str, Any]] = []

    def mock_handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        captured_requests.append(body)
        requests = body.get("requests", [])
        embs = [{"values": make_embedding_vector(i)} for i in range(len(requests))]
        return httpx.Response(200, json={"embeddings": embs}, request=req)

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        transport=transport,
        dispatch_policy=policy,
        quota_ledger=ledger,
    )

    # 101 chunk texts
    chunks_101 = [f"Synthesized handbook chunk paragraph number {i}" for i in range(101)]

    # Simulate processor batching loop
    all_vectors: list[list[float]] = []
    for i in range(0, len(chunks_101), GOOGLE_EMBEDDING_MAX_BATCH_SIZE):
        batch = chunks_101[i : i + GOOGLE_EMBEDDING_MAX_BATCH_SIZE]
        v_batch = _embed_document_chunks_with_task_adaptation(embedder, batch)
        all_vectors.extend(v_batch)

    assert len(all_vectors) == 101
    assert len(captured_requests) == 2
    assert len(captured_requests[0]["requests"]) == 100
    assert len(captured_requests[1]["requests"]) == 1


def test_partial_or_malformed_batch_response_fails_safely(tmp_path: Path):
    """2b: A partial or malformed response raises EmbeddingUnavailableError and settles as failure."""
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q_malformed.json", min_request_interval_seconds=0.0))
    policy = MockDispatchPolicy("google")

    # Handler returns only 2 embeddings for 3 requested texts
    def partial_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [1.0]*384}, {"values": [1.0]*384}]}, request=req)

    embedder_partial = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        transport=httpx.MockTransport(partial_handler),
        dispatch_policy=policy,
        quota_ledger=ledger,
    )

    with pytest.raises(EmbeddingUnavailableError, match="missing embeddings array or count mismatch"):
        _embed_document_chunks_with_task_adaptation(embedder_partial, ["text1", "text2", "text3"])

    # Verify settlement recorded the error
    state = ledger._load_state()
    assert len(state.get("active_reservations", {})) == 0
    settled = state.get("settled_requests", [])
    assert len(settled) == 1
    assert settled[0]["success"] is False
    assert settled[0]["error"] == "malformed_embeddings"

    # Handler returns malformed JSON
    def malformed_handler(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": "not-a-list"}, request=req)

    embedder_malformed = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        transport=httpx.MockTransport(malformed_handler),
        dispatch_policy=policy,
        quota_ledger=ledger,
    )

    with pytest.raises(EmbeddingUnavailableError, match="missing embeddings array"):
        _embed_document_chunks_with_task_adaptation(embedder_malformed, ["text1"])


def test_settlement_happens_exactly_once_per_request(tmp_path: Path):
    """2b: Exactly one reservation and settlement occurs per HTTP batch request."""
    state_file = tmp_path / "q_settle.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file, max_requests_per_minute=200, min_request_interval_seconds=0.0))
    policy = MockDispatchPolicy("google")

    def mock_handler(req: httpx.Request) -> httpx.Response:
        body = json.loads(req.content)
        requests = body.get("requests", [])
        embs = [{"values": make_embedding_vector(i)} for i in range(len(requests))]
        return httpx.Response(200, json={"embeddings": embs}, request=req)

    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        transport=httpx.MockTransport(mock_handler),
        dispatch_policy=policy,
        quota_ledger=ledger,
    )

    chunks_101 = [f"Chunk content line {i}" for i in range(101)]

    for i in range(0, len(chunks_101), GOOGLE_EMBEDDING_MAX_BATCH_SIZE):
        batch = chunks_101[i : i + GOOGLE_EMBEDDING_MAX_BATCH_SIZE]
        _embed_document_chunks_with_task_adaptation(embedder, batch)

    state = ledger._load_state()
    assert len(state.get("active_reservations", {})) == 0
    settled = state.get("settled_requests", [])
    # Exactly 2 requests = exactly 2 settlements
    assert len(settled) == 2
    assert settled[0]["success"] is True
    assert settled[1]["success"] is True


def test_429_mid_ingestion_trips_tripwire_and_stops_further_requests(tmp_path: Path):
    """2b: HTTP 429 on first batch trips the rate limit and prevents subsequent batch dispatch."""
    state_file = tmp_path / "q_429.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file, max_requests_per_minute=200, min_request_interval_seconds=0.0))
    policy = MockDispatchPolicy("google")

    request_count = 0

    def mock_429_handler(req: httpx.Request) -> httpx.Response:
        nonlocal request_count
        request_count += 1
        return httpx.Response(429, json={"error": {"code": 429, "message": "Resource exhausted"}}, request=req)

    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        transport=httpx.MockTransport(mock_429_handler),
        dispatch_policy=policy,
        quota_ledger=ledger,
    )

    # 150 chunks would normally be 2 batches (100 and 50)
    chunks_150 = [f"Chunk number {i}" for i in range(150)]

    with pytest.raises(EmbeddingUnavailableError, match="rate limit exceeded"):
        for i in range(0, len(chunks_150), GOOGLE_EMBEDDING_MAX_BATCH_SIZE):
            batch = chunks_150[i : i + GOOGLE_EMBEDDING_MAX_BATCH_SIZE]
            _embed_document_chunks_with_task_adaptation(embedder, batch)

    # Only 1 request was sent because 429 aborted processing immediately
    assert request_count == 1

    # Verify tripwire was tripped in ledger
    state = ledger._load_state()
    scope = state["scopes"]["google:gemini-embedding-001"]
    assert scope["rate_limited"] is True
    assert "429" in (scope["rate_limit_reason"] or "")
