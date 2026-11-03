"""Hosted chat-completions adapter (OpenAI-compatible endpoints).

Provider selection and request/response parsing adapted from Hassan's
enterprise-knowledge-bot (commit e67771a15f49a79443a365fbce85b8559ef43fb7,
repository https://github.com/Hassan092-prog/enterprise-knowledge-bot,
`src/llm_factory.py` and `src/config.py`). That repository carries no
LICENSE file at this revision; the knowledge-bot source is owned by the
same project author. Adapted here onto KNEXUS's canonical contract,
httpx transport and typed-failure boundary. Differences:

- No LangChain dependency: uses the existing httpx dependency only.
- No automatic retries yet (the source retries 429/5xx with backoff;
  adding bounded retries is deliberately deferred pending review).
- No semantic cache and no query condensation: Phase 1 is non-streaming,
  single-turn, and every query must go to the provider for honest audit.
- KNEXUS canonical schema replaces `[Source: file, Page X]` prose
  citations with inline [citation_id] markers validated against
  authorized evidence.
"""
import httpx
from pydantic import ValidationError

from app.schemas import GenerationRequest, GenerationResult, validate_generation_result
from app.services.generation.errors import (
    MalformedOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

DEFAULT_ENDPOINTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
}

_STRICT_SCHEMA_CACHE: dict[str, object] | None = None
"""Merged schema cache; computed once from the canonical model."""


def strict_generation_schema() -> dict[str, object]:
    """Canonical GenerationResult schema made strict-mode compliant.

    `GenerationResult.model_json_schema()` marks `abstention_reason` with a
    `default` and omits it from `required` because the field is optional in
    Pydantic. Strict json_schema providers (OpenAI, Groq) reject a `default`
    keyword and require every property in `required`; here all fields become
    required (the model must always emit the key, and the canonical
    validation below still enforces the exact answer/abstention invariants).
    """
    global _STRICT_SCHEMA_CACHE
    if _STRICT_SCHEMA_CACHE is None:
        schema = GenerationResult.model_json_schema()
        properties = {
            name: {key: value for key, value in spec.items() if key != "default"}
            for name, spec in schema["properties"].items()
        }
        _STRICT_SCHEMA_CACHE = {
            **schema,
            "properties": properties,
            "required": sorted(properties),
        }
    return _STRICT_SCHEMA_CACHE

async def hosted_generate(
    request: GenerationRequest,
    *,
    system_prompt: str,
    prompt: str,
    url: str,
    model: str,
    timeout: float,
    api_key: str,
    num_predict: int,
    temperature: float = 0.0,
    seed: int | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> GenerationResult:
    """Send a chat completion and parse a canonical GenerationResult."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    payload: dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": num_predict,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "generation_result",
                "strict": True,
                "schema": strict_generation_schema(),
            },
        },
    }
    if seed is not None:
        payload["seed"] = seed
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(
            base_url=url, timeout=httpx.Timeout(timeout), transport=transport
        ) as client:
            response = await client.post(
                "/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ProviderTimeoutError("Hosted provider request timed out") from exc
    except httpx.HTTPStatusError as exc:
        raise ProviderUnavailableError(
            f"Hosted provider returned HTTP {exc.response.status_code}"
        ) from exc
    except httpx.HTTPError as exc:
        raise ProviderUnavailableError("Hosted provider request failed") from exc

    try:
        body = response.json()
    except (ValueError, TypeError) as exc:
        raise MalformedOutputError("Hosted provider returned an invalid HTTP response") from exc
    if not isinstance(body, dict):
        raise MalformedOutputError("Hosted provider response is not an object")
    choices = body.get("choices")
    if not isinstance(choices, list) or len(choices) != 1:
        raise MalformedOutputError("Hosted provider response has no single choice")
    message = choices[0].get("message") if isinstance(choices[0], dict) else None
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        raise MalformedOutputError("Hosted provider response has no text result")
    try:
        result = GenerationResult.model_validate_json(message["content"])
        return validate_generation_result(result, request)
    except (ValidationError, ValueError, TypeError) as exc:
        raise MalformedOutputError(
            "Hosted provider output does not satisfy the generation contract"
        ) from exc
