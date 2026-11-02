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
