"""1.5 Multi-Tenancy: Agency scope middleware enforcing agency_id isolation on all agency endpoints."""
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.utils.auth import decode_token


class AgencyScopeMiddleware(BaseHTTPMiddleware):
    """Extracts agency_id from the JWT for agency users and injects it into request.state.
    All agency-scoped endpoints can then use request.state.agency_id to enforce row-level filtering."""

    async def dispatch(self, request: Request, call_next):
        # Only apply to API routes
        path = request.url.path
        if not path.startswith("/api/"):
            return await call_next(request)

        # Skip public endpoints that don't need auth
        public_paths = [
            "/api/auth/",
            "/api/info",
            "/api/verify",
            "/healthz",
        ]
        if any(path.startswith(p) for p in public_paths):
            return await call_next(request)

        # Extract token from headers
        token = None
        x_auth = request.headers.get("X-Auth-Token")
        auth_header = request.headers.get("Authorization")
        if x_auth:
            token = x_auth
        elif auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]

        if token:
            try:
                payload = decode_token(token)
                user_type = payload.get("type")
                user_id = payload.get("sub")

                # Inject identity into request.state for all authenticated users
                request.state.user_id = user_id
                request.state.user_type = user_type

                if user_type == "agency":
                    request.state.agency_id = user_id
                elif user_type == "admin":
                    # Admins can optionally scope to an agency via query param
                    agency_filter = request.query_params.get("agency_id")
                    request.state.agency_id = agency_filter  # None = see all
                elif user_type == "candidate":
                    request.state.agency_id = None
                    request.state.candidate_id = user_id
            except HTTPException:
                # Token decode failed — let the route handler deal with auth
                pass

        response = await call_next(request)
        return response


def get_agency_id(request: Request) -> str:
    """Helper: extract agency_id from request.state. Raises 403 if not an agency user."""
    agency_id = getattr(request.state, "agency_id", None)
    user_type = getattr(request.state, "user_type", None)
    if user_type == "admin":
        return agency_id  # May be None (admin sees all)
    if not agency_id:
        raise HTTPException(status_code=403, detail="Agency scope required")
    return agency_id


def require_agency_scope(request: Request) -> str:
    """Stricter version: always requires a valid agency_id (even for admin with ?agency_id=)."""
    agency_id = getattr(request.state, "agency_id", None)
    if not agency_id:
        raise HTTPException(status_code=403, detail="Agency ID required for this operation")
    return agency_id
