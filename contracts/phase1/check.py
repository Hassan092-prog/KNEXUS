"""Validate the shared examples and negative cases without services or a database."""
import argparse
from collections.abc import Callable
from copy import deepcopy
import json
from pathlib import Path

from pydantic import ValidationError
from pydantic.json_schema import models_json_schema
from models import (
    CONTRACT_MODELS, GenerationRequest, GenerationResult, QueryRequest,
    QueryResponse, UploadMetadata, DocumentStatus, validate_generation_result,
)

HERE = Path(__file__).resolve().parent


def exported_schema():
    _, schema = models_json_schema(
        [(model, "validation") for model in CONTRACT_MODELS.values()],
        title="KNEXUS Phase 1 reference contracts",
    )
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-schema", action="store_true")
    args = parser.parse_args()
    schema_path = HERE / "schema.json"
    expected = exported_schema()
    if args.write_schema:
        schema_path.write_text(json.dumps(expected, indent=2) + "\n", encoding="utf-8")
    if json.loads(schema_path.read_text()) != expected:
        raise AssertionError("schema.json is stale; review models.py and regenerate with --write-schema")
    manifest = json.loads((HERE / "examples/manifest.json").read_text())
    actual_files = {p.name for p in (HERE / "examples").glob("*.json") if p.name != "manifest.json"}
    if actual_files != set(manifest):
        raise AssertionError("example manifest must cover every fixture exactly")
    fixtures = {}
    for filename, model_name in manifest.items():
        raw = (HERE / "examples" / filename).read_text()
        CONTRACT_MODELS[model_name].model_validate_json(raw)
        fixtures[filename] = json.loads(raw)
    valid = len(manifest)
    rejected = 0

    def rejects(label: str, operation: Callable[[], object]) -> None:
        nonlocal rejected
        try:
            operation()
        except (ValidationError, ValueError):
            rejected += 1
        else:
            raise AssertionError("accepted invalid case: " + label)

    query = fixtures["query-request.json"]
    for label, changes in [
        ("blank question", {"question": "   "}),
        ("oversize question", {"question": "x" * 4001}),
        ("zero top_k", {"top_k": 0}),
        ("oversize top_k", {"top_k": 21}),
        ("boolean top_k", {"top_k": True}),
        ("string top_k", {"top_k": "5"}),
        ("streaming deferred", {"stream": True}),
        ("client tenant injection", {"org_id": "forged"}),
        ("client role injection", {"role": "superadmin"}),
    ]:
        rejects(label, lambda changes=changes: QueryRequest.model_validate({**query, **changes}))
    upload = fixtures["upload-metadata.json"]
    rejects("unknown role", lambda: UploadMetadata.model_validate({**upload, "allowed_roles": ["owner"]}))
    rejects("empty role set", lambda: UploadMetadata.model_validate({**upload, "allowed_roles": []}))
    rejects("duplicate role", lambda: UploadMetadata.model_validate({**upload, "allowed_roles": ["employee", "employee"]}))
    incoming = GenerationRequest.model_validate(fixtures["generation-request.json"])
    answered = GenerationResult.model_validate(fixtures["generation-answer.json"])
    validate_generation_result(answered, incoming)
    validate_generation_result(GenerationResult.model_validate(fixtures["generation-abstention.json"]), incoming)
    duplicate = deepcopy(fixtures["generation-request.json"])
    duplicate["evidence"].append(deepcopy(duplicate["evidence"][0]))
    rejects("duplicate evidence IDs", lambda: GenerationRequest.model_validate(duplicate))
    rejects("empty evidence cannot invoke provider", lambda: GenerationRequest.model_validate({**fixtures["generation-request.json"], "evidence": []}))
    bad = {**fixtures["generation-answer.json"], "answer": "Unsupported [99].", "cited_ids": [99]}
    rejects("citation outside evidence", lambda: validate_generation_result(GenerationResult.model_validate(bad), incoming))
    rejects("unmatched inline citation", lambda: GenerationResult.model_validate({**fixtures["generation-answer.json"], "answer": "Missing citation marker."}))
    rejects("boolean citation ID", lambda: GenerationResult.model_validate({**fixtures["generation-answer.json"], "cited_ids": [True]}))
    rejects("answer attached to abstention", lambda: GenerationResult.model_validate({**fixtures["generation-abstention.json"], "answer": "Invented answer"}))
    rejects("abstention without reason", lambda: GenerationResult.model_validate({**fixtures["generation-abstention.json"], "abstention_reason": None}))
    rejects("answer without citations", lambda: QueryResponse.model_validate({**fixtures["query-answer.json"], "citations": []}))
    rejects("unfinished complete document", lambda: DocumentStatus.model_validate({**fixtures["document-complete.json"], "chunks_processed": 0}))
    rejects("progress exceeds total", lambda: DocumentStatus.model_validate({**fixtures["document-complete.json"], "chunks_processed": 2}))
    rejects("failed job without safe reason", lambda: DocumentStatus.model_validate({**fixtures["document-failed.json"], "failure_message": None}))
    rejects("failure reason on completed job", lambda: DocumentStatus.model_validate({**fixtures["document-complete.json"], "failure_code": "PROCESSING_FAILED"}))
    print(f"PASS: {valid} synthetic examples, {rejected} negative contract cases, evidence membership, and schema freshness")
    print("This validates contracts only; it does not prove authentication, retrieval relevance, factual support or application endpoint behavior.")


if __name__ == "__main__":
    main()
