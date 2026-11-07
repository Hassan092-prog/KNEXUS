"""Source-preserving tokenizer-budgeted document chunking."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
import inspect
import math
import time
from typing import Any, Callable, Protocol
from uuid import UUID, uuid5

from app.core.config import settings
from app.core.token_counter import TokenCounter, TokenCountResult, validate_token_count_result
from app.services.ingestion.errors import (
    InputTokenLimitExceededError,
    TokenCountingError,
    TokenizerUnavailableError,
)
from app.services.ingestion.parsing import ParsedSection


class Tokenizer(Protocol):
    model_max_length: int

    def encode(self, text: str, *, add_special_tokens: bool = False) -> list[int]: ...
    def num_special_tokens_to_add(self, pair: bool = False) -> int: ...


@dataclass(frozen=True)
class ChunkDraft:
    id: UUID
    chunk_index: int
    content: str
    page: int | None
    token_count: int
    source_metadata: dict[str, Any]


@lru_cache(maxsize=4)
def load_embedding_tokenizer(model_name: str, revision: str) -> Tokenizer:
    """Load only an already-cached tokenizer; never contact the model hub."""
    if (
        model_name in {"gemini-embedding-001", "text-embedding-004", "models/gemini-embedding-001"}
        or settings.EMBEDDING_PROVIDER == "google"
    ):
        raise TokenizerUnavailableError(
            f"Token counting for hosted model '{model_name}' is not supported: "
            "no verified offline tokenizer is available. Character approximations "
            "cannot be persisted as exact token counts."
        )

    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(
            model_name,
            revision=revision,
            local_files_only=True,
            trust_remote_code=False,
        )
    except Exception as exc:
        raise TokenizerUnavailableError(
            "The configured embedding tokenizer is not available in the local cache."
        ) from exc


def _encoded_length(tokenizer: Tokenizer, text: str, *, special: bool) -> int:
    return len(tokenizer.encode(text, add_special_tokens=special))


def _largest_fitting_end(
    text: str, start: int, tokenizer: Tokenizer, token_budget: int
) -> int:
    """Find a source character boundary whose exact text fits the token budget."""
    low = start + 1
    high = min(len(text), start + 8000)
    best = start
    while low <= high:
        middle = (low + high) // 2
        candidate = text[start:middle]
        if _encoded_length(tokenizer, candidate, special=True) <= token_budget:
            best = middle
            low = middle + 1
        else:
            high = middle - 1
    if best == start:
        raise ValueError("The tokenizer budget cannot fit one source character")
    if best < len(text):
        boundary = max(
            (index + 1 for index in range(start, best) if text[index].isspace()),
            default=start,
        )
        if boundary > start and _encoded_length(
            tokenizer, text[start:boundary], special=True
        ) <= token_budget:
            best = boundary
    return best


def _overlap_start(
    text: str, start: int, end: int, tokenizer: Tokenizer, overlap: int
) -> int:
    if overlap == 0:
        return end
    selected = end
    candidate = end - 1
    while candidate > start:
        if _encoded_length(tokenizer, text[candidate:end], special=False) > overlap:
            break
        selected = candidate
        candidate -= 1
    return selected


def chunk_sections(
    document_id: UUID,
    sections: list[ParsedSection],
    tokenizer: Tokenizer,
    *,
    token_limit: int = 240,
    overlap: int = 32,
    model_max_input_tokens: int | None = None,
) -> list[ChunkDraft]:
    """Split exact source spans; enforce the resolved encoder/tokenizer limit."""
    if token_limit <= 0 or overlap < 0:
        raise ValueError("Token limit must be positive and overlap nonnegative")
    special_count = tokenizer.num_special_tokens_to_add(pair=False)
    tokenizer_limit = getattr(tokenizer, "model_max_length", token_limit)
    if not isinstance(tokenizer_limit, int) or tokenizer_limit > 1_000_000:
        tokenizer_limit = token_limit
    limits = [token_limit, tokenizer_limit]
    if model_max_input_tokens is not None:
        if model_max_input_tokens <= 0:
            raise ValueError("The embedding model input limit must be positive")
        limits.append(model_max_input_tokens)
    effective_limit = min(limits)
    payload_limit = effective_limit - special_count
    if payload_limit <= overlap:
        raise ValueError("Tokenizer special tokens and overlap leave no usable chunk budget")

    nonempty = [(index, section) for index, section in enumerate(sections) if section.text]
    if not nonempty:
        return []
    text_parts: list[str] = []
    ranges: list[tuple[int, int, int, ParsedSection]] = []
    cursor = 0
    for position, (source_index, section) in enumerate(nonempty):
        if position:
            text_parts.append("\n\n")
            cursor += 2
        begin = cursor
        text_parts.append(section.text)
        cursor += len(section.text)
        ranges.append((begin, cursor, source_index, section))
    source_text = "".join(text_parts)

    output: list[ChunkDraft] = []
    start = 0
    while start < len(source_text):
        end = _largest_fitting_end(source_text, start, tokenizer, effective_limit)
        raw_content = source_text[start:end]
        leading = len(raw_content) - len(raw_content.lstrip())
        trailing = len(raw_content) - len(raw_content.rstrip())
        content_start = start + leading
        content_end = end - trailing if trailing else end
        content = source_text[content_start:content_end]
        if not content:
            start = end
            continue
        measured_input = _encoded_length(tokenizer, content, special=True)
        if measured_input > effective_limit or len(content) > 8000:
            raise ValueError("A source-preserving chunk exceeds its validated budget")

        source_entries: list[dict[str, Any]] = []
        pages: set[int] = set()
        for section_start, section_end, source_index, section in ranges:
            left = max(content_start, section_start)
            right = min(content_end, section_end)
            if left >= right:
                continue
            source_entries.append({
                "section_index": source_index,
                "char_start": left - section_start,
                "char_end": right - section_start,
                **section.source_metadata,
            })
            if section.page is not None:
                pages.add(section.page)
        one_source = len(source_entries) == 1
        page = next(iter(pages)) if one_source and len(pages) == 1 else None
        output.append(
            ChunkDraft(
                id=uuid5(document_id, f"chunk:{len(output)}"),
                chunk_index=len(output),
                content=content,
                page=page,
                token_count=measured_input,
                source_metadata={
                    "char_start": content_start,
                    "char_end": content_end,
                    "sections": source_entries,
                },
            )
        )
        if end >= len(source_text):
            break
        next_start = _overlap_start(source_text, start, end, tokenizer, overlap)
        if not start < next_start <= end or (overlap > 0 and next_start == end):
            raise ValueError("Chunk overlap prevents progress")
        start = next_start
    return output


PHYSICAL_MAX_CANDIDATE_CHARS: int = 8000
# The 8,000-character guard is a physical size boundary to reject pathological inputs, not proof of token safety.


def _supports_timeout_arg(counter: TokenCounter) -> bool:
    """Determine before invocation whether a counter accepts a timeout parameter."""
    try:
        sig = inspect.signature(counter.count_tokens)
        return any(
            param.name == "timeout" or param.kind == inspect.Parameter.VAR_KEYWORD
            for param in sig.parameters.values()
        )
    except (ValueError, TypeError):
        return True


def chunk_document_with_token_validation(
    document_id: UUID,
    sections: list[ParsedSection],
    token_counter: TokenCounter,
    *,
    model: str = "gemini-embedding-001",
    target_chars: int = 1000,
    max_candidate_chars: int = 2000,
    overlap_chars: int = 100,
    max_effective_tokens: int | None = None,
    max_validation_calls: int | None = None,
    deadline_seconds: float | None = None,
    clock: Callable[[], float] = time.monotonic,
) -> list[ChunkDraft]:
    """Split source text by proposing candidate boundaries locally and validating exact token counts.

    Does not rely on remote binary-search tokenization: proposes candidate boundaries locally,
    then validates candidate units with bounded external calls and explicit splitting of oversized candidates.
    Character windows are candidate boundaries only; exact Unicode spans, metadata, and deterministic
    UUIDs (uuid5) are strictly preserved.
    Exhausting the validation call allowance or monotonic deadline fails closed before further counting or embedding.
    Never silently truncates source text.

    Limitation Note:
    In synchronous execution environments, an in-flight counting operation cannot be
    preemptively aborted mid-network-call without process/thread interruption. To ensure
    strict deadline enforcement, remaining allowance is passed into supported counter operations,
    and the monotonic deadline is checked both before and immediately after each counting call.
    Any late result is strictly rejected and discarded, preventing chunk acceptance or
    subsequent embedding dispatch.
    """
    effective_ceiling = (
        max_effective_tokens
        if max_effective_tokens is not None
        else settings.EMBEDDING_MAX_INPUT_TOKENS
    )
    call_allowance = (
        max_validation_calls
        if max_validation_calls is not None
        else settings.EMBEDDING_MAX_VALIDATION_CALLS_PER_DOC
    )
    raw_deadline = (
        deadline_seconds
        if deadline_seconds is not None
        else settings.EMBEDDING_VALIDATION_DEADLINE_SECONDS
    )

    if isinstance(raw_deadline, bool) or not isinstance(raw_deadline, (int, float)) or not math.isfinite(raw_deadline) or raw_deadline <= 0:
        raise ValueError("deadline_seconds must be a finite positive number")
    deadline = float(raw_deadline)

    if target_chars <= 0 or max_candidate_chars <= 0:
        raise ValueError("Candidate character limits must be positive")
    if max_candidate_chars < target_chars:
        raise ValueError("max_candidate_chars must be greater than or equal to target_chars")
    if overlap_chars < 0:
        raise ValueError("overlap_chars must be non-negative")
    if effective_ceiling <= 0:
        raise ValueError("max_effective_tokens must be positive")
    if call_allowance <= 0:
        raise ValueError("max_validation_calls must be positive")
    supports_timeout = _supports_timeout_arg(token_counter)

    nonempty = [(index, s) for index, s in enumerate(sections) if s.text]
    if not nonempty:
        return []

    text_parts: list[str] = []
    ranges: list[tuple[int, int, int, ParsedSection]] = []
    cursor = 0
    for position, (source_index, section) in enumerate(nonempty):
        if position:
            text_parts.append("\n\n")
            cursor += 2
        begin = cursor
        text_parts.append(section.text)
        cursor += len(section.text)
        ranges.append((begin, cursor, source_index, section))
    source_text = "".join(text_parts)
    n = len(source_text)

    output: list[ChunkDraft] = []
    start = 0
    start_time = clock()
    deadline_time = start_time + deadline
    validation_calls = 0

    while start < n:
        # 1. Propose candidate end locally (candidate boundary proposal only)
        proposed_end = min(n, start + target_chars)
        if proposed_end < n:
            search_window = source_text[start : min(n, start + max_candidate_chars)]
            best_break = -1
            half_target = target_chars // 2
            for delim in ["\n\n", "\n", ". ", "? ", "! ", "; ", " "]:
                pos = search_window.rfind(delim, half_target)
                if pos != -1:
                    best_break = start + pos + len(delim)
                    break
            if best_break != -1:
                proposed_end = best_break
            else:
                proposed_end = min(n, start + max_candidate_chars)

        curr_end = proposed_end

        # 2. Validate candidate with token counter; split if oversized
        while curr_end > start:
            # Physical size guard check: candidate window cannot exceed physical guard limit
            if (curr_end - start) > PHYSICAL_MAX_CANDIDATE_CHARS:
                curr_end = start + PHYSICAL_MAX_CANDIDATE_CHARS

            raw_content = source_text[start:curr_end]
            leading = len(raw_content) - len(raw_content.lstrip())
            trailing = len(raw_content) - len(raw_content.rstrip())
            content_start = start + leading
            content_end = curr_end - trailing if trailing else curr_end
            content = source_text[content_start:content_end]

            if not content:
                start = curr_end
                break

            # Physical size boundary on stripped candidate content
            if len(content) > PHYSICAL_MAX_CANDIDATE_CHARS:
                curr_end = content_start + PHYSICAL_MAX_CANDIDATE_CHARS
                continue

            # Check if byte-bound skip applies behind Settings flag:
            # utf8_bytes(candidate) + max_overhead_tokens <= effective_ceiling
            overhead = getattr(token_counter, "overhead_tokens", settings.EMBEDDING_COUNTING_OVERHEAD_TOKENS)
            content_bytes = len(content.encode("utf-8"))
            if settings.TOKEN_COUNT_BYTE_BOUND_SKIP and (content_bytes + overhead <= effective_ceiling):
                count_res = TokenCountResult(
                    raw_tokens=content_bytes,
                    overhead_tokens=overhead,
                    effective_tokens=content_bytes + overhead,
                    model_name=model,
                    content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
                    request_type="document",
                    skipped_by_byte_bound=True,
                )
            else:
                # Check monotonic deadline and call allowance BEFORE the counting operation
                now = clock()
                remaining_allowance = deadline_time - now
                if remaining_allowance <= 0 or (now - start_time) >= deadline:
                    raise TokenCountingError(
                        f"Token validation deadline of {deadline}s exceeded for document."
                    )
                if validation_calls >= call_allowance:
                    raise TokenCountingError(
                        f"Token validation call allowance of {call_allowance} exceeded for document."
                    )
                validation_calls += 1

                # Pass remaining allowance into supported counter operations without exception-driven fallback
                if supports_timeout:
                    count_res = token_counter.count_tokens(
                        content,
                        model=model,
                        request_type="document",
                        timeout=remaining_allowance,
                    )
                else:
                    count_res = token_counter.count_tokens(
                        content,
                        model=model,
                        request_type="document",
                    )

                # Check monotonic deadline AFTER the counting operation: a late result must not produce accepted chunks
                after_now = clock()
                if after_now >= deadline_time or (after_now - start_time) >= deadline:
                    raise TokenCountingError(
                        f"Token validation deadline of {deadline}s exceeded for document."
                    )

            validate_token_count_result(
                count_res,
                expected_model=model,
                expected_text=content,
                expected_request_type="document",
            )

            # Evaluate effective tokens (raw_tokens + overhead_tokens) against the approved ceiling exactly once
            if count_res.effective_tokens <= effective_ceiling:
                source_entries: list[dict[str, Any]] = []
                pages: set[int] = set()
                for s_start, s_end, s_index, section in ranges:
                    left = max(content_start, s_start)
                    right = min(content_end, s_end)
                    if left >= right:
                        continue
                    source_entries.append({
                        "section_index": s_index,
                        "char_start": left - s_start,
                        "char_end": right - s_start,
                        **section.source_metadata,
                    })
                    if section.page is not None:
                        pages.add(section.page)
                one_source = len(source_entries) == 1
                page = next(iter(pages)) if one_source and len(pages) == 1 else None

                chunk_idx = len(output)
                output.append(
                    ChunkDraft(
                        id=uuid5(document_id, f"chunk:{chunk_idx}"),
                        chunk_index=chunk_idx,
                        content=content,
                        page=page,
                        token_count=count_res.raw_tokens,
                        source_metadata={
                            "char_start": content_start,
                            "char_end": content_end,
                            "sections": source_entries,
                            "effective_tokens": count_res.effective_tokens,
                            "overhead_tokens": count_res.overhead_tokens,
                            "skipped_by_byte_bound": count_res.skipped_by_byte_bound,
                        },
                    )
                )

                if curr_end >= n:
                    start = n
                else:
                    if overlap_chars > 0:
                        overlap_candidate = max(start + 1, curr_end - overlap_chars)
                        space_pos = source_text.find(" ", overlap_candidate, curr_end)
                        if space_pos != -1:
                            next_start = space_pos + 1
                        else:
                            next_start = overlap_candidate
                        start = next_start
                    else:
                        start = curr_end
                break
            else:
                content_len = content_end - content_start
                if content_len <= 1:
                    raise InputTokenLimitExceededError(
                        f"Atomic character at index {content_start} exceeds token limit "
                        f"({count_res.effective_tokens} > {effective_ceiling}) and cannot be split"
                    )

                mid = content_start + (content_len // 2)
                search_slice = source_text[content_start:mid]
                split_pos = -1
                for delim in ["\n", ". ", "? ", "! ", " "]:
                    pos = search_slice.rfind(delim)
                    if pos != -1:
                        split_pos = content_start + pos + len(delim)
                        break
                if split_pos != -1 and split_pos > content_start:
                    curr_end = split_pos
                else:
                    curr_end = mid

                if curr_end <= content_start:
                    raise InputTokenLimitExceededError(
                        f"Oversized input at characters {content_start}:{content_end} "
                        f"exceeds token limit ({count_res.effective_tokens} > {effective_ceiling}) "
                        "and cannot be split into smaller valid text units"
                    )

    # Final monotonic deadline verification before returning produced drafts
    if clock() >= deadline_time or (clock() - start_time) >= deadline:
        raise TokenCountingError(
            f"Token validation deadline of {deadline}s exceeded for document."
        )

    return output


def chunk_document(
    document_id: UUID,
    sections: list[ParsedSection],
    tokenizer: Tokenizer | None = None,
    *,
    token_counter: TokenCounter | None = None,
    model_max_input_tokens: int | None = None,
    deadline_seconds: float | None = None,
    clock: Callable[[], float] | None = None,
) -> list[ChunkDraft]:
    if token_counter is not None:
        ceiling = getattr(token_counter, "max_allowed_tokens", settings.EMBEDDING_MAX_INPUT_TOKENS)
        effective_deadline = (
            deadline_seconds
            if deadline_seconds is not None
            else getattr(token_counter, "deadline_seconds", settings.EMBEDDING_VALIDATION_DEADLINE_SECONDS)
        )
        effective_clock = (
            clock
            if clock is not None
            else (getattr(token_counter, "clock", None) or time.monotonic)
        )
        return chunk_document_with_token_validation(
            document_id,
            sections,
            token_counter,
            model=getattr(token_counter, "model_name", "gemini-embedding-001"),
            max_effective_tokens=ceiling,
            max_validation_calls=settings.EMBEDDING_MAX_VALIDATION_CALLS_PER_DOC,
            deadline_seconds=effective_deadline,
            clock=effective_clock,
        )

    if settings.EMBEDDING_PROVIDER == "google":
        from app.core.token_counter import get_default_token_counter
        counter = get_default_token_counter(settings.EMBEDDING_MODEL_NAME)
        effective_deadline = (
            deadline_seconds
            if deadline_seconds is not None
            else settings.EMBEDDING_VALIDATION_DEADLINE_SECONDS
        )
        effective_clock = clock if clock is not None else time.monotonic
        return chunk_document_with_token_validation(
            document_id,
            sections,
            counter,
            model=settings.EMBEDDING_MODEL_NAME,
            max_effective_tokens=settings.EMBEDDING_MAX_INPUT_TOKENS,
            max_validation_calls=settings.EMBEDDING_MAX_VALIDATION_CALLS_PER_DOC,
            deadline_seconds=effective_deadline,
            clock=effective_clock,
        )

    tokenizer = tokenizer or load_embedding_tokenizer(
        settings.EMBEDDING_MODEL_NAME, settings.EMBEDDING_MODEL_REVISION
    )
    return chunk_sections(
        document_id,
        sections,
        tokenizer,
        token_limit=settings.CHUNK_TOKEN_LIMIT,
        overlap=settings.CHUNK_TOKEN_OVERLAP,
        model_max_input_tokens=model_max_input_tokens,
    )
