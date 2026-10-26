from typing import Any
from contracts.phase1.models import GenerationRequest, GenerationResult, EvidenceChunk


async def fake_generate(request: GenerationRequest) -> GenerationResult:
    """Return a deterministic fake generation result.
    Uses the first evidence item to build a simple answer and cites its ID.
    """
    # Ensure there is evidence; contract validation already ensures at least one.
    first: EvidenceChunk = request.evidence[0]
    answer = f"Generated answer based on evidence [{first.citation_id}]."
    return GenerationResult(
        answer=answer,
        cited_ids=[first.citation_id],
        abstained=False,
        abstention_reason=None,
    )
