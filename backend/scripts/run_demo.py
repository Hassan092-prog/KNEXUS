"""Phase 1 demo runner: exercises the 12-question demo set against a live backend.

HTTP client only (stdlib + httpx). No API keys in this script: Phase 1 identity is
owned by the server (see app/api/dependencies.py), and the runner never sends or
spoofs identity fields. ``--actor-role`` only selects which demo questions to ask;
the server must itself run the matching demo actor role for that role group.

Uploads every demo DOCX from backend/tests/fixtures/demo when --upload is given
(repeated ``allowed_roles`` form fields, matching the API contract), polls the
status endpoint until the ingest terminal state or a bounded timeout, then asks
every question whose actor_role matches on POST /api/v1/query (stream=false,
top_k=5). Results are scored, written as JSONL and printed as a table; the exit
code is non-zero when any case fails or errors. Provider/HTTP failures are
recorded as ``error`` rows and never count as a pass.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx

BACKEND_DIR = Path(__file__).resolve().parents[1]
FIXTURES_DIR = BACKEND_DIR / "tests" / "fixtures" / "demo"
UPLOAD_PATH = "/api/v1/documents/upload"
STATUS_PATH = "/api/v1/documents/{document_id}/status"
QUERY_PATH = "/api/v1/query"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_OUTPUT = "demo_results.jsonl"
STATUS_POLL_INTERVAL_SECONDS = 2.0
STATUS_TIMEOUT_SECONDS = 120.0
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
VALID_ROLES = {"employee", "manager", "orgadmin", "superadmin"}


def load_fixtures(fixtures_dir: Path = FIXTURES_DIR) -> tuple[list[dict], list[dict]]:
    manifest = json.loads((fixtures_dir / "manifest.json").read_text(encoding="utf-8"))
    questions = json.loads((fixtures_dir / "questions.json").read_text(encoding="utf-8"))["questions"]
    return manifest["documents"], questions


def upload_documents(
    client: httpx.Client, manifest_docs: list[dict], fixtures_dir: Path = FIXTURES_DIR
) -> dict[str, UUID]:
    """Upload every manifest document once and map its filename -> document_id."""
    document_id_by_source: dict[str, UUID] = {}
    for entry in manifest_docs:
        filename = entry["filename"]
        content = (fixtures_dir / filename).read_bytes()
        files: list[tuple[str, object]] = [
            ("allowed_roles", (None, role)) for role in entry["allowed_roles"]
        ]
        files.append(("title", (None, entry["title"])))
        files.append(("file", (filename, content, DOCX_MIME)))
        response = client.post(UPLOAD_PATH, files=files)
        if response.status_code != 202:
            raise RuntimeError(
                f"upload failed for {filename}: HTTP {response.status_code} {response.text[:200]}"
            )
        payload = response.json()
        document_id_by_source[filename] = UUID(str(payload["document_id"]))
        print(f"uploaded {filename} -> document_id={payload['document_id']}")
    return document_id_by_source


def poll_status(
    client: httpx.Client,
    document_id: UUID,
    *,
    poll_interval: float = STATUS_POLL_INTERVAL_SECONDS,
    status_timeout: float = STATUS_TIMEOUT_SECONDS,
) -> tuple[str, str | None]:
    """Poll the status endpoint until a terminal state; bounded, no retries."""
    deadline = time.monotonic() + status_timeout
    first = True
    while first or time.monotonic() < deadline:
        first = False
        response = client.get(STATUS_PATH.format(document_id=document_id))
        if response.status_code != 200:
            return "error", f"HTTP {response.status_code} {response.text[:200]}"
        payload = response.json()
        state = str(payload["status"])
        if state == "complete":
            return "complete", None
        if state == "failed":
            code = payload.get("failure_code")
            message = payload.get("failure_message")
            return "failed", f"{code}: {message}" if code else str(message)
        if poll_interval > 0:
            time.sleep(poll_interval)
    return "timeout", f"status polling exceeded the {status_timeout:.0f}s bound"


def score_case(
    question: dict[str, Any],
    payload: dict[str, Any],
    document_id_by_source: dict[str, str],
    title_by_source: dict[str, str],
) -> tuple[str, str]:
    """Score one query payload against a demo case ("pass"/"fail", never "error")."""
    expected = question["expected"]
    if payload["abstained"]:
        if expected == "abstain":
            return "pass", "abstained as expected"
        return "fail", f"expected answer, got abstention: {payload.get('abstention_reason')!r}"
    if expected == "abstain":
        return "fail", "expected abstention, an answer was returned"

    answer = payload.get("answer") or ""
    fact = question["expected_fact"]
    source = question["expected_source"]
    allowed_titles = {source, title_by_source.get(source)}
    citation_hit = any(
        document_id_by_source.get(source) == citation.get("document_id")
        or citation.get("document_title") in allowed_titles
        for citation in payload.get("citations", [])
    )
    fact_hit = fact is not None and fact in answer
    if fact_hit and citation_hit:
        return "pass", "expected fact present and citation points at the expected source"
    detail = []
    if not fact_hit:
        detail.append(f"fact {fact!r} missing from the answer")
    if not citation_hit:
        detail.append(f"no citation points at {source}")
    return "fail", "; ".join(detail)


def run_query_case(
    client: httpx.Client,
    question: dict[str, Any],
    document_id_by_source: dict[str, str],
    title_by_source: dict[str, str],
) -> dict[str, Any]:
    """Ask one demo question and score it. Provider/HTTP failures yield 'error' rows."""
    row: dict[str, Any] = {
        "id": question["id"],
        "question": question["question"],
        "actor_role": question["actor_role"],
        "expected": question["expected"],
        "expected_source": question["expected_source"],
        "status": "error",
        "reason": None,
        "abstained": None,
        "answer_excerpt": None,
        "citation_titles": [],
    }
    try:
        response = client.post(
            QUERY_PATH,
            json={"question": question["question"], "top_k": 5, "stream": False},
        )
    except httpx.HTTPError as exc:
        row["reason"] = f"query transport failure: {exc}"
        return row
    if response.status_code != 200:
        try:
            body: dict[str, Any] = response.json()
        except ValueError:
            body = {}
        row["reason"] = (
            f"provider/query error: HTTP {response.status_code} "
            f"{body.get('code')} {body.get('detail')}"
        )
        return row
    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        row["reason"] = f"query response is not JSON: {exc}"
        return row
    status, reason = score_case(question, payload, document_id_by_source, title_by_source)
    row["status"] = status
    row["reason"] = reason
    row["abstained"] = bool(payload.get("abstained"))
    answer = payload.get("answer") or ""
    row["answer_excerpt"] = answer[:240] if not row["abstained"] else None
    row["citation_titles"] = sorted(
        {c.get("document_title") for c in payload.get("citations", []) if c.get("document_title")}
    )
    return row


def run_demo(
    client: httpx.Client,
    actor_role: str,
    *,
    upload: bool,
    output_path: Path,
    fixtures_dir: Path = FIXTURES_DIR,
    poll_interval: float = STATUS_POLL_INTERVAL_SECONDS,
    status_timeout: float = STATUS_TIMEOUT_SECONDS,
) -> int:
    if actor_role not in VALID_ROLES:
        raise ValueError(f"unsupported --actor-role {actor_role!r}")
    manifest_docs, questions = load_fixtures(fixtures_dir)
    document_id_by_source: dict[str, str] = {}
    if upload:
        ids = upload_documents(client, manifest_docs, fixtures_dir)
        for filename, document_id in ids.items():
            state, detail = poll_status(
                client,
                document_id,
                poll_interval=poll_interval,
                status_timeout=status_timeout,
            )
            print(f"ingest {filename}: {state}" + (f" ({detail})" if detail else ""))
        # Ingest failures stay visible; questions are still asked and scored.
        document_id_by_source = {source: str(value) for source, value in ids.items()}
    title_by_source = {entry["filename"]: entry["title"] for entry in manifest_docs}

    rows = []
    for question in questions:
        if question["actor_role"] != actor_role:
            continue
        rows.append(run_query_case(client, question, document_id_by_source, title_by_source))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")

    width = max((len(row["id"]) for row in rows), default=6)
    print()
    print(f"demo run | actor_role={actor_role} | results: {output_path}")
    print(f"{'id'.ljust(width)}  status  detail")
    for row in rows:
        print(
            f"{row['id'].ljust(width)}  {row['status'].ljust(5)}  {row['reason'] or ''}"
        )
    print()
    failed = [row for row in rows if row["status"] != "pass"]
    print(f"{len(rows) - len(failed)}/{len(rows)} passed")
    return 1 if failed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument(
        "--actor-role",
        required=True,
        help="server-owned demo actor role this backend is running with",
    )
    parser.add_argument("--upload", action="store_true", help="upload the demo corpus first")
    parser.add_argument("--output", type=Path, default=Path(DEFAULT_OUTPUT))
    args = parser.parse_args(argv)
    with httpx.Client(base_url=args.base_url, timeout=60.0) as client:
        return run_demo(client, args.actor_role, upload=args.upload, output_path=args.output)


if __name__ == "__main__":
    sys.exit(main())
