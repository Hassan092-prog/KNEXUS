"""Offline parser, storage, tokenizer and embedding regressions."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
import stat
import sys

import pytest
from docx import Document as WordDocument
from pydantic import ValidationError

from app.core.config import settings
from app.services.ingestion.chunking import chunk_sections
from app.services.ingestion.embedding import FakeEmbedder, SentenceTransformerEmbedder, validate_embeddings
from app.services.ingestion.errors import DocumentInputError, StorageError
from app.services.ingestion.parsing import (
    ParsedSection,
    detect_source_type,
    parse_uploaded_document,
)
from app.services.ingestion.storage import (
    delete_upload,
    make_storage_key,
    resolve_storage_path,
    write_upload,
)


class CharacterTokenizer:
    """Deterministic test double: one Unicode code point per payload token."""

    model_max_length = 256

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        values = [ord(character) for character in text]
        return [1001, *values, 1002] if add_special_tokens else values

    def decode(
        self,
        token_ids: list[int],
        *,
        skip_special_tokens: bool = True,
        clean_up_tokenization_spaces: bool = False,
    ) -> str:
        return "".join(chr(value) for value in token_ids if value not in {1001, 1002})

    def num_special_tokens_to_add(self, pair: bool = False) -> int:
        return 2

    def build_inputs_with_special_tokens(self, token_ids: list[int]) -> list[int]:
        return [1001, *token_ids, 1002]


def tiny_pdf(text: str = "KNEXUS leave policy") -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    output = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, body in enumerate(objects, start=1):
        offsets.append(len(output))
        output.extend(f"{index} 0 obj\n".encode() + body + b"\nendobj\n")
    xref = len(output)
    output.extend(b"xref\n0 6\n0000000000 65535 f \n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    output.extend(
        f"trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return bytes(output)


def make_docx() -> bytes:
    document = WordDocument()
    document.add_paragraph("Annual leave is twenty days.")
    table = document.add_table(rows=1, cols=2)
    table.cell(0, 0).text = "Policy"
    table.cell(0, 1).text = "Reviewed annually"
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


def test_pdf_and_docx_signature_type_and_text_parsing():
    pdf = tiny_pdf()
    kind, sections = parse_uploaded_document("policy.pdf", "application/pdf", pdf)
    assert kind == "pdf"
    assert sections[0].page == 1
    assert "KNEXUS leave policy" in sections[0].text

    docx = make_docx()
    kind, sections = parse_uploaded_document(
        "policy.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        docx,
    )
    assert kind == "docx"
    assert any("Annual leave" in section.text for section in sections)
    assert any("Reviewed annually" in section.text for section in sections)
    assert all(section.page is None for section in sections)
    assert any(section.source_metadata["block_type"] == "table_row" for section in sections)


@pytest.mark.parametrize(
    ("filename", "content_type", "data"),
    [
        ("policy.txt", "text/plain", b"content"),
        ("policy.pdf", "application/pdf", b"not-a-pdf"),
        ("policy.docx", "application/pdf", b"PK\x03\x04invalid"),
        ("policy.docx", None, b"PK\x03\x04invalid"),
    ],
)
def test_upload_parser_rejects_wrong_type_signature_or_package(
    filename, content_type, data
):
    with pytest.raises(DocumentInputError):
        parse_uploaded_document(filename, content_type, data)


def test_empty_or_over_limit_upload_is_rejected(monkeypatch):
    monkeypatch.setattr(settings, "MAX_UPLOAD_BYTES", 10)
    with pytest.raises(DocumentInputError):
        parse_uploaded_document("policy.pdf", "application/pdf", b"%PDF-" + b"x" * 10)


def test_tokenizer_chunk_limit_counts_special_tokens_and_keeps_32_overlap():
    document_id = __import__("uuid").UUID("00000000-0000-4000-8000-000000000099")
    tokenizer = CharacterTokenizer()
    chunks = chunk_sections(
        document_id,
        [ParsedSection("a" * 500, 7, {"page_number": 7})],
        tokenizer,
    )
    assert [chunk.chunk_index for chunk in chunks] == [0, 1, 2]
    assert all(chunk.token_count <= 240 for chunk in chunks)
    assert chunks[0].content[-32:] == chunks[1].content[:32]
    assert chunks[1].content[-32:] == chunks[2].content[:32]
    assert all(chunk.page == 7 for chunk in chunks)
    assert all(chunk.source_metadata["sections"][0]["page_number"] == 7 for chunk in chunks)
    assert len({chunk.id for chunk in chunks}) == len(chunks)
    assert chunks == chunk_sections(
        document_id,
        [ParsedSection("a" * 500, 7, {"page_number": 7})],
        tokenizer,
    )


def test_chunking_preserves_each_source_section_and_page_boundaries():
    document_id = __import__("uuid").UUID("00000000-0000-4000-8000-000000000098")
    chunks = chunk_sections(
        document_id,
        [
            ParsedSection("first page text", 1, {"page_number": 1}),
            ParsedSection("second page text", 2, {"page_number": 2}),
        ],
        CharacterTokenizer(),
    )
    assert len(chunks) == 1
    assert chunks[0].page is None
    assert [item["page_number"] for item in chunks[0].source_metadata["sections"]] == [1, 2]


def test_sentence_transformer_budget_comes_from_loaded_encoder(monkeypatch):
    from types import SimpleNamespace

    embedder = SentenceTransformerEmbedder("sentence-transformers/all-MiniLM-L6-v2", "revision")
    monkeypatch.setattr(embedder, "_get_model", lambda: SimpleNamespace(max_seq_length=256))
    assert embedder.get_max_input_tokens() == 256

def test_fake_embedder_is_explicit_deterministic_and_384_dimensional():
    embedder = FakeEmbedder()
    first = embedder.embed_texts(["policy text"])
    second = embedder.embed_texts(["policy text"])
    assert first == second
    assert len(first[0]) == 384
    assert validate_embeddings(first, 1) == first
    with pytest.raises(ValueError, match="384 finite"):
        validate_embeddings([[0.0] * 383], 1)
    with pytest.raises(ValueError, match="finite"):
        validate_embeddings([[float("nan")] + [0.0] * 383], 1)


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX file permission bits (0o600/0o700) not enforced on Windows")
def test_storage_uses_generated_private_keys_and_rejects_traversal(
    monkeypatch, tmp_path: Path
):
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", tmp_path / "private")
    key = make_storage_key("docx")
    path = write_upload(key, b"synthetic")
    assert path.parent == (tmp_path / "private").resolve()
    assert path.read_bytes() == b"synthetic"
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700
    assert make_storage_key("docx") != key
    with pytest.raises(StorageError):
        resolve_storage_path("../outside.pdf")
    delete_upload(key)
    assert not path.exists()

from datetime import datetime, timezone
from uuid import UUID

from app.core.demo_identity import build_demo_actor
from app.models import Document, DocumentChunk, Embedding, IngestionJob
from app.services.ingestion.processor import (
    enqueue_document_retry,
    process_document,
    recover_interrupted_jobs,
)


class ProcessorResult:
    def __init__(self, rows):
        self.rows = list(rows)

    def scalar_one_or_none(self):
        return self.rows[0] if self.rows else None

    def scalars(self):
        return self

    def all(self):
        return self.rows


class ProcessorSession:
    def __init__(self, document, job):
        self.document = document
        self.job = job
        self.added = []
        self.statements = []
        self.commits = 0

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, model, identifier):
        if model is Document and self.document.id == identifier:
            return self.document
        return None

    def add(self, row):
        self.added.append(row)
        if isinstance(row, IngestionJob):
            self.job = row

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def execute(self, statement):
        self.statements.append(statement)
        if "ingestion_jobs" in str(statement):
            return ProcessorResult([self.job] if self.job else [])
        if "embeddings" in str(statement) or "document_chunks" in str(statement):
            return ProcessorResult([])
        return ProcessorResult([self.job] if self.job else [])


def processor_rows(status="queued"):
    org_id = UUID("00000000-0000-4000-8000-000000000032")
    user_id = UUID("00000000-0000-4000-8000-000000000031")
    document_id = UUID("00000000-0000-4000-8000-000000000701")
    document = Document(
        id=document_id,
        org_id=org_id,
        uploaded_by=user_id,
        title="Synthetic handbook",
        source_type="docx",
        original_filename="handbook.docx",
        storage_key="a" * 32 + ".docx",
        file_size_bytes=256,
        allowed_roles=["employee"],
        status=status,
        chunk_count=0,
        metadata_json={},
        is_deleted=False,
    )
    job = IngestionJob(
        id=UUID("00000000-0000-4000-8000-000000000702"),
        org_id=org_id,
        document_id=document_id,
        attempt_number=1,
        status=status,
        chunks_processed=0,
        total_chunks=None,
    )
    return document, job


@pytest.mark.asyncio
async def test_processor_persists_processing_chunks_embeddings_and_completion():
    document, job = processor_rows()
    session = ProcessorSession(document, job)
    sections = [ParsedSection("a" * 300, 1, {"page_number": 1})]
    succeeded = await process_document(
        document.id,
        parsed_sections=sections,
        session_factory=lambda: session,
        embedder=FakeEmbedder(),
        tokenizer=CharacterTokenizer(),
    )
    assert succeeded is True
    assert document.status == job.status == "complete"
    assert job.started_at is not None and job.finished_at is not None
    assert job.total_chunks == job.chunks_processed == document.chunk_count == 2
    chunks = [row for row in session.added if isinstance(row, DocumentChunk)]
    embeddings = [row for row in session.added if isinstance(row, Embedding)]
    assert len(chunks) == len(embeddings) == 2
    assert all(len(row.embedding) == 384 for row in embeddings)
    assert all(row.model_name == FakeEmbedder.model_name for row in embeddings)
    assert session.commits >= 5


@pytest.mark.asyncio
async def test_processor_failure_persists_safe_failed_state_and_excludes_partial_data():
    document, job = processor_rows()
    session = ProcessorSession(document, job)

    class InvalidEmbedder:
        model_name = "fake-minilm"
        model_revision = "bad-test"

        def embed_texts(self, texts):
            return [[0.0] * 383]

    succeeded = await process_document(
        document.id,
        parsed_sections=[ParsedSection("text", None, {"paragraph_number": 1})],
        session_factory=lambda: session,
        embedder=InvalidEmbedder(),
        tokenizer=CharacterTokenizer(),
    )
    assert succeeded is False
    assert document.status == job.status == "failed"
    assert job.failure_code == "PROCESSING_FAILED"
    assert job.failure_message and "384" not in job.failure_message
    assert job.finished_at is not None


@pytest.mark.asyncio
async def test_cancelled_processor_records_interruption_and_propagates_cancellation():
    import asyncio
    from threading import Event

    document, job = processor_rows()
    session = ProcessorSession(document, job)
    started = Event()
    release = Event()

    class SlowEmbedder:
        model_name = "fake-minilm"
        model_revision = "slow-test"

        def embed_texts(self, texts):
            started.set()
            release.wait(3)
            return FakeEmbedder().embed_texts(texts)

    task = asyncio.create_task(
        process_document(
            document.id,
            parsed_sections=[ParsedSection("text", None, {"paragraph_number": 1})],
            session_factory=lambda: session,
            embedder=SlowEmbedder(),
            tokenizer=CharacterTokenizer(),
        )
    )
    try:
        assert await asyncio.to_thread(started.wait, 2)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert document.status == job.status == "failed"
        assert job.failure_code == "INTERRUPTED"
        assert "interrupted" in job.failure_message.lower()
    finally:
        release.set()




class LowercaseCharacterTokenizer(CharacterTokenizer):
    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]:
        values = [ord(character) for character in text.lower()]
        return [1001, *values, 1002] if add_special_tokens else values


def test_chunking_preserves_source_text_and_offsets_across_sections():
    from uuid import UUID

    first = "US policy: API key AbC123."
    second = "Cafe" + chr(0x0301) + " costs " + chr(0x20AC) + "20! Punct, yes."
    source = first + chr(10) * 2 + second
    chunks = chunk_sections(
        UUID("00000000-0000-4000-8000-000000000097"),
        [
            ParsedSection(first, 1, {"page_number": 1}),
            ParsedSection(second, 2, {"page_number": 2}),
        ],
        LowercaseCharacterTokenizer(),
        token_limit=55,
        overlap=4,
    )
    assert any(len(chunk.source_metadata["sections"]) == 2 for chunk in chunks)
    assert all(
        source[chunk.source_metadata["char_start"]:chunk.source_metadata["char_end"]]
        == chunk.content
        for chunk in chunks
    )
    assert all(chunk.token_count <= 55 for chunk in chunks)
    assert any("AbC123" in chunk.content for chunk in chunks)
    assert any("US policy" in chunk.content for chunk in chunks)
    phrase = "Cafe" + chr(0x0301) + " costs " + chr(0x20AC) + "20!"
    assert any(phrase in chunk.content for chunk in chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))


def test_chunking_caps_requested_budget_at_actual_model_limit_and_validates_overlap():
    from uuid import UUID

    chunks = chunk_sections(
        UUID("00000000-0000-4000-8000-000000000096"),
        [ParsedSection("word " * 200, None, {})],
        CharacterTokenizer(),
        token_limit=400,
        overlap=32,
        model_max_input_tokens=256,
    )
    assert len(chunks) > 1
    assert all(chunk.token_count <= 256 for chunk in chunks)

    with pytest.raises(ValueError, match="leave no usable chunk budget"):
        chunk_sections(
            UUID("00000000-0000-4000-8000-000000000095"),
            [ParsedSection("text", None, {})],
            CharacterTokenizer(),
            token_limit=34,
            overlap=32,
            model_max_input_tokens=34,
        )


@pytest.mark.asyncio
async def test_tokenizer_loading_does_not_block_event_loop(monkeypatch):
    import asyncio
    import time

    from app.services.ingestion import processor as processor_module

    document, job = processor_rows()
    session = ProcessorSession(document, job)

    def slow_loader(*_args):
        time.sleep(0.12)
        return CharacterTokenizer()

    monkeypatch.setattr(processor_module, "load_embedding_tokenizer", slow_loader)
    task = asyncio.create_task(
        process_document(
            document.id,
            parsed_sections=[ParsedSection("US AbC123", 1, {"page_number": 1})],
            session_factory=lambda: session,
            embedder=FakeEmbedder(),
        )
    )
    ticks = 0

    async def heartbeat():
        nonlocal ticks
        while not task.done():
            ticks += 1
            await asyncio.sleep(0.005)

    succeeded, _ = await asyncio.gather(task, heartbeat())
    assert succeeded is True
    assert ticks >= 5


@pytest.mark.parametrize("abandoned_status", ["queued", "processing"])
@pytest.mark.asyncio
async def test_recovery_fails_abandoned_queued_and_processing_then_allows_retry(
    abandoned_status,
):
    document, job = processor_rows(abandoned_status)
    if abandoned_status == "processing":
        job.started_at = datetime.now(timezone.utc)
    session = ProcessorSession(document, job)

    with pytest.raises(ValueError, match="all ingestion workers are stopped"):
        await recover_interrupted_jobs(lambda: session)
    assert session.statements == []
    assert job.status == document.status == abandoned_status

    recovered = await recover_interrupted_jobs(
        lambda: session, workers_stopped=True
    )
    assert recovered == 1
    assert document.status == job.status == "failed"
    assert job.failure_code == "INTERRUPTED"
    assert job.failure_message and job.failure_message.strip()
    assert job.finished_at is not None

    retry = await enqueue_document_retry(session, build_demo_actor(), document.id)
    assert document.status == "queued"
    assert document.chunk_count == 0
    assert retry.status == "queued" and retry.attempt_number == 2
    assert session.commits == 2
    statements = [str(statement).lower() for statement in session.statements]
    assert any(statement.startswith("delete from embeddings") for statement in statements)
    assert any(statement.startswith("delete from document_chunks") for statement in statements)

def test_zero_overlap_splits_long_source_without_gaps_or_duplicates():
    from uuid import UUID

    source = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" * 8
    chunks = chunk_sections(
        UUID("00000000-0000-4000-8000-000000000094"),
        [ParsedSection(source, None, {"section_name": "one"})],
        CharacterTokenizer(),
        token_limit=16,
        overlap=0,
        model_max_input_tokens=16,
    )

    assert len(chunks) > 1
    spans = [
        (chunk.source_metadata["char_start"], chunk.source_metadata["char_end"])
        for chunk in chunks
    ]
    assert spans[0][0] == 0
    assert spans[-1][1] == len(source)
    assert all(previous[1] == current[0] for previous, current in zip(spans, spans[1:]))
    assert all(chunk.content == source[start:end] for chunk, (start, end) in zip(chunks, spans))
    assert "".join(chunk.content for chunk in chunks) == source
    assert all(chunk.token_count <= 16 for chunk in chunks)


def test_default_chunk_overlap_remains_32_tokens():
    from uuid import UUID

    source = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" * 15
    chunks = chunk_sections(
        UUID("00000000-0000-4000-8000-000000000093"),
        [ParsedSection(source, None, {})],
        CharacterTokenizer(),
    )

    assert len(chunks) > 1
    spans = [
        (chunk.source_metadata["char_start"], chunk.source_metadata["char_end"])
        for chunk in chunks
    ]
    assert spans[0][0] == 0
    assert spans[0][1] - spans[1][0] == 32
    assert all(start < end for start, end in spans)
    assert all(chunk.content == source[start:end] for chunk, (start, end) in zip(chunks, spans))
    assert all(chunk.token_count <= 240 for chunk in chunks)
