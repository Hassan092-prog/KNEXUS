"""Offline tests for the Phase 1 demo runner (backend/scripts/run_demo.py).

Everything is exercised against ``httpx.MockTransport``: no real network, no DB,
no provider calls. The scoring rules under test: answer cases pass only when the
expected fact is in the answer AND a citation points at the expected source;
abstain cases pass on an abstention; HTTP/provider failures are ``error`` rows
and never count as a pass.
"""
import importlib.util
import json
import socket
import uuid as uuid_module
from pathlib import Path

import httpx
import pytest

_REPO_BACKEND = Path(__file__).resolve().parents[2]
_SPEC = importlib.util.spec_from_file_location("run_demo", _REPO_BACKEND / "scripts" / "run_demo.py")
run_demo_module = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(run_demo_module)

DEMO_DIR = _REPO_BACKEND / "tests" / "fixtures" / "demo"


def answer_case() -> dict:
    return {
        "id": "case_answer",
        "question": "What is on the record?",
        "actor_role": "employee",
        "expected": "answer",
        "expected_source": "demo.docx",
        "expected_fact": "42 widgets",
    }


def citation(document_id: uuid_module.UUID, title: str = "demo.docx") -> dict:
    return {
        "document_id": str(document_id),
        "document_title": title,
        "id": 1,
        "chunk_id": str(uuid_module.uuid4()),
        "chunk_index": 0,
        "page": 1,
        "excerpt": "42 widgets",
        "similarity_score": 0.9,
    }


def score(payload: dict, question: dict | None = None, doc_ids: dict | None = None) -> tuple[str, str]:
    doc_ids = doc_ids if doc_ids is not None else {"demo.docx": str(DOC_ID)}
    return run_demo_module.score_case(question or answer_case(), payload, doc_ids, {"demo.docx": "Demo Title"})


DOC_ID = uuid_module.uuid4()


def test_scoring_answer_pass_fail() -> None:
    # pass: fact in answer AND citation points at the expected source.
    payload = {"abstained": False, "answer": "... 42 widgets shipped", "citations": [citation(DOC_ID)]}
    assert score(payload)[0] == "pass"
    # fail: fact missing from the answer.
    payload_no_fact = {"abstained": False, "answer": "unrelated text", "citations": [citation(DOC_ID)]}
    assert score(payload_no_fact)[0] == "fail"
    # fail: citation does not point at the expected source.
    other = uuid_module.uuid4()
    payload_wrong_citation = {
        "abstained": False,
        "answer": "42 widgets shipped",
        "citations": [citation(other, title="other.docx")],
    }
    assert score(payload_wrong_citation)[0] == "fail"


def test_scoring_abstain_pass_and_fail() -> None:
    abstain_case = {
        "id": "case_abstain",
        "question": "Is it hidden?",
        "actor_role": "employee",
        "expected": "abstain",
        "expected_source": None,
        "expected_fact": None,
    }
    abstained = {"abstained": True, "answer": None, "citations": [],
                 "abstention_reason": "unsupported question"}
    status, reason = score(abstained, question=abstain_case)
    assert status == "pass" and "abstained" in reason
    answered = {
        "abstained": False,
        "answer": "a speculative answer",
        "citations": [citation(DOC_ID)],
    }
    assert score(answered, question=abstain_case)[0] == "fail"
    # An abstention on an expected-answer case also fails.
    assert score(abstained)[0] == "fail"


