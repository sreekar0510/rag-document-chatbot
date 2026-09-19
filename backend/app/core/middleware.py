"""Request ID middleware – injects a unique ID into every request context."""

from __future__ import annotations

import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import request_id_var


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Attach a unique X-Request-ID to every request and response."""

    async def dispatch(self, request: Request, call_next) -> Response:  # type: ignore[override]
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
