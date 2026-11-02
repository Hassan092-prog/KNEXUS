"""Deterministic offline provider for boundary tests only."""
from app.schemas import EvidenceChunk, GenerationRequest, GenerationResult

async def fake_generate(request: GenerationRequest) -> GenerationResult:
    """Return a contract-valid fixture result; this does not test answer quality."""
    first: EvidenceChunk = request.evidence[0]
    return GenerationResult(
        answer=f"Fixture response for supplied evidence [{first.citation_id}].",
        cited_ids=[first.citation_id],
        abstained=False,
        abstention_reason=None,
    )