def test_provider_errors_are_error_rows_never_pass(httpx_assert_no_network) -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(503, json={"code": "PROVIDER_UNAVAILABLE", "detail": "down"})

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        row = run_demo_module.run_query_case(client, answer_case(), {"demo.docx": str(DOC_ID)}, {"demo.docx": "t"})
    assert row["status"] == "error" and row["status"] != "pass"
    assert "PROVIDER_UNAVAILABLE" in row["reason"]
    # Transport-level failures (connection refused) are also error rows.
    def broken_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    with httpx.Client(transport=httpx.MockTransport(broken_handler), base_url="http://test") as client:
        row = run_demo_module.run_query_case(client, answer_case(), {}, {})
    assert row["status"] == "error" and row["status"] != "pass"
    assert calls  # the first handler was actually reached
    # A 200 body missing the Abstained/Answer contract shape still errors, never passes.
    def malformed_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    with httpx.Client(transport=httpx.MockTransport(malformed_handler), base_url="http://test") as client:
        row = run_demo_module.run_query_case(client, answer_case(), {}, {})
    assert row["status"] == "error"


def test_upload_sends_repeated_allowed_roles_fields() -> None:
    manifest = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))["documents"]
    roster = next(entry for entry in manifest if entry["filename"] == "demo_employee_roster.docx")
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["content"] = request.content
        return httpx.Response(
            202,
            json={
                "document_id": str(DOC_ID),
                "task_id": str(uuid_module.uuid4()),
                "status": "queued",
                "message": "queued",
            },
        )

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        mapping = run_demo_module.upload_documents(client, [roster], fixtures_dir=DEMO_DIR)

    body = seen["content"]
    assert body.count(b'name="allowed_roles"') == len(roster["allowed_roles"]) == 3
    for role in roster["allowed_roles"]:
        assert role.encode() in body
    # No client-invented 'employee' role value anywhere in the form fields.
    assert b'\r\n\r\nemployee' not in body
    assert mapping["demo_employee_roster.docx"] == DOC_ID


def test_upload_fails_loudly_on_error_status() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(413, json={"code": "FILE_TOO_LARGE", "detail": "too big"})

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        with pytest.raises(RuntimeError, match="upload failed"):
            run_demo_module.upload_documents(
                client,
                [{"filename": "demo_security_policy.docx", "title": "t",
                  "allowed_roles": ["manager"]}],
                fixtures_dir=DEMO_DIR,
            )


def test_polling_stops_on_failed() -> None:
    calls: list[str] = []
    responses = ["queued", "processing", "failed"]

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        state = responses[min(len(calls) - 1, len(responses) - 1)]
        if state == "failed":
            return httpx.Response(200, json={
                "document_id": str(DOC_ID), "status": "failed", "chunks_processed": 0,
                "total_chunks": 4, "progress_percent": 0,
                "failure_code": "PARSE_FAILED", "failure_message": "bad docx",
            })
        return httpx.Response(200, json={
            "document_id": str(DOC_ID), "status": state, "chunks_processed": 0,
            "total_chunks": 4, "progress_percent": 0,
            "failure_code": None, "failure_message": None,
        })

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        state, detail = run_demo_module.poll_status(
            client, DOC_ID, poll_interval=0.0, status_timeout=30.0
        )
    assert state == "failed" and "PARSE_FAILED" in detail
    assert len(calls) == 3  # stopped right after the terminal 'failed' state


def test_polling_stops_on_timeout() -> None:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={
            "document_id": str(DOC_ID), "status": "processing", "chunks_processed": 0,
            "total_chunks": None, "progress_percent": 0,
            "failure_code": None, "failure_message": None,
        })

    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        state, detail = run_demo_module.poll_status(
            client, DOC_ID, poll_interval=0.0, status_timeout=0.05
        )
    assert state == "timeout" and "bound" in detail
    assert len(calls) >= 1  # attempted at least once before the deadline


@pytest.fixture()
def httpx_assert_no_network(monkeypatch):
    def _fail(*args, **kwargs):
        raise AssertionError("demo runner tests must not open real sockets")

    monkeypatch.setattr(socket, "create_connection", _fail)
    monkeypatch.setattr(socket.socket, "connect", _fail)


