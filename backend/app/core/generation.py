"""Backend-owned interface for the independently implemented generator."""
from typing import Protocol

from app.schemas import (
    GenerationRequest,
    GenerationResult,
    validate_generation_result,
)


class GenerationService(Protocol):
    """Generate from evidence already authorized by the backend.

    Implementations must not load database records, select tenants, change
    permissions, or execute tools. The backend validates returned citation IDs.
    """

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Return a contract-valid answer or abstention for supplied evidence."""
        ...


async def run_generation(
    service: GenerationService, request: GenerationRequest
) -> GenerationResult:
    """Call an injected generator and reject citations outside supplied evidence."""
    result = await service.generate(request)
    return validate_generation_result(result, request)
