"""CSRF protection middleware.

When the request is authenticated via cookies (not Bearer token), state-changing
methods (POST/PUT/PATCH/DELETE) must include an X-CSRF-Token header whose value
matches the viperai_csrf cookie set at login.

Requests that use Authorization/X-Auth-Token headers are exempt — they are
not vulnerable to CSRF because cookies are not the authentication mechanism.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.utils.auth import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
_EXEMPT_PATHS = (
    "/api/auth/",
    "/api/webhooks/",
    "/healthz",
)


class CSRFMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in _EXEMPT_PATHS):
            return await call_next(request)

        # Only enforce CSRF when the request relies on cookie auth
        has_bearer = (
            request.headers.get("Authorization", "").startswith("Bearer ")
            or request.headers.get("X-Auth-Token")
        )
        if has_bearer:
            return await call_next(request)

        has_refresh_cookie = request.cookies.get(REFRESH_COOKIE_NAME)
        if not has_refresh_cookie:
            return await call_next(request)

        # Cookie-authenticated mutation → require matching CSRF token
        csrf_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
        csrf_header = request.headers.get("X-CSRF-Token", "")
        if not csrf_cookie or not csrf_header or csrf_cookie != csrf_header:
            return JSONResponse(
                status_code=403,
                content={"detail": "CSRF token missing or invalid"},
            )

        return await call_next(request)
