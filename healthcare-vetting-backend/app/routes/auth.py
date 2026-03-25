"""Authentication routes for candidates and agencies."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request, status
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
        existing = db.execute("SELECT id FROM candidates WHERE email=?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        # If invite_code provided, validate it
        invite = None
        if data.invite_code:
            invite_row = db.execute(
                "SELECT * FROM agency_invites WHERE invite_code=? AND status='pending'",
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
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
                "INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at) VALUES (?, ?, ?)",
                (invite["agency_id"], candidate_id, now),
            )
            db.execute(
                "UPDATE agency_invites SET status='accepted', candidate_id=?, accepted_at=? WHERE id=?",
                (candidate_id, now, invite["id"]),
            )

    token = create_access_token(candidate_id, "candidate")
    return TokenResponse(access_token=token, user_type="candidate", user_id=candidate_id)


@router.post("/candidates/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_candidate(request: Request, data: CandidateLogin):
    with get_db() as db:
        user = db.execute("SELECT * FROM candidates WHERE email=?", (data.email,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_dict = dict(user)
        if not verify_password(data.password, user_dict["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_dict["id"], "candidate")
    return TokenResponse(access_token=token, user_type="candidate", user_id=user_dict["id"])


@router.post("/agencies/register", response_model=TokenResponse)
@limiter.limit("5/minute")
async def register_agency(request: Request, data: AgencyCreate):
    with get_db() as db:
        existing = db.execute("SELECT id FROM agencies WHERE email=?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email already registered")

        agency_id = generate_id()
        db.execute(
            """INSERT INTO agencies
               (id, name, email, password_hash, contact_name, phone, plan)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
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
    with get_db() as db:
        user = db.execute("SELECT * FROM agencies WHERE email=?", (data.email,)).fetchone()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        user_dict = dict(user)
        if not verify_password(data.password, user_dict["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user_dict["id"], "agency")
    return TokenResponse(access_token=token, user_type="agency", user_id=user_dict["id"])


@router.post("/admin/login", response_model=TokenResponse)
@limiter.limit("5/minute")
async def login_admin(request: Request, data: CandidateLogin):
    """Admin login with hardcoded credentials for demo."""
    if data.email == "admin@healthvet.ai" and data.password == "admin123":
        token = create_access_token("admin", "admin")
        return TokenResponse(access_token=token, user_type="admin", user_id="admin")
    raise HTTPException(status_code=401, detail="Invalid admin credentials")


@router.post("/token/refresh", response_model=TokenResponse)
@limiter.limit("10/minute")
async def refresh_token(request: Request, current_user: dict = None):
    """Refresh an access token. Requires a valid (non-expired) token."""
    from fastapi import Depends
    from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
    # Extract token from Authorization header or X-Auth-Token
    x_auth_token = request.headers.get("X-Auth-Token")
    auth_header = request.headers.get("Authorization")
    token = None
    if x_auth_token:
        token = x_auth_token
    elif auth_header and auth_header.startswith("Bearer "):
        token = auth_header[7:]
    if not token:
        raise HTTPException(status_code=401, detail="No token provided")
    payload = decode_token(token)
    user_id = payload.get("sub")
    user_type = payload.get("type")
    if not user_id or not user_type:
        raise HTTPException(status_code=401, detail="Invalid token payload")
    new_token = create_access_token(user_id, user_type)
    return TokenResponse(access_token=new_token, user_type=user_type, user_id=user_id)
