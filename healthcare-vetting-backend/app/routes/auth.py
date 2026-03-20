"""Authentication routes for candidates and agencies."""
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.utils.auth import hash_password, verify_password, create_access_token, generate_id
from app.schemas.candidates import CandidateCreate, CandidateLogin, TokenResponse
from app.schemas.agencies import AgencyCreate, AgencyLogin


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
async def register_candidate(data: CandidateRegisterWithInvite):
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
async def login_candidate(data: CandidateLogin):
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
async def register_agency(data: AgencyCreate):
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
async def login_agency(data: AgencyLogin):
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
async def login_admin(data: CandidateLogin):
    """Admin login with hardcoded credentials for demo."""
    if data.email == "admin@healthvet.ai" and data.password == "admin123":
        token = create_access_token("admin", "admin")
        return TokenResponse(access_token=token, user_type="admin", user_id="admin")
    raise HTTPException(status_code=401, detail="Invalid admin credentials")
