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


# ---------------------------------------------------------------------------
# Tolerant normalization
# ---------------------------------------------------------------------------

NORMALIZE = run_demo_module.normalize_text


def test_normalize_currency_millions_commas_and_units() -> None:
    # The q03 money trio must all be interchangeable.
    assert (
        NORMALIZE("$48,500,000 USD")
        == NORMALIZE("48,500,000")
        == NORMALIZE("48.5 million")
        == NORMALIZE("$48.5 million USD")
        == NORMALIZE("48.5 million dollars")
        == NORMALIZE("48.5M")
    )
    # Currency symbols and tokens drop out entirely; commas inside digit groups vanish.
    assert NORMALIZE("$11,200,000 USD in Q4") == NORMALIZE("11.2 million in q4")
    assert NORMALIZE("11,200,000 USD") == NORMALIZE("11.2M")
    # Units: liters/litres/L collapse; minutes/min collapse.
    assert NORMALIZE("3.5 liters") == NORMALIZE("3.5 L") == NORMALIZE("3.5 litres")
    assert NORMALIZE("47 minutes") == NORMALIZE("47 min")
    assert NORMALIZE("2 kilograms") == NORMALIZE("2 kg")
    # Case and whitespace differences vanish.
    assert NORMALIZE("ACME-HALT-999") == NORMALIZE("acme halt 999")
    assert NORMALIZE("Review  Cycle:   Annual") == NORMALIZE("review cycle annual")
    # Decimal numbers survive normalization ("3.5" stays "3.5").
    assert NORMALIZE("exactly 3.5 liters") == "exactly 3.5 l"
    # Word-number compounds: forty-seven minutes.
    assert NORMALIZE("forty-seven minutes") == NORMALIZE("47 min")


def test_accepted_facts_includes_expected_and_any_variants() -> None:
    question = {
        "expected_fact": "$48,500,000 USD",
        "expected_fact_any": ["$48,500,000 USD", "48.5 million", "48.5M"],
    }
    assert run_demo_module.accepted_facts(question) == ["$48,500,000 USD", "48.5 million", "48.5M"]
    # Expected-fact-only questions keep a single accepted phrasing; abstain questions accept none.
    assert run_demo_module.accepted_facts({"expected_fact": "42 widgets", "expected_fact_any": None}) == [
        "42 widgets"
    ]
    assert run_demo_module.accepted_facts({"expected_fact": None, "expected_fact_any": []}) == []


def test_match_accepted_facts_any_variant_matches_reworded_answer() -> None:
    question = {
        "expected_fact": "$48,500,000 USD",
        "expected_fact_any": ["$48,500,000 USD", "48,500,000", "48.5 million", "$48.5 million USD", "48.5M"],
    }
    # Exact phrasing: normal match, exact substring hit recorded.
    matched, matched_fact, exact = run_demo_module.match_accepted_facts(
        question, "Revenue was $48,500,000 USD in Q3."
    )
    assert matched and matched_fact == "$48,500,000 USD" and exact
    # Reworded (normalized-only) phrasing: matches, exact_hit stays False for reviewers.
    matched, matched_fact, exact = run_demo_module.match_accepted_facts(
        question, "Consolidated revenue was about 48.5 million dollars."
    )
    assert matched and matched_fact == "$48,500,000 USD" and not exact
    # A variant rewording still matches the same normalized fact.
    hybrid = {"expected_fact": "42 widgets", "expected_fact_any": ["42 widgets", "forty-two widgets"]}
    matched, matched_fact, exact = run_demo_module.match_accepted_facts(
        hybrid, "We shipped forty-two widgets."
    )
    assert matched and matched_fact == "42 widgets" and not exact
    # Wrong number never matches any accepted phrasing.
    matched, _, _ = run_demo_module.match_accepted_facts(question, "Revenue was $41,020,000 USD.")
    assert not matched


