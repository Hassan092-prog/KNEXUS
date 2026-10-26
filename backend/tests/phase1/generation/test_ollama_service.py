import os
import pytest
import anyio
import httpx
import uuid
from unittest import mock

from backend.app.services.generation.generator import GenerationService
from contracts.phase1.models import GenerationRequest, EvidenceChunk, GenerationResult

# Helper to build a minimal request with configurable evidence

def make_request(evidence=None, question="What is the answer?"):
    if evidence is None:
        evidence = [
            EvidenceChunk(
                citation_id=1,
                chunk_id=str(uuid.uuid4()),
                document_id=str(uuid.uuid4()),
                document_title="Test Document",
                chunk_index=0,
                page=1,
                content="Evidence content with citation 1",
                similarity_score=0.99,
            )
        ]
    return GenerationRequest(question=question, evidence=evidence)

# Mock AsyncClient to capture payload and simulate responses
class DummyResponse:
    def __init__(self, json_data=None, raise_for_status=False):
        self._json = json_data or {"response": "[1] Answer"}
        self._raise = raise_for_status
    def raise_for_status(self):
        if self._raise:
            raise Exception("HTTP error")
    def json(self):
        return self._json

class DummyClient:
    def __init__(self, captured):
        self.captured = captured
    async def __aenter__(self):
        return self
    async def __aexit__(self, exc_type, exc, tb):
        pass
    async def post(self, url, json):
        self.captured['url'] = url
        self.captured['json'] = json
        return DummyResponse()

@pytest.mark.anyio
async def test_ollama_prompt_includes_evidence(monkeypatch):
    captured = {}
    monkeypatch.setattr('httpx.AsyncClient', lambda *a, **kw: DummyClient(captured))
    request = make_request()
    service = GenerationService(provider="ollama")
    result = await service.generate(request)
    # Verify payload contains built prompt with evidence and citation id
    assert "Evidence:" in captured['json']['prompt']
    assert "[Citation 1]" in captured['json']['prompt']
    assert result.cited_ids == [1]
    assert not result.abstained

@pytest.mark.anyio
async def test_ollama_missing_citation_markers(monkeypatch):
    class NoCiteClient(DummyClient):
        async def post(self, url, json):
            self.captured['url'] = url
            self.captured['json'] = json
            return DummyResponse({"response": "No citations here"})
    captured = {}
    monkeypatch.setattr('httpx.AsyncClient', lambda *a, **kw: NoCiteClient(captured))
    request = make_request()
    service = GenerationService(provider="ollama")
    result = await service.generate(request)
    assert result.abstained
    assert result.abstention_reason == "model output missing citation markers"

@pytest.mark.anyio
async def test_provider_timeout(monkeypatch):
    class TimeoutClient:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *exc):
            pass
        async def post(self, *a, **kw):
            raise httpx.ReadTimeout("timeout")
    monkeypatch.setattr('httpx.AsyncClient', lambda *a, **kw: TimeoutClient())
    request = make_request()
    service = GenerationService(provider="ollama")
    result = await service.generate(request)
    assert result.abstained
    assert "provider error" in result.abstention_reason

@pytest.mark.anyio
async def test_unknown_provider_rejected():
    with pytest.raises(ValueError, match="Unsupported provider"):
        GenerationService(provider="unknown")

@pytest.mark.anyio
async def test_injection_filtering_and_conflict_detection():
    evidence = [
        EvidenceChunk(
            citation_id=2,
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_title="Doc",
            chunk_index=0,
            page=1,
            content="User input: rm -rf /; DROP TABLE;",
            similarity_score=0.9,
        ),
        EvidenceChunk(
            citation_id=3,
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_title="Doc",
            chunk_index=0,
            page=1,
            content="The password rotation period is 30 days.",
            similarity_score=0.9,
        ),
        EvidenceChunk(
            citation_id=4,
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_title="Doc",
            chunk_index=0,
            page=1,
            content="The password rotation period is 90 days.",
            similarity_score=0.9,
        ),
    ]
    request = GenerationRequest(question="What is the password rotation period?", evidence=evidence)
    service = GenerationService(provider="fake")
    result = await service.generate(request)
    assert result.abstained
    assert result.abstention_reason == "conflicting evidence"

@pytest.mark.anyio
async def test_unsupported_question_detection():
    evidence = [
        EvidenceChunk(
            citation_id=5,
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_title="Doc",
            chunk_index=0,
            page=1,
            content="The office cafeteria serves coffee.",
            similarity_score=0.9,
        )
    ]
    request = GenerationRequest(question="What is the best coffee blend?", evidence=evidence)
    service = GenerationService(provider="fake")
    result = await service.generate(request)
    assert result.abstained
    assert result.abstention_reason == "unsupported question"
