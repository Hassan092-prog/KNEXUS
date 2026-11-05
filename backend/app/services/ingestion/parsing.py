"""Bounded PDF and DOCX parsing with source-location metadata."""
from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Any
import zipfile

from app.core.config import settings
from app.services.ingestion.errors import DocumentInputError, ParserUnavailableError


@dataclass(frozen=True)
class ParsedSection:
    text: str
    page: int | None
    source_metadata: dict[str, Any]


def _check_docx_archive(data: bytes) -> None:
    try:
        with zipfile.ZipFile(BytesIO(data)) as archive:
            infos = archive.infolist()
            if len(infos) > 1000:
                raise DocumentInputError("The DOCX contains too many internal files.")
            expanded = sum(info.file_size for info in infos)
            if expanded > 50 * 1024 * 1024:
                raise DocumentInputError("The DOCX expands beyond the parser size limit.")
            if any(info.file_size > 20 * 1024 * 1024 for info in infos):
                raise DocumentInputError("A DOCX part exceeds the parser size limit.")
            if "[Content_Types].xml" not in archive.namelist() or "word/document.xml" not in archive.namelist():
                raise DocumentInputError("The DOCX package is incomplete.")
            if any(info.flag_bits & 0x1 for info in infos):
                raise DocumentInputError("Encrypted DOCX files are not supported.")
    except DocumentInputError:
        raise
    except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
        raise DocumentInputError("The DOCX package is unreadable.") from exc


def detect_source_type(filename: str, content_type: str | None, data: bytes) -> str:
    """Validate extension, optional MIME declaration, and the file signature."""
    suffix = Path(filename).suffix.lower()
    allowed = {
        ".pdf": ("pdf", "application/pdf"),
        ".docx": (
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    }
    if suffix not in allowed:
        raise DocumentInputError("Only PDF and DOCX files are accepted.")
    source_type, expected_mime = allowed[suffix]
    if content_type and content_type not in {expected_mime, "application/octet-stream"}:
        raise DocumentInputError("The declared media type does not match the file type.")
    if source_type == "pdf":
        if not data.startswith(b"%PDF-"):
            raise DocumentInputError("The PDF signature is invalid.")
    else:
        if not data.startswith(b"PK\x03\x04"):
            raise DocumentInputError("The DOCX signature is invalid.")
        _check_docx_archive(data)
    return source_type


def _parse_pdf(data: bytes) -> list[ParsedSection]:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ParserUnavailableError("The PDF parser is not installed.") from exc

    try:
        with pdfplumber.open(BytesIO(data)) as pdf:
            if not pdf.pages or len(pdf.pages) > settings.MAX_PDF_PAGES:
                raise DocumentInputError("The PDF page count is outside the supported range.")
            sections: list[ParsedSection] = []
            extracted_chars = 0
            for page_number, page in enumerate(pdf.pages, start=1):
                text = (page.extract_text() or "").strip()
                extracted_chars += len(text)
                if extracted_chars > settings.MAX_EXTRACTED_CHARS:
                    raise DocumentInputError("The extracted document exceeds the parser text limit.")
                if text:
                    sections.append(
                        ParsedSection(
                            text=text,
                            page=page_number,
                            source_metadata={"page_number": page_number},
                        )
                    )
    except DocumentInputError:
        raise
    except Exception as exc:
        raise DocumentInputError("The PDF could not be read.") from exc
    if not sections:
        raise DocumentInputError("The PDF contains no extractable text.")
    return sections


def _parse_docx(data: bytes) -> list[ParsedSection]:
    try:
        from docx import Document as WordDocument
        from docx.table import Table
        from docx.text.paragraph import Paragraph
    except ImportError as exc:
        raise ParserUnavailableError("The DOCX parser is not installed.") from exc

    try:
        document = WordDocument(BytesIO(data))
        sections: list[ParsedSection] = []
        extracted_chars = 0
        paragraph_number = 0
        table_number = 0
        for block in document.element.body.iterchildren():
            if block.tag.endswith("}p"):
                paragraph_number += 1
                text = Paragraph(block, document).text.strip()
                if not text:
                    continue
                source = {"block_type": "paragraph", "paragraph_number": paragraph_number}
            elif block.tag.endswith("}tbl"):
                table_number += 1
                table = Table(block, document)
                for row_number, row in enumerate(table.rows, start=1):
                    cells = [cell.text.strip() for cell in row.cells]
                    text = " | ".join(cell for cell in cells if cell)
                    if not text:
                        continue
                    extracted_chars += len(text)
                    if extracted_chars > settings.MAX_EXTRACTED_CHARS:
                        raise DocumentInputError("The extracted document exceeds the parser text limit.")
                    sections.append(
                        ParsedSection(
                            text=text,
                            page=None,
                            source_metadata={
                                "block_type": "table_row",
                                "table_number": table_number,
                                "row_number": row_number,
                            },
                        )
                    )
                continue
            else:
                continue
            extracted_chars += len(text)
            if extracted_chars > settings.MAX_EXTRACTED_CHARS:
                raise DocumentInputError("The extracted document exceeds the parser text limit.")
            sections.append(ParsedSection(text=text, page=None, source_metadata=source))
    except DocumentInputError:
        raise
    except Exception as exc:
        raise DocumentInputError("The DOCX could not be read.") from exc
    if not sections:
        raise DocumentInputError("The DOCX contains no extractable text.")
    return sections


def parse_document_bytes(data: bytes, source_type: str) -> list[ParsedSection]:
    """Parse a previously signature-validated PDF/DOCX byte sequence."""
    if not data or len(data) > settings.MAX_UPLOAD_BYTES:
        raise DocumentInputError("The file is empty or exceeds the upload limit.")
    if source_type == "pdf":
        return _parse_pdf(data)
    if source_type == "docx":
        return _parse_docx(data)
    raise DocumentInputError("Only PDF and DOCX files are accepted.")


def parse_uploaded_document(
    filename: str, content_type: str | None, data: bytes
) -> tuple[str, list[ParsedSection]]:
    if not data:
        raise DocumentInputError("The uploaded file is empty.")
    if len(data) > settings.MAX_UPLOAD_BYTES:
        raise DocumentInputError("The upload exceeds the 10 MiB limit.")
    source_type = detect_source_type(filename, content_type, data)
    return source_type, parse_document_bytes(data, source_type)
