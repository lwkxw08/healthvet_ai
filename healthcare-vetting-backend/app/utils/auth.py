import os
import secrets as _stdlib_secrets
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db

# ── JWT key management (supports key versioning / rotation) ──────────────
# JWT_SECRET is the *current* signing key.
# JWT_SECRET_PREVIOUS (optional) is accepted for verification only, allowing
# zero-downtime rotation: set a new JWT_SECRET, copy the old one to
# JWT_SECRET_PREVIOUS, redeploy.  Tokens signed with the old key remain
# valid until they expire; new tokens use the new key.
SECRET_KEY = os.environ.get("JWT_SECRET", "")
if not SECRET_KEY:
    import warnings
    warnings.warn(
        "JWT_SECRET environment variable is not set — using an auto-generated key. "
        "Sessions will NOT survive server restarts. Set JWT_SECRET in production!",
        stacklevel=2,
    )
    SECRET_KEY = _stdlib_secrets.token_urlsafe(64)

_PREVIOUS_SECRET = os.environ.get("JWT_SECRET_PREVIOUS", "")
ALGORITHM = "HS256"

# Short-lived access tokens (15 min) — session maintained via httpOnly refresh cookie
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.environ.get("REFRESH_TOKEN_EXPIRE_DAYS", "7"))
# Backwards compat: keep the old constant for any code that references it
ACCESS_TOKEN_EXPIRE_HOURS = ACCESS_TOKEN_EXPIRE_MINUTES / 60

security = HTTPBearer(auto_error=False)

# ── Cookie configuration ─────────────────────────────────────────────────
_IS_PRODUCTION = os.environ.get("RAILWAY_ENVIRONMENT", "") == "production" or \
                 os.environ.get("ENVIRONMENT", "").lower() == "production"
COOKIE_SECURE = _IS_PRODUCTION  # True in production (HTTPS only)
COOKIE_SAMESITE = "lax"
COOKIE_HTTPONLY = True
COOKIE_DOMAIN = os.environ.get("COOKIE_DOMAIN", None)  # e.g. ".viperai.io"
REFRESH_COOKIE_NAME = "viperai_refresh"
CSRF_COOKIE_NAME = "viperai_csrf"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str, user_type: str, *, impersonator_id: str | None = None) -> str:
    """Create a short-lived access token (15 min default).

    If impersonator_id is set, the token represents an admin viewing as another user.
    The 'imp' claim records the admin's ID for audit purposes.
    """
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": user_id,
        "type": user_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
    }
    if impersonator_id:
        payload["imp"] = impersonator_id
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: str, user_type: str) -> str:
    """Create a long-lived refresh token (7 days default) for httpOnly cookie."""
    expire = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": user_id,
        "type": user_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid.uuid4()),
        "token_type": "refresh",
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def generate_csrf_token() -> str:
    """Generate a random CSRF token."""
    return _stdlib_secrets.token_urlsafe(32)


def decode_token(token: str) -> dict:
    """Decode a JWT, trying the current key first then the previous key for rotation."""
    for key in (SECRET_KEY, _PREVIOUS_SECRET) if _PREVIOUS_SECRET else (SECRET_KEY,):
        try:
            payload = jwt.decode(token, key, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            continue
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )


def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    # 1. Check X-Auth-Token header (used when Authorization is needed for tunnel Basic Auth)
    x_auth_token = request.headers.get("X-Auth-Token")
    if x_auth_token:
        return decode_token(x_auth_token)
    # 2. Standard Authorization: Bearer header
    if credentials:
        return decode_token(credentials.credentials)
    # 3. Fall back to httpOnly refresh cookie (for cookie-based auth)
    refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh:
        payload = decode_token(refresh)
        if payload.get("token_type") == "refresh":
            return payload
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
    )


def get_current_admin(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """Get current user and verify they are an admin."""
    user = get_current_user(request, credentials)
    if user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def generate_id() -> str:
    return str(uuid.uuid4())


def verify_agency_owns_candidate(current_user: dict, candidate_id: str) -> None:
    """Verify that an agency user has access to a specific candidate.
    Admins and candidates always pass. Agencies must have the candidate assigned."""
    user_type = current_user.get("type")
    if user_type == "admin":
        return
    if user_type == "candidate":
        # Candidates can only access their own data
        if current_user["sub"] != candidate_id:
            raise HTTPException(status_code=403, detail="You can only access your own data")
        return
    if user_type == "agency":
        with get_db() as db:
            db.execute(
                "SELECT 1 FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
                (current_user["sub"], candidate_id),
            )
            row = db.fetchone()
            if not row:
                raise HTTPException(
                    status_code=403,
                    detail="This candidate is not assigned to your agency",
                )
        return
    raise HTTPException(status_code=403, detail="Not authorized")