def _demo_payload(question_fact: str, doc_id: uuid_module.UUID, abstained: bool = False) -> httpx.Response:
    if abstained:
        return httpx.Response(200, json={
            "answer": None, "citations": [], "abstained": True,
            "abstention_reason": "No sufficiently relevant accessible evidence was found.",
            "session_id": str(uuid_module.uuid4()),
            "meta": {"retrieval_time_ms": 1.0, "generation_time_ms": 0.0, "model": "fake"},
        })
    return httpx.Response(200, json={
        "answer": f"The record states {question_fact}.",
        "citations": [citation(doc_id)], "abstained": False,
        "abstention_reason": None, "session_id": str(uuid_module.uuid4()),
        "meta": {"retrieval_time_ms": 1.0, "generation_time_ms": 1.0, "model": "fake"},
    })


def test_run_demo_end_to_end_offline(httpx_assert_no_network, tmp_path: Path) -> None:
    """Full loop offline (--upload): 5 uploads -> complete -> employee questions -> JSONL."""
    interactions: dict[str, int] = {"allowed_roles_fields": 0, "queries": 0}
    questions = json.loads((DEMO_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
    manifest_docs = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))["documents"]
    doc_ids = {entry["filename"]: uuid_module.uuid4() for entry in manifest_docs}
    case_by_question = {
        question["question"]: question
        for question in questions
        if question["actor_role"] == "employee"
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == run_demo_module.UPLOAD_PATH:
            interactions["allowed_roles_fields"] += request.content.count(b'name="allowed_roles"')
            name = request.content.split(b'name="file"')[1].split(b'filename="')[1].split(b'"')[0].decode()
            return httpx.Response(202, json={
                "document_id": str(doc_ids[name]), "task_id": str(uuid_module.uuid4()),
                "status": "queued", "message": "queued",
            })
        if "/status" in request.url.path:
            return httpx.Response(200, json={
                "document_id": "0" * 32, "status": "complete", "chunks_processed": 4,
                "total_chunks": 4, "progress_percent": 100,
                "failure_code": None, "failure_message": None,
            })
        if request.url.path == run_demo_module.QUERY_PATH:
            interactions["queries"] += 1
            case = case_by_question[json.loads(request.content)["question"]]
            abstained = case["expected"] == "abstain"
            doc_id = doc_ids[case["expected_source"]] if case["expected_source"] else uuid_module.uuid4()
            return _demo_payload(case["expected_fact"], doc_id, abstained=abstained)
        raise AssertionError(f"unexpected path {request.url.path}")

    output = tmp_path / "results.jsonl"
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        exit_code = run_demo_module.run_demo(
            client, "employee", upload=True, output_path=output,
            poll_interval=0.0, status_timeout=30.0,
        )

    assert interactions["queries"] == 8  # 8 employee-role questions asked
    assert interactions["allowed_roles_fields"] == sum(
        len(entry["allowed_roles"]) for entry in
        json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))["documents"]
    )
    assert exit_code == 0
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 8
    rows = [json.loads(line) for line in lines]
    assert all(row["status"] == "pass" for row in rows)
    assert {row["actor_role"] for row in rows} == {"employee"}
    assert not any(row["id"].startswith(("demo_q04", "demo_q06", "demo_q08", "demo_q12")) for row in rows)


def test_run_demo_exit_nonzero_on_failure(httpx_assert_no_network, tmp_path: Path) -> None:
    questions = json.loads((DEMO_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
    called = {"queries": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == run_demo_module.QUERY_PATH:
            called["queries"] += 1
            return _demo_payload("$48,500,000 USD", uuid_module.uuid4())
        raise AssertionError(f"unexpected path {request.url.path}")

    output = tmp_path / "results.jsonl"
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        exit_code = run_demo_module.run_demo(
            client, "manager", upload=False, output_path=output,
            poll_interval=0.0, status_timeout=30.0,
        )
    # Every manager question gets an unrelated financial answer: abstain cases fail.
    assert exit_code == 1
    assert called["queries"] == len([question for question in questions if question["actor_role"] == "manager"]) == 4
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").strip().splitlines()]
    assert {row["status"] for row in rows} == {"fail"}
    assert all(row["status"] == "fail" for row in rows)
