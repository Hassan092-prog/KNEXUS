"""Cached local MiniLM embeddings and an explicitly injected offline fake."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from math import isfinite, sqrt
import random
from threading import Lock
from typing import Protocol, Sequence

from app.core.config import settings
from app.models.documents import VECTOR_DIMENSIONS
from app.services.ingestion.errors import EmbeddingUnavailableError


class Embedder(Protocol):
    model_name: str
    model_revision: str

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]: ...


def validate_embeddings(
    vectors: Sequence[Sequence[float]], expected_count: int
) -> list[list[float]]:
    if len(vectors) != expected_count:
        raise ValueError("Embedding count does not match text count")
    normalized: list[list[float]] = []
    for vector in vectors:
        values = [float(value) for value in vector]
        if len(values) != VECTOR_DIMENSIONS or not all(isfinite(value) for value in values):
            raise ValueError("Embedding output must contain 384 finite dimensions")
        normalized.append(values)
    return normalized


class FakeEmbedder:
    """Deterministic shape-valid test double; it has no semantic retrieval quality."""

    model_name = "fake-minilm"
    model_revision = "deterministic-v1"

    def get_max_input_tokens(self) -> int:
        return 256

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            seed = int.from_bytes(sha256(text.encode("utf-8")).digest(), "big")
            generator = random.Random(seed)
            values = [generator.uniform(-1.0, 1.0) for _ in range(VECTOR_DIMENSIONS)]
            norm = sqrt(sum(value * value for value in values))
            vectors.append([value / norm for value in values])
        return vectors


class SentenceTransformerEmbedder:
    """Load the agreed model once, on CPU, with local-files-only behavior."""

    def __init__(self, model_name: str, revision: str) -> None:
        self.model_name = model_name
        self.model_revision = revision
        self._model = None
        self._lock = Lock()

    def _get_model(self):
        if self._model is None:
            with self._lock:
                if self._model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                        model = SentenceTransformer(
                            self.model_name,
                            revision=self.model_revision,
                            device="cpu",
                            local_files_only=True,
                            trust_remote_code=False,
                        )
                        config = model._first_module().auto_model.config
                        actual_revision = getattr(config, "_commit_hash", None)
                        if isinstance(actual_revision, str) and actual_revision:
                            self.model_revision = actual_revision
                        self._model = model
                    except Exception as exc:
                        raise EmbeddingUnavailableError(
                            "The configured embedding model is not available in the local cache."
                        ) from exc
        return self._model

    def get_max_input_tokens(self) -> int:
        """Resolve the truncation limit from this exact loaded model snapshot."""
        try:
            limit = int(self._get_model().max_seq_length)
        except Exception as exc:
            raise EmbeddingUnavailableError(
                "The configured embedding model limit is unavailable."
            ) from exc
        if limit <= 0:
            raise EmbeddingUnavailableError(
                "The configured embedding model limit is invalid."
            )
        return limit

    def embed_texts(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []
        try:
            raw = self._get_model().encode(
                list(texts),
                convert_to_numpy=True,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
            return validate_embeddings(raw.tolist(), len(texts))
        except EmbeddingUnavailableError:
            raise
        except Exception as exc:
            raise EmbeddingUnavailableError("The local embedding model failed.") from exc


@lru_cache(maxsize=4)
def get_default_embedder(
    model_name: str | None = None,
    revision: str | None = None,
) -> SentenceTransformerEmbedder:
    return SentenceTransformerEmbedder(
        model_name or settings.EMBEDDING_MODEL_NAME,
        revision or settings.EMBEDDING_MODEL_REVISION,
    )
