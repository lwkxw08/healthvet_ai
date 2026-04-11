import os
import uuid
from datetime import datetime, timedelta, timezone
import bcrypt
from jose import jwt, JWTError
from fastapi import HTTPException, Depends, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.database import get_db

SECRET_KEY = os.environ.get("JWT_SECRET", "")
if not SECRET_KEY:
    import warnings
    warnings.warn(
        "JWT_SECRET environment variable is not set — using an auto-generated key. "
        "Sessions will NOT survive server restarts. Set JWT_SECRET in production!",
        stacklevel=2,
    )
    import secrets as _secrets
    SECRET_KEY = _secrets.token_urlsafe(64)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

security = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def create_access_token(user_id: str, user_type: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    payload = {
        "sub": user_id,
        "type": user_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )


def get_current_user(request: Request, credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    # First check X-Auth-Token header (used when Authorization is needed for tunnel Basic Auth)
    x_auth_token = request.headers.get("X-Auth-Token")
    if x_auth_token:
        return decode_token(x_auth_token)
    # Fall back to standard Authorization: Bearer header
    if credentials:
        return decode_token(credentials.credentials)
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
            row = db.execute(
                "SELECT 1 FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
                (current_user["sub"], candidate_id),
            ).fetchone()
            if not row:
                raise HTTPException(
                    status_code=403,
                    detail="This candidate is not assigned to your agency",
                )
        return
    raise HTTPException(status_code=403, detail="Not authorized")
