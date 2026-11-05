"""Deterministic test doubles for backend-owned service interfaces."""
from dataclasses import dataclass, field

from app.schemas import GenerationRequest, GenerationResult


@dataclass
class FakeGenerator:
    """Return a fixed result and record requests without contacting a model."""

    result: GenerationResult
    requests: list[GenerationRequest] = field(default_factory=list)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        self.requests.append(request)
        return self.result
