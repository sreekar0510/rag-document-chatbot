"""In-memory document metadata store.

Stores ``DocumentRecord`` objects in a plain dict keyed by ``document_id``.

This is intentionally simple for Stage 2.  Later stages will replace this
with a persistent store (e.g. SQLite or a database) without changing the
interface consumed by ``DocumentService``.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from app.services.documents.models import DocumentRecord


class DocumentStore:
    """Thread-unsafe in-memory store (adequate for single-worker dev server).

    Replace with a persistent, thread-safe implementation in later stages.
    """

    def __init__(self) -> None:
        self._records: Dict[str, DocumentRecord] = {}

    def save(self, record: DocumentRecord) -> None:
        """Insert or overwrite a document record."""
        self._records[record.document_id] = record

    def get(self, document_id: str) -> Optional[DocumentRecord]:
        """Return the record for *document_id*, or ``None`` if not found."""
        return self._records.get(document_id)

    def list_all(self) -> List[DocumentRecord]:
        """Return all records ordered by creation time (oldest first)."""
        return sorted(self._records.values(), key=lambda r: r.created_at)

    def delete(self, document_id: str) -> bool:
        """Remove a record.  Returns True if it existed, False otherwise."""
        if document_id in self._records:
            del self._records[document_id]
            return True
        return False

    def __len__(self) -> int:
        return len(self._records)
