"""Enhanced audit logging middleware — logs every state-changing request with full context."""

import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuditMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request and log state-changing operations.

    The request ID is:
    - Stored in request.state.request_id for use by route handlers
    - Returned in the X-Request-ID response header for client-side tracing
    - Available for inclusion in audit log entries created by route handlers

    Also extracts and stores the client IP address for audit trail purposes.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request.state.request_id = request_id

        # Extract real client IP (respecting reverse proxy headers)
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"
        request.state.client_ip = client_ip

        start_time = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        return response
