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
