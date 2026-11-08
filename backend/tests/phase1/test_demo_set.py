"""Offline Phase 1 demo corpus and question-set checks.

The demo fixtures in ``backend/tests/fixtures/demo/`` were converted offline
(single conversion pass, temp clone deleted afterwards) from five fictional
test files of Hassan's enterprise-knowledge-bot repository. All persons and
companies are fictional (Acme); the selected files contain no real-looking
emails, phone numbers or personal IDs. The roster is manager-and-above only.

These tests exercise only the offline ingestion boundary: DOCX parsing and
token chunking with the existing chunker under the default local embedding
settings. The local MiniLM tokenizer loads from the local cache only
(``load_embedding_tokenizer`` never contacts the model hub), and no database,
network, or provider call is involved; the module is not marked ``db``.
"""
import json
import uuid as uuid_module
from pathlib import Path
from functools import lru_cache

import pytest

from app.core.config import settings
from app.services.ingestion.chunking import load_embedding_tokenizer
from app.services.ingestion.parsing import parse_uploaded_document

DEMOS_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "demo"

VALID_ROLES = {"employee", "manager", "orgadmin", "superadmin"}


def _load_json(name: str):
    return json.loads((DEMOS_DIR / name).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _parsed_and_chunked():
    """Parse and chunk every manifest document once, offline (module cache)."""
    from app.services.ingestion.chunking import chunk_sections

    tokenizer = load_embedding_tokenizer(
        settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_MODEL_REVISION
    )
    cache = {}
    for entry in _load_json("manifest.json")["documents"]:
        data = (DEMOS_DIR / entry["filename"]).read_bytes()
        source_type, sections = parse_uploaded_document(entry["filename"], None, data)
        chunks = chunk_sections(
            uuid_module.uuid4(),
            sections,
            tokenizer,
            token_limit=settings.CHUNK_TOKEN_LIMIT,
            overlap=settings.CHUNK_TOKEN_OVERLAP,
            model_max_input_tokens=settings.EMBEDDING_MAX_INPUT_TOKENS,
        )
        cache[entry["filename"]] = (source_type, sections, chunks)
    return cache


@pytest.fixture(scope="module")
def manifest():
    return _load_json("manifest.json")


@pytest.fixture(scope="module")
def questions():
    return _load_json("questions.json")["questions"]


def test_demo_manifest_files_exist_and_parse(manifest):
    assert len(manifest["documents"]) == 5
    named = {entry["filename"] for entry in manifest["documents"]}
    assert len(named) == 5
    for entry in manifest["documents"]:
        path = DEMOS_DIR / entry["filename"]
        assert path.exists()
        assert path.stat().st_size < 10 * 1024 * 1024
        assert path.read_bytes()[:2] == b"PK"  # real DOCX zip archive
        source_type, sections = parse_uploaded_document(entry["filename"], None, path.read_bytes())
        assert source_type == "docx"
        assert sections and all(section.text.strip() for section in sections)
        assert entry["title"].strip()
        set_roles = set(entry["allowed_roles"])
        assert set_roles <= VALID_ROLES and set_roles
        if entry["filename"] != "demo_employee_roster.docx":
            assert "employee" in set_roles
        else:
            assert "employee" not in set_roles  # roster is manager-and-above only


def test_demo_files_chunk_offline_with_existing_chunker(manifest, monkeypatch):
    import socket

    # Guard the offline guarantee: any outbound socket attempt fails the test.
    def _fail(*args, **kwargs):  # pragma: no cover - defensive
        raise AssertionError("demo corpus chunking must not touch the network")

    monkeypatch.setattr(socket, "create_connection", _fail)
    monkeypatch.setattr(socket.socket, "connect", _fail)

    cache = _parsed_and_chunked()
    for entry in manifest["documents"]:
        source_type, sections, chunks = cache[entry["filename"]]
        assert source_type == "docx"
        assert chunks, entry["filename"]
        for chunk in chunks:
            assert chunk.content.strip()
            assert chunk.token_count > 0


def test_every_expected_fact_appears_in_a_chunk_of_expected_source(manifest, questions):
    cache = _parsed_and_chunked()
    for question in questions:
        if question["expected"] != "answer":
            continue
        source = question["expected_source"]
        fact = question["expected_fact"]
        assert source is not None and fact is not None, question["id"]
        assert source in {entry["filename"] for entry in manifest["documents"]}
        _, _, chunks = cache[source]
        hits = [chunk.chunk_index for chunk in chunks if fact in chunk.content]
        assert hits, f"{fact!r} missing from every chunk of {source} (question {question['id']})"


def _runner_module():
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "run_demo_for_corpus", Path(__file__).resolve().parents[2] / "scripts" / "run_demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_every_expected_fact_any_variant_is_grounded_in_source_chunks(manifest, questions):
    """No invented alternatives: every expected_fact_any phrasing must normalize
    into the text of some chunk of the question's expected source document."""
    runner = _runner_module()
    cache = _parsed_and_chunked()
    answerable = [question for question in questions if question["expected"] == "answer"]
    assert answerable, "demo set must contain answerable cases"
    checked_variants = 0
    for question in answerable:
        variants = question.get("expected_fact_any") or []
        assert variants, f"{question['id']} must list accepted phrasings"
        source = question["expected_source"]
        _, _, chunks = cache[source]
        chunk_texts = [chunk.content for chunk in chunks]
        # The exact fact is always part of the accepted set.
        assert question["expected_fact"] in variants, question["id"]
        for variant in variants:
            normalized_variant = runner.normalize_text(variant)
            assert normalized_variant, f"{question['id']}: empty normalization for {variant!r}"
            grounded = any(normalized_variant in runner.normalize_text(text) for text in chunk_texts)
            assert grounded, (
                f"{question['id']}: expected_fact_any entry {variant!r} is not grounded "
                f"in any chunk of {source}"
            )
            checked_variants += 1
    assert checked_variants >= len(answerable)


def test_expected_fact_any_consistency_fields(questions):
    for question in questions:
        if question["expected"] == "abstain":
            assert question.get("expected_fact_any") in (None, []), question["id"]
            continue
        assert question.get("expected_fact_any"), question["id"]
        variants = question["expected_fact_any"]
        assert len(variants) == len(set(variants)), question["id"]
        assert all(isinstance(variant, str) and variant.strip() for variant in variants)


def test_demo_questions_are_consistent(questions):
    ids = [question["id"] for question in questions]
    assert len(questions) == 12 and len(ids) == len(set(ids))
    answerable = [question for question in questions if question["expected"] == "answer"]
    role_denied = [question for question in questions if question["expected"] == "abstain"
                   and question["expected_source"] is not None]
    out_of_corpus = [question for question in questions if question["expected"] == "abstain"
                     and question["expected_source"] is None]
    assert len(answerable) == 8 and len(role_denied) == 2 and len(out_of_corpus) == 2
    for question in questions:
        assert question["actor_role"] in VALID_ROLES
        assert question["expected"] in {"answer", "abstain"}
        if question["expected"] == "abstain":
            assert question["expected_fact"] is None
        assert all(part.strip() for part in (question["id"], question["question"]))
    # Role-denied cases: an employee asks about roster (manager-only) data.
    for question in role_denied:
        assert question["actor_role"] == "employee"
        assert question["expected_source"] == "demo_employee_roster.docx"
