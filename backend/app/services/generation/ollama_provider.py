import os
import re
import httpx
from typing import Any

from contracts.phase1.models import GenerationRequest, GenerationResult, EvidenceChunk


def _extract_citation_ids(answer: str) -> list[int]:
    """Return a list of integer citation IDs found in ``[id]`` markers.
    The regex finds any sequence of digits inside square brackets.
    Duplicates are removed while preserving order of first occurrence.
    """
    ids = [int(m) for m in re.findall(r"\[(\d+)\]", answer)]
    # Preserve order, drop duplicates
    seen = set()
    uniq: list[int] = []
    for i in ids:
        if i not in seen:
            seen.add(i)
            uniq.append(i)
    return uniq


async def ollama_generate(request: GenerationRequest) -> GenerationResult:
    """Call a local Ollama server to generate an answer.
    The Ollama API expects a JSON payload with ``model`` and ``prompt``.
    The response returns a ``response`` string containing the generated text.
    This implementation extracts inline citation markers ``[id]`` from the
    answer and validates them against the supplied evidence. If no markers are
    present, we fall back to citing the first evidence chunk (mirroring the fake
    provider) so the contract's ``cited_ids`` never ends up empty.
    """
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = os.getenv("OLLAMA_MODEL", "llama2")
    payload = {"model": model, "prompt": request.question, "stream": False}
    try:
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            resp = await client.post("/api/generate", json=payload)
            resp.raise_for_status()
            data = resp.json()
            answer = data.get("response", "")
    except httpx.HTTPError as exc:
        # Propagate network/server errors to caller for unified handling
        raise RuntimeError(f"Ollama request failed: {exc}")
    except Exception as exc:
        # Unexpected error – propagate
        raise RuntimeError(f"Unexpected error in Ollama provider: {exc}")
    cited_ids = _extract_citation_ids(answer)
    # ---------- New validation ----------
    if not answer:
        # Empty answer string – treat as provider malformed output
        return GenerationResult(
            answer=None,
            cited_ids=[],
            abstained=True,
            abstention_reason="model output empty",
        )
    if not cited_ids:
        # No citation markers found – provider failed to produce required citations
        return GenerationResult(
            answer=None,
            cited_ids=[],
            abstained=True,
            abstention_reason="model output missing citation markers",
        )
    # Verify that every cited ID is present in the supplied evidence
    allowed = {e.citation_id for e in request.evidence}
    unknown = [cid for cid in cited_ids if cid not in allowed]
    if unknown:
        return GenerationResult(
            answer=None,
            cited_ids=[],
            abstained=True,
            abstention_reason=f"model cited unknown IDs {unknown}",
        )
    # All citations are valid – keep them
    # ------------------------------------
    return GenerationResult(
        answer=answer,
        cited_ids=cited_ids,
        abstained=False,
        abstention_reason=None,
    )
