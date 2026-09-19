"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar

import structlog

request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def add_request_id(
    logger: logging.Logger,  # noqa: ARG001
    method: str,  # noqa: ARG001
    event_dict: dict,
) -> dict:
    """Inject the current request ID into every log record."""
    rid = request_id_var.get("")
    if rid:
        event_dict["request_id"] = rid
    return event_dict


def configure_logging(debug: bool = False) -> None:
    """Wire up structlog with JSON output for production, pretty output for dev."""
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        add_request_id,
    ]

    if debug:
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.DEBUG if debug else logging.INFO)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a named structlog logger."""
    return structlog.get_logger(name)


def new_request_id() -> str:
    """Generate and store a fresh request ID in the context var."""
    rid = str(uuid.uuid4())
    request_id_var.set(rid)
    return rid
