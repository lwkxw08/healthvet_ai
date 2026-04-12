"""Auth hardening service: account lockout, password reset tokens, token blacklist, input sanitisation."""
import hashlib
import html
import re
import secrets
from datetime import datetime, timedelta, timezone

from app.database import get_db
from app.utils.auth import generate_id, hash_password


# ── Constants ───────────────────────────────────────────────────────────────
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15
PASSWORD_RESET_TOKEN_EXPIRY_HOURS = 1


# ── Account Lockout ─────────────────────────────────────────────────────────

def record_login_attempt(email: str, user_type: str, ip_address: str, success: bool) -> None:
    """Record a login attempt and update the lockout counter on the user row."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "INSERT INTO login_attempts (id, email, user_type, ip_address, success, created_at) VALUES (%s,%s,%s,%s,%s,%s)",
            (generate_id(), email, user_type, ip_address, 1 if success else 0, now),
        )

        table = _user_table(user_type)
        if not table:
            return

        if success:
            db.execute(f"UPDATE {table} SET failed_login_attempts=0, locked_until=NULL, last_login_at=%s WHERE email=%s", (now, email))
        else:
            db.execute(f"UPDATE {table} SET failed_login_attempts = COALESCE(failed_login_attempts,0)+1 WHERE email=%s", (email,))
            # Check if we should lock the account
            db.execute(f"SELECT failed_login_attempts FROM {table} WHERE email=%s", (email,))
            row = db.fetchone()
            if row and row["failed_login_attempts"] >= MAX_FAILED_ATTEMPTS:
                lock_until = (datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)).isoformat()
                db.execute(f"UPDATE {table} SET locked_until=%s WHERE email=%s", (lock_until, email))


def is_account_locked(email: str, user_type: str) -> bool:
    """Check whether the account is currently locked."""
    table = _user_table(user_type)
    if not table:
        return False
    with get_db() as db:
        db.execute(f"SELECT locked_until FROM {table} WHERE email=%s", (email,))
        row = db.fetchone()
        if not row or not row["locked_until"]:
            return False
        locked_until = datetime.fromisoformat(row["locked_until"]).replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) >= locked_until:
            # Auto-unlock
            db.execute(f"UPDATE {table} SET locked_until=NULL, failed_login_attempts=0 WHERE email=%s", (email,))
            return False
        return True


def _user_table(user_type: str) -> str | None:
    return {"candidate": "candidates", "agency": "agencies", "admin": "admin_users"}.get(user_type)


# ── Password Reset Tokens ───────────────────────────────────────────────────

def create_password_reset_token(user_id: str, user_type: str) -> str:
    """Generate a one-time password reset token (returned in plaintext, stored hashed)."""
    raw_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(hours=PASSWORD_RESET_TOKEN_EXPIRY_HOURS)).isoformat()
    with get_db() as db:
        # Invalidate any previous tokens for this user
        db.execute("DELETE FROM password_reset_tokens WHERE user_id=%s AND user_type=%s", (user_id, user_type))
        db.execute(
            "INSERT INTO password_reset_tokens (id, user_id, user_type, token_hash, expires_at) VALUES (%s,%s,%s,%s,%s)",
            (generate_id(), user_id, user_type, token_hash, expires_at),
        )
    return raw_token


def validate_password_reset_token(raw_token: str) -> dict | None:
    """Validate a reset token. Returns {user_id, user_type} or None."""
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM password_reset_tokens WHERE token_hash=%s AND used_at IS NULL AND expires_at>%s",
            (token_hash, now),
        )
        row = db.fetchone()
        if not row:
            return None
        return {"user_id": row["user_id"], "user_type": row["user_type"], "token_id": row["id"]}


def consume_password_reset_token(token_id: str) -> None:
    """Mark a reset token as used."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("UPDATE password_reset_tokens SET used_at=%s WHERE id=%s", (now, token_id))


# ── Token Blacklist (Logout) ────────────────────────────────────────────────

def blacklist_token(token_jti: str, user_id: str, expires_at: str) -> None:
    """Add a JWT to the blacklist so it can no longer be used."""
    with get_db() as db:
        db.execute(
            "INSERT OR IGNORE INTO token_blacklist (id, token_jti, user_id, expires_at) VALUES (%s,%s,%s,%s)",
            (generate_id(), token_jti, user_id, expires_at),
        )


def is_token_blacklisted(token_jti: str) -> bool:
    """Check if a token has been revoked."""
    with get_db() as db:
        db.execute("SELECT 1 FROM token_blacklist WHERE token_jti=%s", (token_jti,))
        row = db.fetchone()
        return row is not None


def cleanup_expired_blacklist() -> int:
    """Remove expired entries from the blacklist. Returns count removed."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        cursor = db.execute("DELETE FROM token_blacklist WHERE expires_at<%s", (now,))
        return cursor.rowcount


# ── Input Sanitisation ──────────────────────────────────────────────────────

def sanitise_string(value: str) -> str:
    """Sanitise a string against XSS — HTML-encode dangerous characters."""
    if not value:
        return value
    return html.escape(value, quote=True)


def sanitise_dict(data: dict, fields: list[str] | None = None) -> dict:
    """Sanitise all string values in a dict (or only specified fields)."""
    result = dict(data)
    for key, val in result.items():
        if isinstance(val, str) and (fields is None or key in fields):
            result[key] = sanitise_string(val)
    return result


# ── Password Strength Validation ────────────────────────────────────────────

def validate_password_strength(password: str) -> list[str]:
    """Return a list of issues with the password. Empty list = OK."""
    issues: list[str] = []
    if len(password) < 8:
        issues.append("Password must be at least 8 characters")
    if not re.search(r"[A-Z]", password):
        issues.append("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        issues.append("Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        issues.append("Password must contain at least one digit")
    return issues