def test_scoring_scores_saved_live_q01_answer_annual_pass_monthly_fail() -> None:
    """The saved live Groq answer for q01 must pass; the monthly phrasing must fail."""
    fixture_questions = json.loads((DEMO_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
    q01 = next(question for question in fixture_questions if question["id"] == "demo_q01")
    doc_ids = {"demo_security_policy.docx": str(DOC_ID)}
    titles = {"demo_security_policy.docx": "Enterprise Information Security Policy"}

    # Saved live answer: paraphrase (no variant is an exact substring), pass.
    good = {
        "abstained": False,
        "answer": "The enterprise security policy is reviewed annually [1].",
        "citations": [citation(DOC_ID, title="demo_security_policy.docx")],
    }
    status, reason = run_demo_module.score_case(q01, good, doc_ids, titles)
    assert status == "pass" and "normalized match only" in reason
    fact_ok, matched_fact, exact = run_demo_module.match_accepted_facts(q01, good["answer"])
    assert fact_ok and matched_fact in ("annually", "reviewed annually") and not exact

    # Monthly (the wrong cadence, same citation) must fail.
    bad = {
        "abstained": False,
        "answer": "The enterprise security policy is reviewed monthly [1].",
        "citations": [citation(DOC_ID, title="demo_security_policy.docx")],
    }
    fact_ok, _, _ = run_demo_module.match_accepted_facts(q01, bad["answer"])
    assert not fact_ok
    status, reason = run_demo_module.score_case(q01, bad, doc_ids, titles)
    assert status == "fail" and "none of the accepted facts matched" in reason


def test_scoring_accepts_reworded_but_correct_answer_and_flags_wrong_number() -> None:
    question = answer_case()
    question["expected_fact"] = "3.5 liters"
    question["expected_fact_any"] = ["3.5 liters", "3.5 L", "exactly 3.5 liters"]
    # Reworded-but-correct answer passes with normalized-only matching
    # (exact_fact_match stays False for reviewers).
    payload = {
        "abstained": False,
        "answer": "You must add exactly 3.5 L of water.",
        "citations": [citation(DOC_ID)],
    }
    status, reason = score(payload, question=question)
    assert status == "pass" and "normalized match only" in reason
    # A wrong number fails even though a citation points at the right source.
    wrong = {
        "abstained": False,
        "answer": "You must add 5.0 L of water.",
        "citations": [citation(DOC_ID)],
    }
    assert score(wrong, question=question)[0] == "fail"


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


def test_run_query_case_records_fact_flag_similarity_and_meta_fields(httpx_assert_no_network) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "answer": "About 48.5 million dollars.",
            "citations": [
                citation(DOC_ID),
                {**citation(DOC_ID), "id": 2, "chunk_index": 1, "similarity_score": 0.42},
            ],
            "abstained": False, "abstention_reason": None,
            "session_id": str(uuid_module.uuid4()),
            "meta": {"model": "openai/test-model", "retrieval_time_ms": 8.0,
                     "generation_time_ms": 120.0},
        })

    question = answer_case()
    question["expected_fact"] = "$48,500,000 USD"
    question["expected_fact_any"] = ["$48,500,000 USD", "48.5 million"]
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        row = run_demo_module.run_query_case(
            client, question, {"demo.docx": str(DOC_ID)}, {"demo.docx": "Demo Title"}
        )
    assert row["status"] == "pass"
    assert row["fact_matched"] is True
    assert row["matched_fact"] == "$48,500,000 USD"  # first accepted candidate matches
    assert row["exact_fact_match"] is False  # normalized-only, kept separately for reviewers
    # Contract field similarity_score, recorded per citation: descending with max.
    assert row["similarities"] == [0.9, 0.42]
    assert row["max_similarity"] == 0.9
    assert row["abstained"] is False and row["abstention_reason"] is None
    assert row["meta"]["model"] == "openai/test-model"
    assert row["meta"]["retrieval_time_ms"] == 8.0 and row["meta"]["generation_time_ms"] == 120.0
    # An abstained row records the reason; no fact fields are claimed.
    def abstain_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={
            "answer": None, "citations": [], "abstained": True,
            "abstention_reason": "No sufficiently relevant accessible evidence was found.",
            "session_id": str(uuid_module.uuid4()),
            "meta": {"model": "openai/test-model"},
        })

    question_abstain = answer_case()
    with httpx.Client(transport=httpx.MockTransport(abstain_handler), base_url="http://test") as client:
        row2 = run_demo_module.run_query_case(
            client, question_abstain, {"demo.docx": str(DOC_ID)}, {}
        )
    assert row2["status"] == "fail"  # expected answer, got abstention
    assert row2["abstained"] is True
    assert row2["abstention_reason"] == "No sufficiently relevant accessible evidence was found."
    assert row2["similarities"] == [] and row2["max_similarity"] is None
    assert row2["fact_matched"] is False and row2["matched_fact"] is None


def test_run_demo_prints_threshold_calibration_table(httpx_assert_no_network, tmp_path, capsys) -> None:
    questions = json.loads((DEMO_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
    asked = [q for q in questions if q["actor_role"] == "employee"]
    answers = iter(asked)

    def handler(request: httpx.Request) -> httpx.Response:
        case = next(answers)
        if case["expected"] == "abstain":
            return httpx.Response(200, json={
                "answer": None, "citations": [], "abstained": True,
                "abstention_reason": "no evidence", "session_id": str(uuid_module.uuid4()),
                "meta": {},
            })
        return httpx.Response(200, json={
            "answer": f"fact: {case['expected_fact']}",
            "citations": [{**citation(DOC_ID), "similarity_score": 0.73}],
            "abstained": False, "abstention_reason": None,
            "session_id": str(uuid_module.uuid4()), "meta": {},
        })

    output = tmp_path / "results.jsonl"
    with httpx.Client(transport=httpx.MockTransport(handler), base_url="http://test") as client:
        run_demo_module.run_demo(client, "employee", upload=False, output_path=output,
                                 poll_interval=0.0, status_timeout=30.0)
    printed = capsys.readouterr().out
    assert "threshold calibration" in printed and "max_similarity" in printed
    calibration_section = printed.split("threshold calibration", 1)[1]
    row_lines = [line for line in calibration_section.splitlines() if line.strip().startswith("demo_q")]
    assert len(row_lines) == 8  # 8 employee questions: id | expected | abstained | max_similarity
    for question in questions:
        if question["actor_role"] != "employee":
            continue
        matching = [line for line in row_lines if question["id"] in line]
        assert len(matching) == 1
        columns = matching[0].split()
        # id expected abstained max_similarity: 0.73 when answered, n/a on abstention.
        expected_value = "0.7300" if question["expected"] == "answer" else "n/a"
        assert columns[-1] == expected_value
        assert (columns[-2] == "True") if question["expected"] == "abstain" else (columns[-2] == "False")
    # JSONL rows carry the calibration data Hassan needs: answered rows have
    # similarity values; abstained rows abstention fields and no similarity.
    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").strip().splitlines()]
    answered_rows = [row for row in rows if not row["abstained"]]
    assert answered_rows and all(row["max_similarity"] == 0.73 for row in answered_rows)
    abstained_rows = [row for row in rows if row["abstained"]]
    assert abstained_rows and all(
        row["max_similarity"] is None and row["abstention_reason"] for row in abstained_rows
    )


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
