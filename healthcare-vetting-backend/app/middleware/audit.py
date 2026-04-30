"""Enhanced audit logging middleware — logs every request with structured context."""

import logging
import uuid
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("viperai.http")


class AuditMiddleware(BaseHTTPMiddleware):
    """Attach a unique request ID to every request, log structured HTTP context.

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

        # Structured request log (skip health checks and static files)
        path = request.url.path
        if not path.startswith(("/health", "/static", "/favicon")):
            logger.info(
                "%s %s %s %.0fms",
                request.method, path, response.status_code, duration_ms,
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "ip": client_ip,
                    "http": {
                        "method": request.method,
                        "url": str(request.url),
                        "status_code": response.status_code,
                        "user_agent": request.headers.get("user-agent", ""),
                    },
                },
            )

        return response
