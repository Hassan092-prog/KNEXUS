"""Typed failures from the generation service boundary."""

class GenerationServiceError(RuntimeError):
    """Base class for generation failures that the API maps to safe errors."""

class GenerationConfigurationError(GenerationServiceError):
    """Provider configuration is missing or invalid."""

class ProviderUnavailableError(GenerationServiceError):
    """The configured provider could not complete the request."""

class ProviderTimeoutError(GenerationServiceError):
    """Provider or overall generation deadline expired."""

class MalformedOutputError(GenerationServiceError):
    """Provider output does not satisfy the generation result contract."""

class ContextBudgetExceededError(GenerationServiceError):
    """The complete prompt exceeds the configured input-size guard."""

class GenerationSettlementError(GenerationServiceError):
    """Failure occurred while recording settlement in the shared quota ledger.

    Mirrors the ingestion-side TokenCountingSettlementError contract: the
    outstanding reservation is preserved in the ledger (it is never silently
    released), and the classification of any preceding provider failure is
    kept in the message and attributes without leaking payload content,
    credentials, or internal exception traces.
    """

    def __init__(
        self,
        message: str,
        *,
        provider_error: str | None = None,
        status_code: int | None = None,
    ) -> None:
        super().__init__(message)
        self.provider_error = provider_error
        self.status_code = status_code
