"""Rate limiting middleware using slowapi.

Configures per-endpoint rate limits to prevent brute force attacks and abuse.
"""

import os
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.requests import Request
from starlette.responses import JSONResponse


def _key_func(request: Request) -> str:
    """Extract client IP for rate limiting, respecting X-Forwarded-For behind proxies."""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


# Global limiter instance — imported by route modules to apply per-endpoint limits
_enabled = os.environ.get("RATE_LIMIT_ENABLED", "1") not in ("0", "false", "no")
limiter = Limiter(
    key_func=_key_func,
    default_limits=[
        os.environ.get("RATE_LIMIT_DEFAULT", "100/minute"),
    ],
    storage_uri=os.environ.get("RATE_LIMIT_STORAGE", "memory://"),
    enabled=_enabled,
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return 429 with Retry-After header when rate limit is exceeded."""
    retry_after = getattr(exc, "retry_after", 60)
    return JSONResponse(
        status_code=429,
        content={
            "detail": f"Rate limit exceeded: {exc.detail}",
            "retry_after": retry_after,
        },
        headers={"Retry-After": str(retry_after)},
    )
