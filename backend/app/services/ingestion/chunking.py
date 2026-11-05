"""Source-preserving tokenizer-budgeted document chunking."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Protocol
from uuid import UUID, uuid5

from app.core.config import settings
from app.services.ingestion.errors import TokenizerUnavailableError
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


def chunk_document(
    document_id: UUID,
    sections: list[ParsedSection],
    tokenizer: Tokenizer | None = None,
    *,
    model_max_input_tokens: int | None = None,
) -> list[ChunkDraft]:
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
