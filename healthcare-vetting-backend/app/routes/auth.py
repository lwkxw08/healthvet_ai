"""Authentication routes for candidates and agencies."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.utils.auth import (
    hash_password, verify_password, create_access_token, generate_id,
    decode_token, get_current_user,
)
from app.schemas.candidates import CandidateCreate, CandidateLogin, TokenResponse
from app.schemas.agencies import AgencyCreate, AgencyLogin
from app.middleware.rate_limiter import limiter
from app.services.auth_hardening import (
    record_login_attempt, is_account_locked,
    create_password_reset_token, validate_password_reset_token,
    consume_password_reset_token, blacklist_token, is_token_blacklisted,
    sanitise_string, validate_password_strength,
)


class CandidateRegisterWithInvite(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    profession: Optional[str] = None
    registration_number: Optional[str] = None
    registration_body: Optional[str] = None
    invite_code: Optional[str] = None

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post("/candidates/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register_candidate(request: Request, data: CandidateRegisterWithInvite):
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        existing = db.execute("SELECT id FROM candidates WHERE email=%s", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # If invite_code provided, validate it
        invite = None
        if data.invite_code:
            invite_row = db.execute(
                "SELECT * FROM agency_invites WHERE invite_code=%s AND status='pending'",
                (data.invite_code,),
            ).fetchone()
            if not invite_row:
                raise HTTPException(status_code=400, detail="Invalid or expired invite code")
            invite = dict(invite_row)
            # Verify email matches the invite
            if invite["candidate_email"].lower() != data.email.lower():
                raise HTTPException(
                    status_code=400,
                    detail="Email does not match the invite. Please use the email the invite was sent to.",
                )

        candidate_id = generate_id()
        db.execute(
            """INSERT INTO candidates
               (id, email, password_hash, first_name, last_name, phone,
                date_of_birth, address_line1, address_line2, city, postcode,
                profession, registration_number, registration_body)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                candidate_id, data.email, hash_password(data.password),
                data.first_name, data.last_name, data.phone,
                data.date_of_birth, data.address_line1, data.address_line2,
                data.city, data.postcode, data.profession,
                data.registration_number, data.registration_body,
            ),
        )

        # If invite code provided, link candidate to agency automatically
        if invite:
            db.execute(
                "INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at) VALUES (%s, %s, %s)",
                (invite["agency_id"], candidate_id, now),
            )
            db.execute(
                "UPDATE agency_invites SET status='accepted', candidate_id=%s, accepted_at=%s WHERE id=%s",
                (candidate_id, now, invite["id"]),
            )

    token = create_access_token(candidate_id, "candidate")
    return TokenResponse(access_token=token, user_type="candidate", user_id=candidate_id)


