"""H01 checks for canonical schemas, demo identity and generator injection."""
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.demo_identity import build_demo_actor, expand_effective_roles
from app.core.generation import run_generation
from app.schemas import GenerationRequest, GenerationResult, QueryRequest, Role, UploadMetadata
from contracts.phase1 import models as contract_models
from tests.fakes import FakeGenerator

EXAMPLES = Path(__file__).resolve().parents[2] / "contracts" / "phase1" / "examples"


def fixture(name: str) -> dict[str, object]:
    return json.loads((EXAMPLES / name).read_text(encoding="utf-8"))


def test_application_schema_boundary_reexports_canonical_types() -> None:
    assert QueryRequest is contract_models.QueryRequest
    assert UploadMetadata is contract_models.UploadMetadata
    assert GenerationRequest is contract_models.GenerationRequest
    assert GenerationResult is contract_models.GenerationResult


@pytest.mark.parametrize(
    ("primary", "expected"),
    [
        ("employee", ["employee"]),
        ("manager", ["manager", "employee"]),
        ("orgadmin", ["orgadmin", "manager", "employee"]),
        ("superadmin", ["superadmin", "orgadmin", "manager", "employee"]),
    ],
)
def test_effective_roles_follow_documented_hierarchy(
    primary: Role, expected: list[Role]
) -> None:
    assert expand_effective_roles(primary) == expected


def test_demo_actor_is_server_owned_and_matches_synthetic_fixture() -> None:
    actor = build_demo_actor()
    reference = contract_models.ActorContext.model_validate(fixture("actor-context.json"))
    assert actor == reference
    assert actor.effective_roles == ["orgadmin", "manager", "employee"]


def test_unknown_demo_role_is_rejected() -> None:
    with pytest.raises(ValueError, match="Unsupported demo role"):
        expand_effective_roles("owner")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("user_id", "00000000-0000-4000-8000-000000000031"),
        ("org_id", "00000000-0000-4000-8000-000000000032"),
        ("role", "superadmin"),
        ("effective_roles", ["superadmin"]),
        ("actor", {"user_id": "client-controlled"}),
    ],
)
def test_query_rejects_client_supplied_identity(field: str, value: object) -> None:
    payload = fixture("query-request.json")
    payload[field] = value
    with pytest.raises(ValidationError):
        QueryRequest.model_validate(payload)


def test_upload_roles_remain_valid_metadata_but_identity_is_forbidden() -> None:
    metadata = UploadMetadata.model_validate(fixture("upload-metadata.json"))
    assert metadata.allowed_roles == ["employee"]

    payload = fixture("upload-metadata.json")
    payload["org_id"] = "00000000-0000-4000-8000-000000000032"
    with pytest.raises(ValidationError):
        UploadMetadata.model_validate(payload)


@pytest.mark.asyncio
async def test_generator_can_be_injected_without_ollama_or_database() -> None:
    request = GenerationRequest.model_validate(fixture("generation-request.json"))
    result = GenerationResult.model_validate(fixture("generation-answer.json"))
    generator = FakeGenerator(result)

    returned = await run_generation(generator, request)

    assert returned is result
    assert generator.requests == [request]


@pytest.mark.asyncio
async def test_generator_rejects_citations_outside_supplied_evidence() -> None:
    request = GenerationRequest.model_validate(fixture("generation-request.json"))
    unsupported = GenerationResult(
        answer="Unsupported evidence [2].",
        cited_ids=[2],
        abstained=False,
        abstention_reason=None,
    )

    with pytest.raises(ValueError, match="outside the supplied evidence"):
        await run_generation(FakeGenerator(unsupported), request)


@pytest.mark.asyncio
async def test_generator_boundary_rejects_a_synchronous_implementation() -> None:
    request = GenerationRequest.model_validate(fixture("generation-request.json"))
    result = GenerationResult.model_validate(fixture("generation-answer.json"))

    class SynchronousGenerator:
        def generate(self, request: GenerationRequest) -> GenerationResult:
            return result

    with pytest.raises(TypeError):
        await run_generation(SynchronousGenerator(), request)
