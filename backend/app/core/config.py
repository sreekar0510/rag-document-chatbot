"""Application configuration using Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration.  All values can be overridden via environment
    variables or a .env file placed in the backend directory."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────────────────────
    app_name: str = "RAG Document Chatbot"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── API ───────────────────────────────────────────────────────────────────
    api_prefix: str = "/api"
    allowed_origins: List[str] = ["http://localhost:5173", "http://localhost:3000"]

    # ── AWS (credentials must NEVER be hardcoded) ─────────────────────────────
    aws_region: str = "us-east-1"
    # AWS credentials are read from the environment / IAM role – never stored here.

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_host: str = "localhost"
    chroma_port: int = 8001
    chroma_collection: str = "documents"

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Document processing ───────────────────────────────────────────────────
    chunk_size: int = 512
    chunk_overlap: int = 64
    max_upload_mb: int = 50

    # ── Retrieval ─────────────────────────────────────────────────────────────
    retrieval_top_k: int = 5

    # ── Bedrock ───────────────────────────────────────────────────────────────
    bedrock_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
