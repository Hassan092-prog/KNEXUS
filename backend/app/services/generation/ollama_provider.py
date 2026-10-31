"""HTTP adapter for Ollama's non-streaming structured generation endpoint."""
import httpx
from pydantic import ValidationError

from app.schemas import GenerationRequest, GenerationResult, validate_generation_result
from app.services.generation.errors import (
    MalformedOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

async def ollama_generate(
    request: GenerationRequest,
    *,
    system_prompt: str,
    prompt: str,
    url: str,
    model: str,
    timeout: float,
    num_ctx: int,
    num_predict: int,
    transport: httpx.AsyncBaseTransport | None = None,
) -> GenerationResult:
    """Send the complete prompt and parse a canonical GenerationResult."""
    payload = {
        "model": model,
        "system": system_prompt,
        "prompt": prompt,
        "stream": False,
        "format": GenerationResult.model_json_schema(),
        "options": {"num_ctx": num_ctx, "num_predict": num_predict},
    }
    try:
        async with httpx.AsyncClient(
            base_url=url, timeout=httpx.Timeout(timeout), transport=transport
        ) as client:
            response = await client.post("/api/generate", json=payload)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ProviderTimeoutError("Ollama request timed out") from exc
    except httpx.HTTPError as exc:
        raise ProviderUnavailableError("Ollama request failed") from exc

    try:
        body = response.json()
    except (ValueError, TypeError) as exc:
        raise MalformedOutputError("Ollama returned an invalid HTTP response") from exc
    if not isinstance(body, dict) or not isinstance(body.get("response"), str):
        raise MalformedOutputError("Ollama response has no text result")
    try:
        result = GenerationResult.model_validate_json(body["response"])
        return validate_generation_result(result, request)
    except (ValidationError, ValueError, TypeError) as exc:
        raise MalformedOutputError(
            "Ollama output does not satisfy the generation contract"
        ) from exc
