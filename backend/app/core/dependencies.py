"""FastAPI dependency providers.

Singleton instances are created once and shared across requests.
"""

from __future__ import annotations

from functools import lru_cache

from app.core.config import get_settings
from app.services.documents.service import DocumentService
from app.services.documents.store import DocumentStore
from app.services.documents.storage import LocalFileStorage


@lru_cache(maxsize=1)
def _get_document_service() -> DocumentService:
    settings = get_settings()
    storage_root = settings.upload_dir
    # Resolve relative to CWD at first access; absolute paths pass through unchanged.
    store = DocumentStore()
    storage = LocalFileStorage(storage_root)
    return DocumentService(store=store, storage=storage)


def get_document_service() -> DocumentService:
    """FastAPI dependency that returns the shared DocumentService."""
    return _get_document_service()
