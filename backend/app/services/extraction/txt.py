"""Plain-text document extraction.

Reads UTF-8 text with graceful handling of encoding errors.  The entire
document is treated as a single logical page for consistency with the
page-aware model used by the PDF extractor.
"""

from __future__ import annotations

from pathlib import Path

from app.core.logging import get_logger
from app.services.documents.models import ExtractionResult, ExtractedPage

logger = get_logger(__name__)


def extract_txt(document_id: str, file_path: Path) -> ExtractionResult:
    """Extract text from a plain-text file.

    Args:
        document_id: The internal document identifier.
        file_path: Absolute path to the stored TXT file.

    Returns:
        ``ExtractionResult`` with a single ``ExtractedPage`` representing the
        full document content.

    Raises:
        ``ValueError`` if the file cannot be read or produces no content.
    """
    try:
        # errors="replace" substitutes the Unicode replacement character for
        # any bytes that are not valid UTF-8, preventing a hard crash on
        # malformed / binary content.
        raw = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        raise ValueError(f"Cannot read text file: {exc}") from exc

    text = raw.strip()

    page = ExtractedPage(page_number=1, text=text)
    result = ExtractionResult(
        document_id=document_id,
        pages=[page],
        total_pages=1,
    )
    logger.info(
        "txt.extracted",
        document_id=document_id,
        total_chars=result.total_chars,
    )
    return result
