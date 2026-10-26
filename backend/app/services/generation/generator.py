import os
from .fake_provider import fake_generate
from .ollama_provider import ollama_generate
from contracts.phase1.models import GenerationRequest, GenerationResult, validate_generation_result

async def generate(request: GenerationRequest) -> GenerationResult:
    """Async wrapper for generation.
    Selects provider based on OLLAMA_PROVIDER env var (default "fake").
    Validates the GenerationResult against the request using the contract validator.
    Provider-specific errors are mapped to a GenerationResult with abstention=True and a diagnostic reason.
    """
    provider = os.getenv("OLLAMA_PROVIDER", "fake").lower()
    if provider == "ollama":
        result = await ollama_generate(request)
    else:
        result = await fake_generate(request)
    # Validate result against request; on validation failure, treat as provider malformed output
    try:
        result = validate_generation_result(result, request)
    except Exception as exc:
        return GenerationResult(
            answer=None,
            cited_ids=[],
            abstained=True,
            abstention_reason=str(exc),
        )
    return result
