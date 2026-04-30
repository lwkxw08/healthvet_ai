"""
API versioning middleware.

Supports /api/v1/... as the canonical versioned prefix. Requests to /api/v1/...
are rewritten to /api/... so existing route handlers work unchanged.

The unversioned /api/... paths remain as a backward-compatible alias but should
be considered deprecated for external integrations.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("viperai.versioning")


class APIVersioningMiddleware(BaseHTTPMiddleware):
    """Rewrite /api/v1/* → /api/* so versioned URLs hit existing handlers."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope.get("path", "")

        if path.startswith("/api/v1/"):
            # Rewrite versioned path to unversioned
            new_path = "/api/" + path[len("/api/v1/"):]
            request.scope["path"] = new_path
            # Also update raw_path if present
            if "raw_path" in request.scope:
                request.scope["raw_path"] = new_path.encode("utf-8")

        response = await call_next(request)

        # Add API version header to all /api responses
        if path.startswith("/api/"):
            response.headers["X-API-Version"] = "v1"
            response.headers["Deprecation"] = "false"

        return response
