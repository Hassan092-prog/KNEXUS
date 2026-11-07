"""Local MiniLM embeddings, hosted Google embeddings, and offline fake double."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
from math import isfinite, sqrt
import os
import random
from threading import Lock
from typing import Any, Protocol, Sequence

import httpx

from app.core.config import settings
from app.core.dispatch_policy import BlockedLiveDispatchPolicy, DispatchPolicy, LiveInferenceBlockedError
from app.models.documents import VECTOR_DIMENSIONS
from app.services.ingestion.errors import (
    EmbeddingSettlementError,
    EmbeddingUnavailableError,
    InputTokenLimitExceededError,
)


SUPPORTED_EMBEDDING_PROVIDERS = {"google", "fake", "local", "sentence-transformers"}
SUPPORTED_GOOGLE_TASK_TYPES = {
    "RETRIEVAL_DOCUMENT",
    "RETRIEVAL_QUERY",
    "SEMANTIC_SIMILARITY",
    "CLASSIFICATION",
    "CLUSTERING",
    "QUESTION_ANSWERING",
    "FACT_VERIFICATION",
}


class Embedder(Protocol):
    model_name: str
    model_revision: str

    def embed_texts(
        self, texts: Sequence[str], *, task_type: str | None = None, **kwargs: Any
    ) -> list[list[float]]: ...


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

    def embed_texts(
        self, texts: Sequence[str], *, task_type: str | None = None, **kwargs: Any
    ) -> list[list[float]]:
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

    def embed_texts(
        self, texts: Sequence[str], *, task_type: str | None = None, **kwargs: Any
    ) -> list[list[float]]:
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


class GoogleGenAIEmbedder:
    """Hosted Google AI Studio embedder requesting provider-supported 384-dim MRL.

    Synchronous adapter: uses httpx.Client; async routes offload calls via asyncio.to_thread.
    Enforces fail-closed live dispatch authorization before any HTTP request or client creation.
    """

    def __init__(
        self,
        model_name: str = "gemini-embedding-001",
        model_revision: str = "001",
        *,
        output_dimensions: int = 384,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 20.0,
        task_type: str = "RETRIEVAL_DOCUMENT",
        transport: httpx.BaseTransport | None = None,
        dispatch_policy: DispatchPolicy | None = None,
        quota_ledger: QuotaLedger | None = None,
    ) -> None:
        self.model_name = model_name
        self.model_revision = model_revision
        self.output_dimensions = output_dimensions
        self.api_key = api_key or (
            settings.EMBEDDING_API_KEY.get_secret_value()
            if settings.EMBEDDING_API_KEY is not None
            else os.getenv("EMBEDDING_API_KEY")
        )
        self.base_url = (
            base_url or settings.EMBEDDING_BASE_URL or "https://generativelanguage.googleapis.com"
        ).rstrip("/")
        self.timeout = timeout
        self.task_type = task_type
        self.transport = transport
        self.dispatch_policy = dispatch_policy or BlockedLiveDispatchPolicy()
        self.quota_ledger = quota_ledger

    def _settle_attempt(
        self,
        attempt_id: str | None,
        *,
        success: bool,
        error: str | None = None,
        status_code: int | None = None,
        usage: dict[str, Any] | None = None,
        provider_failure_detail: str | None = None,
    ) -> None:
        if not self.quota_ledger or not attempt_id:
            return
        try:
            self.quota_ledger.settle_attempt(
                attempt_id,
                usage=usage,
                success=success,
                error=error,
                status_code=status_code,
            )
        except Exception as exc:
            exc_name = type(exc).__name__
            if not success:
                detail = provider_failure_detail or error or (f"http_{status_code}" if status_code else "provider_error")
                msg = f"Quota settlement failed ({exc_name}); outstanding reservation preserved. Original provider failure: {detail}"
            else:
                msg = f"Quota settlement failed ({exc_name}); outstanding reservation preserved."
            raise EmbeddingSettlementError(msg, provider_error=error, status_code=status_code) from None

    def get_max_input_tokens(self) -> int:
        """Google gemini-embedding-001 documented maximum input tokens per chunk."""
        return 2048

    def embed_texts(
        self,
        texts: Sequence[str],
        *,
        task_type: str | None = None,
        **kwargs: Any,
    ) -> list[list[float]]:
        if not texts:
            return []

        # 1. Dispatch authorization check fails closed before any HTTP request or client
        self.dispatch_policy.check_dispatch("google", self.model_name)

        # 2. Credential validation
        if not self.api_key or not self.api_key.strip():
            raise EmbeddingUnavailableError(
                "Set EMBEDDING_API_KEY (or pass api_key) for hosted provider 'google'"
            )

        # 3. Task type validation
        effective_task = task_type or self.task_type
        if effective_task not in SUPPORTED_GOOGLE_TASK_TYPES:
            raise EmbeddingUnavailableError(
                f"Unsupported Google embedding task_type: '{effective_task}'"
            )

        # 4. Durable reserve-before-dispatch
        attempt_id: str | None = None
        if self.quota_ledger:
            attempt_id = self.quota_ledger.reserve_attempt("google", self.model_name)

        endpoint = f"{self.base_url}/v1beta/models/{self.model_name}:batchEmbedContents"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        for t in texts:
            if not isinstance(t, str):
                raise EmbeddingUnavailableError("Input text must be a string")
            if len(t) > 8000:
                raise InputTokenLimitExceededError(
                    f"Input text length ({len(t)}) exceeds maximum safe boundary (8000 chars)"
                )

        requests_payload = [
            {
                "model": f"models/{self.model_name}",
                "content": {"parts": [{"text": t}]},
                "taskType": effective_task,
                "outputDimensionality": self.output_dimensions,
            }
            for t in texts
        ]
        body = {"requests": requests_payload}

        try:
            with httpx.Client(
                timeout=httpx.Timeout(self.timeout), transport=self.transport
            ) as client:
                response = client.post(endpoint, json=body, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            self._settle_attempt(attempt_id, success=False, error="timeout", provider_failure_detail="Google embedding provider timed out")
            raise EmbeddingUnavailableError("Google embedding provider timed out") from exc
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            self._settle_attempt(attempt_id, success=False, error=f"http_{status}", status_code=status, provider_failure_detail=f"HTTP {status}")
            if status == 429:
                raise EmbeddingUnavailableError("Google embedding rate limit exceeded") from exc
            if status in {401, 403}:
                raise EmbeddingUnavailableError(
                    "Google embedding authentication failed: invalid or unauthorized key"
                ) from exc
            raise EmbeddingUnavailableError(
                f"Google embedding provider returned HTTP {status}"
            ) from exc
        except httpx.HTTPError as exc:
            self._settle_attempt(attempt_id, success=False, error="network_error", provider_failure_detail="Google embedding provider request failed")
            raise EmbeddingUnavailableError("Google embedding provider request failed") from exc

        try:
            data = response.json()
        except Exception as exc:
            self._settle_attempt(attempt_id, success=False, error="invalid_response")
            raise EmbeddingUnavailableError(
                "Google embedding provider returned non-JSON response"
            ) from exc

        usage_data = data.get("usageMetadata") if isinstance(data, dict) else None
        parsed_usage: dict[str, Any] | None = None
        if isinstance(usage_data, dict):
            p_tok = usage_data.get("promptTokenCount")
            t_tok = usage_data.get("totalTokenCount")
            if isinstance(p_tok, int) and isinstance(t_tok, int) and p_tok >= 0 and t_tok >= 0:
                parsed_usage = {"prompt_tokens": p_tok, "completion_tokens": 0, "total_tokens": t_tok}

        if not isinstance(data, dict):
            self._settle_attempt(attempt_id, success=False, error="malformed_root", usage=parsed_usage)
            raise EmbeddingUnavailableError("Google embedding response root must be an object")

        if "error" in data:
            err_msg = data.get("error", {}).get("message") if isinstance(data.get("error"), dict) else str(data.get("error"))
            self._settle_attempt(attempt_id, success=False, error="service_error", usage=parsed_usage)
            raise EmbeddingUnavailableError(f"Google embedding service error: {err_msg}")

        raw_embeddings = data.get("embeddings")
        if not isinstance(raw_embeddings, list) or len(raw_embeddings) != len(texts):
            self._settle_attempt(attempt_id, success=False, error="malformed_embeddings", usage=parsed_usage)
            raise EmbeddingUnavailableError(
                "Google embedding response missing embeddings array or count mismatch"
            )

        vectors: list[list[float]] = []
        for idx, item in enumerate(raw_embeddings):
            if not isinstance(item, dict) or "values" not in item:
                self._settle_attempt(attempt_id, success=False, error="malformed_item", usage=parsed_usage)
                raise EmbeddingUnavailableError(f"Google embedding item {idx} missing 'values'")
            values = item["values"]
            if not isinstance(values, list) or len(values) != self.output_dimensions:
                self._settle_attempt(attempt_id, success=False, error="dimension_mismatch", usage=parsed_usage)
                raise EmbeddingUnavailableError(
                    f"Google embedding values dimension mismatch: expected {self.output_dimensions}, "
                    f"got {len(values) if isinstance(values, list) else None}"
                )
            float_vals: list[float] = []
            for elem in values:
                # Reject booleans or non-numbers
                if isinstance(elem, bool) or not isinstance(elem, (int, float)):
                    self._settle_attempt(attempt_id, success=False, error="invalid_vector_element", usage=parsed_usage)
                    raise EmbeddingUnavailableError(
                        f"Google embedding vector element must be a finite number, got {type(elem).__name__}"
                    )
                fv = float(elem)
                if not isfinite(fv):
                    self._settle_attempt(attempt_id, success=False, error="non_finite_vector_value", usage=parsed_usage)
                    raise EmbeddingUnavailableError("Google embedding values contain non-finite numbers")
                float_vals.append(fv)

            norm = sqrt(sum(v * v for v in float_vals))
            if norm <= 0.0 or not isfinite(norm):
                self._settle_attempt(attempt_id, success=False, error="invalid_vector_norm", usage=parsed_usage)
                raise EmbeddingUnavailableError("Google embedding vector has zero or non-finite norm")
            vectors.append([v / norm for v in float_vals])

        self._settle_attempt(attempt_id, success=True, usage=parsed_usage)
        return vectors


@lru_cache(maxsize=4)
def get_default_embedder(
    provider: str | None = None,
    model_name: str | None = None,
    revision: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    transport: httpx.BaseTransport | None = None,
    dispatch_policy: DispatchPolicy | None = None,
    quota_ledger: QuotaLedger | None = None,
) -> Embedder:
    raw_provider = provider or settings.EMBEDDING_PROVIDER
    if not raw_provider or not raw_provider.strip():
        raise ValueError("Embedding provider must be explicitly configured")
    selected_provider = raw_provider.strip().lower()

    if selected_provider not in SUPPORTED_EMBEDDING_PROVIDERS:
        raise ValueError(
            f"Unsupported embedding provider: {selected_provider!r}. "
            f"Must be one of: {sorted(SUPPORTED_EMBEDDING_PROVIDERS)}"
        )

    selected_model = model_name or settings.EMBEDDING_MODEL_NAME
    selected_revision = revision or settings.EMBEDDING_MODEL_REVISION

    if selected_provider == "google":
        return GoogleGenAIEmbedder(
            model_name=selected_model,
            model_revision=selected_revision,
            output_dimensions=settings.EMBEDDING_DIMENSIONS,
            api_key=api_key,
            base_url=base_url,
            timeout=settings.EMBEDDING_TIMEOUT,
            task_type=settings.EMBEDDING_TASK_TYPE,
            transport=transport,
            dispatch_policy=dispatch_policy,
            quota_ledger=quota_ledger,
        )
    if selected_provider == "fake":
        return FakeEmbedder()
    return SentenceTransformerEmbedder(
        selected_model,
        selected_revision,
    )
