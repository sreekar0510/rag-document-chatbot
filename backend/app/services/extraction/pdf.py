"""PDF text extraction using PyMuPDF (``fitz``).

Each page is extracted independently.  Pages with no extractable text are
represented as empty strings rather than causing failures.  The extractor
never crashes on a single bad page — it records the error and continues.
"""

from __future__ import annotations

import re
from pathlib import Path

import fitz  # PyMuPDF

from app.core.logging import get_logger
from app.services.documents.models import ExtractionResult, ExtractedPage

logger = get_logger(__name__)

# Collapse 3+ consecutive newlines to 2 (normalise without destroying content)
_MULTI_NEWLINE_RE = re.compile(r"\n{3,}")


def _normalize_text(text: str) -> str:
    """Light normalisation that preserves meaningful whitespace."""
    # Replace form-feeds (PDF page separators) with newlines
    text = text.replace("\f", "\n")
    # Normalise excessive blank lines
    text = _MULTI_NEWLINE_RE.sub("\n\n", text)
    return text.strip()


def extract_pdf(document_id: str, file_path: Path) -> ExtractionResult:
    """Extract text from a PDF file page-by-page.

    Args:
        document_id: The internal document identifier (used for logging only).
        file_path: Absolute path to the stored PDF file.

    Returns:
        ``ExtractionResult`` with one ``ExtractedPage`` per PDF page.

    Raises:
        ``ValueError`` if the file cannot be opened as a PDF or has no pages.
    """
    try:
        doc = fitz.open(str(file_path))
    except Exception as exc:
        raise ValueError(f"Cannot open PDF: {exc}") from exc

    page_count = len(doc)
    if page_count == 0:
        doc.close()
        raise ValueError("PDF contains no pages")

    pages: list[ExtractedPage] = []

    for page_index in range(page_count):
        page_number = page_index + 1  # 1-indexed
        try:
            page = doc[page_index]
            raw_text = page.get_text("text")  # type: ignore[call-arg]
            text = _normalize_text(raw_text)
        except Exception as exc:
            logger.warning(
                "pdf.page_extraction_error",
                document_id=document_id,
                page=page_number,
                error=str(exc),
            )
            text = ""

        pages.append(ExtractedPage(page_number=page_number, text=text))

    doc.close()

    result = ExtractionResult(
        document_id=document_id,
        pages=pages,
        total_pages=page_count,
    )
    logger.info(
        "pdf.extracted",
        document_id=document_id,
        total_pages=result.total_pages,
        total_chars=result.total_chars,
    )
    return result
