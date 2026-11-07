"""Safe typed failures for document ingestion and embedding."""


class DocumentInputError(ValueError):
    """The submitted file is invalid, unreadable, or outside resource limits."""


class ParserUnavailableError(RuntimeError):
    """An installed parser required for supported document types is unavailable."""


class TokenizerUnavailableError(RuntimeError):
    """The configured embedding tokenizer is not present in the local cache."""


class EmbeddingUnavailableError(RuntimeError):
    """The configured embedding model cannot be loaded from the local cache."""


class StorageError(RuntimeError):
    """Private upload storage could not safely read or write the document."""


class IngestionProcessingError(RuntimeError):
    """A safe, expected failure while indexing a persisted document."""


class TokenCountingError(RuntimeError):
    """Failure occurred during hosted token counting or response validation."""


class EmbeddingSettlementError(EmbeddingUnavailableError):
    """Failure occurred while recording embedding settlement in the durable quota ledger.

    Preserves safe classification of the original provider failure without leaking
    sensitive payload content, credentials, or internal exception traces.
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


class TokenCountingSettlementError(TokenCountingError):
    """Failure occurred while recording settlement in the durable quota ledger.

    Preserves safe classification of the original provider failure without leaking
    sensitive payload content, credentials, or internal exception traces.
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


class InputTokenLimitExceededError(ValueError):
    """The submitted input exceeds the approved model token limit after counting and overhead."""
