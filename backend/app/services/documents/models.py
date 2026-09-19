"""Internal domain models for document ingestion.

These are *not* API response models — they represent the internal state of a
document as it moves through ingestion.  API-facing schemas live in
``app/models/documents.py``.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Status ────────────────────────────────────────────────────────────────────

class DocumentStatus(str, Enum):
    """Processing lifecycle of an ingested document."""

    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"


# ── Extraction layer ──────────────────────────────────────────────────────────

class ExtractedPage(BaseModel):
    """Text extracted from a single page (PDF) or logical section (TXT)."""

    page_number: int  # 1-indexed
    text: str
    char_count: int = Field(default=0)

    def model_post_init(self, __context: object) -> None:
        if self.char_count == 0:
            object.__setattr__(self, "char_count", len(self.text))


class ExtractionResult(BaseModel):
    """Raw output from the extraction layer — consumed by later ingestion stages."""

    document_id: str
    pages: List[ExtractedPage]
    total_pages: int
    total_chars: int = Field(default=0)

    def model_post_init(self, __context: object) -> None:
        if self.total_chars == 0:
            object.__setattr__(
                self, "total_chars", sum(p.char_count for p in self.pages)
            )

    @property
    def full_text(self) -> str:
        """Concatenated text across all pages, separated by newlines."""
        return "\n\n".join(p.text for p in self.pages if p.text.strip())


# ── Document record ────────────────────────────────────────────────────────────

class DocumentRecord(BaseModel):
    """Persistent metadata for an uploaded document."""

    document_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    original_filename: str
    content_type: str          # detected, not trusted from client header
    file_extension: str
    file_size_bytes: int
    storage_path: Path         # absolute path on disk — NEVER exposed to API clients
    status: DocumentStatus = DocumentStatus.UPLOADED
    error_message: Optional[str] = None  # sanitized, no stack traces
    page_count: Optional[int] = None
    total_chars: Optional[int] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def mark_processing(self) -> None:
        self.status = DocumentStatus.PROCESSING
        self.updated_at = datetime.now(timezone.utc)

    def mark_processed(self, *, page_count: int, total_chars: int) -> None:
        self.status = DocumentStatus.PROCESSED
        self.page_count = page_count
        self.total_chars = total_chars
        self.updated_at = datetime.now(timezone.utc)

    def mark_failed(self, reason: str) -> None:
        """Store a sanitized failure reason — no stack traces, no paths."""
        self.status = DocumentStatus.FAILED
        self.error_message = reason
        self.updated_at = datetime.now(timezone.utc)
