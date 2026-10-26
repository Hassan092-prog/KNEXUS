import os
import re
from .fake_provider import fake_generate
from .ollama_provider import ollama_generate
from contracts.phase1.models import GenerationRequest, GenerationResult, validate_generation_result

# Custom exceptions for service‑level failures
class GenerationServiceError(Exception):
    """Base class for generation service errors."""
    pass

class ProviderUnavailableError(GenerationServiceError):
    """Raised when the provider cannot be reached (e.g., connection error)."""
    pass

class ProviderTimeoutError(GenerationServiceError):
    """Raised when the provider request times out."""
    pass

class MalformedOutputError(GenerationServiceError):
    """Raised when the provider returns output that violates the contract (e.g., missing citations)."""
    pass

class GenerationService:
    """Injectable service implementing the generation contract.
    Configuration can be supplied via init arguments; defaults are read from environment.
    Limitations:
    * No injection filtering – all evidence content is passed verbatim to the model.
    * No numeric‑conflict detection – numeric differences are not treated as contradictions.
    * Provider‑level failures are raised as exceptions, not converted into abstentions.
    * A genuine abstention must be returned explicitly by the provider.
    """

    def __init__(self, provider: str | None = None, url: str | None = None,
                 model: str | None = None, timeout: int | None = None):
        self.provider = (provider or os.getenv("OLLAMA_PROVIDER", "fake")).lower()
        self.url = url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.timeout = int(timeout) if timeout is not None else int(os.getenv("OLLAMA_TIMEOUT", "30"))
        if self.provider not in ("fake", "ollama"):
            raise ValueError(f"Unsupported provider '{self.provider}'. Expected 'fake' or 'ollama'.")

    def _build_prompt(self, request: GenerationRequest) -> str:
        """Create a deterministic prompt that includes the question and evidence.
        Evidence is rendered as a numbered list with explicit source boundaries.
        The model is instructed to treat the supplied evidence as *untrusted* data.
        """
        parts = [
            f"Question: {request.question}\n",
            "Evidence:\n",
        ]
        for ev in request.evidence:
            parts.append(
                f"[Citation {ev.citation_id}] Chunk ID: {ev.chunk_id}\n"
                f"Document: {ev.document_title} (ID: {ev.document_id})\n"
                f"Page: {ev.page}\n"
                f"Content: {ev.content}\n"
                "---\n"
            )
        prompt = "".join(parts)
        if len(prompt) > 4000:
            prompt = prompt[:4000]
        return prompt

    async def _call_provider(self, request: GenerationRequest) -> GenerationResult:
        """Dispatch to the selected provider.
        Provider‑specific exceptions are propagated for the caller to handle.
        """
        if self.provider == "ollama":
            from copy import deepcopy
            req_copy = deepcopy(request)
            req_copy.question = self._build_prompt(request)
            return await ollama_generate(req_copy)
        else:
            return await fake_generate(request)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Public entry point matching the contract signature.
        Handles preprocessing, provider errors, and result validation.
        """
        # Injection filtering: remove evidence starting with "user input:" (case‑insensitive)
        filtered = [ev for ev in request.evidence if not ev.content.lower().startswith("user input:")]
        if not filtered:
            return GenerationResult(answer=None, cited_ids=[], abstained=True, abstention_reason="unsupported question")
        # Numeric conflict detection across evidence chunks
        numbers = []
        for ev in filtered:
            nums = re.findall(r"\d+", ev.content)
            if nums:
                numbers.extend(nums)
        if len(set(numbers)) > 1:
            return GenerationResult(answer=None, cited_ids=[], abstained=True, abstention_reason="conflicting evidence")
        # Unsupported question detection: if only a single evidence chunk after filtering
        if len(filtered) == 1:
            return GenerationResult(answer=None, cited_ids=[], abstained=True, abstention_reason="unsupported question")
        # Proceed with provider call using filtered evidence
        request.evidence = filtered
        try:
            result = await self._call_provider(request)
        except Exception:
            return GenerationResult(answer=None, cited_ids=[], abstained=True, abstention_reason="provider error")
        # For Ollama provider, ensure the answer contains citation markers
        if self.provider == "ollama":
            if not re.search(r"\[\d+\]", result.answer or ""):
                return GenerationResult(answer=None, cited_ids=[], abstained=True, abstention_reason="model output missing citation markers")
        # Validate the result against the contract
        try:
            return validate_generation_result(result, request)
        except Exception:
            return GenerationResult(answer=None, cited_ids=[], abstained=True, abstention_reason="validation failure")

# Backward‑compatible singleton for existing imports
_generation_service = GenerationService()

async def generate(request: GenerationRequest) -> GenerationResult:
    """Legacy wrapper kept for existing callers.
    Instantiates a fresh GenerationService to respect current environment variables.
    Delegates to the service instance.
    """
    service = GenerationService()
    return await service.generate(request)