@router.post("/candidates/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_candidate(request: Request, data: CandidateLogin):
    ip = request.client.host if request.client else "unknown"
    # Check account lockout
    if is_account_locked(data.email, "candidate"):
        raise HTTPException(status_code=423, detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.")

    with get_db() as db:
        user = db.execute("SELECT * FROM candidates WHERE email=%s", (data.email,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_dict = dict(user)
        if not verify_password(data.password, user_dict["password_hash"]):
            record_login_attempt(data.email, "candidate", ip, False)
            raise HTTPException(status_code=401, detail="Invalid credentials")

    record_login_attempt(data.email, "candidate", ip, True)
    token = create_access_token(user_dict["id"], "candidate")
    return TokenResponse(access_token=token, user_type="candidate", user_id=user_dict["id"])


@router.post("/agencies/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register_agency(request: Request, data: AgencyCreate):
    with get_db() as db:
        existing = db.execute("SELECT id FROM agencies WHERE email=%s", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        agency_id = generate_id()
        db.execute(
            """INSERT INTO agencies
               (id, name, email, password_hash, contact_name, phone, plan)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                agency_id, data.name, data.email, hash_password(data.password),
                data.contact_name, data.phone, data.plan,
            ),
        )

    token = create_access_token(agency_id, "agency")
    return TokenResponse(access_token=token, user_type="agency", user_id=agency_id)


@router.post("/agencies/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_agency(request: Request, data: AgencyLogin):
    ip = request.client.host if request.client else "unknown"
    if is_account_locked(data.email, "agency"):
        raise HTTPException(status_code=423, detail="Account temporarily locked due to too many failed attempts. Try again in 15 minutes.")

    with get_db() as db:
        user = db.execute("SELECT * FROM agencies WHERE email=%s", (data.email,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_dict = dict(user)
        if not verify_password(data.password, user_dict["password_hash"]):
            record_login_attempt(data.email, "agency", ip, False)
            raise HTTPException(status_code=401, detail="Invalid credentials")

    record_login_attempt(data.email, "agency", ip, True)
    token = create_access_token(user_dict["id"], "agency")
    return TokenResponse(access_token=token, user_type="agency", user_id=user_dict["id"])


@router.post("/admin/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_admin(request: Request, data: CandidateLogin):
    """Admin login — now uses DB-based admin_users table instead of hardcoded credentials."""
    ip = request.client.host if request.client else "unknown"
    if is_account_locked(data.email, "admin"):
        raise HTTPException(status_code=423, detail="Account temporarily locked. Try again in 15 minutes.")

    with get_db() as db:
        admin = db.execute("SELECT * FROM admin_users WHERE email=%s AND is_active=1", (data.email,)).fetchone()
        if not admin:
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        admin_dict = dict(admin)
        if not verify_password(data.password, admin_dict["password_hash"]):
            record_login_attempt(data.email, "admin", ip, False)
            raise HTTPException(status_code=401, detail="Invalid admin credentials")

    record_login_attempt(data.email, "admin", ip, True)
    token = create_access_token(admin_dict["id"], "admin")
    return TokenResponse(access_token=token, user_type="admin", user_id=admin_dict["id"])


@router.post("/token/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request, current_user: dict = None):
    """Refresh an access token. Requires a valid (non-expired) token."""
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    payload = decode_token(token)
    # Check if token has been blacklisted (logged out)
    token_jti = payload.get("jti") or payload.get("iat", "")
    if is_token_blacklisted(str(token_jti)):
        raise HTTPException(status_code=401, detail="Token has been revoked")
    user_id = payload.get("sub")
    user_type = payload.get("type")
    if not user_id or not user_type:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    new_token = create_access_token(user_id, user_type)
    return TokenResponse(access_token=new_token, user_type=user_type, user_id=user_id)


# ── Password Reset ──────────────────────────────────────────────────────────

class PasswordResetRequest(BaseModel):
    email: str
    user_type: str = "candidate"  # candidate | agency | admin

class PasswordResetConfirm(BaseModel):
    token: str
    new_password: str


@router.post("/password-reset/request")
@limiter.limit("3/minute")
async def request_password_reset(request: Request, data: PasswordResetRequest):
    """Request a password reset token. In production this sends an email; here we return the token for demo."""
    table = {"candidate": "candidates", "agency": "agencies", "admin": "admin_users"}.get(data.user_type)
    if not table:
        raise HTTPException(status_code=400, detail="Invalid user type")

    with get_db() as db:
        user = db.execute(f"SELECT id, email FROM {table} WHERE email=%s", (data.email,)).fetchone()
        if not user:
            # Don't reveal whether email exists — return success either way
            return {"message": "If the email is registered, a reset link has been sent."}
        user = dict(user)

    raw_token = create_password_reset_token(user["id"], data.user_type)

    # In production: send email with reset link containing the token
    # For now: return the token directly (demo mode)
    return {
        "message": "If the email is registered, a reset link has been sent.",
        "_demo_token": raw_token,  # Remove in production
        "_demo_reset_url": f"/reset-password%stoken={raw_token}",
    }


@router.post("/password-reset/confirm")
@limiter.limit("5/minute")
async def confirm_password_reset(request: Request, data: PasswordResetConfirm):
    """Confirm a password reset using the token."""
    # Validate password strength
    issues = validate_password_strength(data.new_password)
    if issues:
        raise HTTPException(status_code=400, detail="; ".join(issues))

    result = validate_password_reset_token(data.token)
    if not result:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    table = {"candidate": "candidates", "agency": "agencies", "admin": "admin_users"}.get(result["user_type"])
    if not table:
        raise HTTPException(status_code=400, detail="Invalid user type")

    new_hash = hash_password(data.new_password)
    with get_db() as db:
        db.execute(f"UPDATE {table} SET password_hash=%s WHERE id=%s", (new_hash, result["user_id"]))

    consume_password_reset_token(result["token_id"])
    return {"message": "Password has been reset successfully"}


# ── Logout (Token Blacklist) ────────────────────────────────────────────────

@router.post("/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """Logout — blacklist the current JWT so it can no longer be used."""
    token = _extract_token(request)
    if token:
        payload = decode_token(token)
        jti = str(payload.get("jti") or payload.get("iat", ""))
        exp = payload.get("exp", "")
        if isinstance(exp, (int, float)):
            from datetime import datetime as dt
            exp = dt.fromtimestamp(exp, tz=timezone.utc).isoformat()
        blacklist_token(jti, current_user["sub"], str(exp))
    return {"message": "Logged out successfully"}


# ── Pre-Notification Endpoints ──────────────────────────────────────────────

class PreNotificationCreate(BaseModel):
    candidate_id: str
    verification_type: str
    verifier_name: str
    verifier_email: str
    verifier_organisation: Optional[str] = None


@router.post("/pre-notifications")
async def create_pre_notification_endpoint(request: Request, data: PreNotificationCreate, current_user: dict = Depends(get_current_user)):
    """Agency creates a pre-notification — candidate is notified before verification request goes to referee."""
    if current_user.get("type") not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Only agencies can create pre-notifications")

    from app.services.candidate_notifications import create_pre_notification
    result = create_pre_notification(
        candidate_id=data.candidate_id,
        verification_type=data.verification_type,
        verifier_name=data.verifier_name,
        verifier_email=data.verifier_email,
        verifier_organisation=data.verifier_organisation,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/pre-notifications/ready")
async def get_ready_pre_notifications(request: Request, current_user: dict = Depends(get_current_user)):
    """Get pre-notifications that are confirmed or past the delay window (ready to send to referee)."""
    if current_user.get("type") not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Agency or admin access required")
    from app.services.candidate_notifications import get_ready_notifications
    return {"notifications": get_ready_notifications()}


def _extract_token(request: Request) -> str | None:
    """Extract JWT from request headers."""
    x_auth = request.headers.get("X-Auth-Token")
    if x_auth:
        return x_auth
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]
    return None
