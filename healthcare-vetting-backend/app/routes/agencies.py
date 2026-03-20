"""Agency management and invite routes."""
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.utils.auth import get_current_user, generate_id
from app.schemas.agencies import InviteCreate, InviteResponse

router = APIRouter(prefix="/api/agencies", tags=["Agencies"])


@router.post("/invites", response_model=InviteResponse)
async def create_invite(data: InviteCreate, current_user: dict = Depends(get_current_user)):
    """Agency creates an invite for a candidate email."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    invite_code = secrets.token_urlsafe(16)
    invite_id = generate_id()

    with get_db() as db:
        # Get agency name for the response
        agency_row = db.execute("SELECT name FROM agencies WHERE id=?", (agency_id,)).fetchone()
        agency_name = dict(agency_row)["name"] if agency_row else "Unknown Agency"

        # Check if there's already a pending invite for this email from this agency
        existing = db.execute(
            "SELECT id FROM agency_invites WHERE agency_id=? AND candidate_email=? AND status='pending'",
            (agency_id, data.candidate_email),
        ).fetchone()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="A pending invite already exists for this email",
            )

        db.execute(
            """INSERT INTO agency_invites (id, agency_id, candidate_email, invite_code, status, created_at)
               VALUES (?, ?, ?, ?, 'pending', ?)""",
            (invite_id, agency_id, data.candidate_email, invite_code, datetime.now(timezone.utc).isoformat()),
        )

    return InviteResponse(
        id=invite_id,
        agency_id=agency_id,
        agency_name=agency_name,
        candidate_email=data.candidate_email,
        invite_code=invite_code,
        status="pending",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


@router.get("/invites", response_model=list[InviteResponse])
async def list_invites(current_user: dict = Depends(get_current_user)):
    """List all invites created by the current agency."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    with get_db() as db:
        agency_row = db.execute("SELECT name FROM agencies WHERE id=?", (agency_id,)).fetchone()
        agency_name = dict(agency_row)["name"] if agency_row else "Unknown Agency"

        rows = db.execute(
            "SELECT * FROM agency_invites WHERE agency_id=? ORDER BY created_at DESC",
            (agency_id,),
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["agency_name"] = agency_name
            results.append(d)
        return results


@router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke a pending invite."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM agency_invites WHERE id=? AND agency_id=?",
            (invite_id, current_user["sub"]),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invite not found")
        invite = dict(row)
        if invite["status"] != "pending":
            raise HTTPException(status_code=400, detail="Can only revoke pending invites")

        db.execute(
            "UPDATE agency_invites SET status='revoked' WHERE id=?",
            (invite_id,),
        )

    return {"status": "revoked"}


@router.get("/invite-info/{invite_code}")
async def get_invite_info(invite_code: str):
    """Public endpoint: get invite details by code (for registration page)."""
    with get_db() as db:
        row = db.execute(
            """SELECT ai.*, a.name as agency_name FROM agency_invites ai
               JOIN agencies a ON ai.agency_id = a.id
               WHERE ai.invite_code=? AND ai.status='pending'""",
            (invite_code,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invalid or expired invite code")

        invite = dict(row)
        return {
            "invite_code": invite["invite_code"],
            "agency_name": invite["agency_name"],
            "candidate_email": invite["candidate_email"],
        }


@router.post("/invites/{invite_code}/accept")
async def accept_invite(invite_code: str, current_user: dict = Depends(get_current_user)):
    """Candidate accepts an invite, linking them to the agency."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM agency_invites WHERE invite_code=? AND status='pending'",
            (invite_code,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invalid or expired invite code")

        invite = dict(row)

        # Verify the candidate email matches the invite
        candidate_row = db.execute(
            "SELECT email FROM candidates WHERE id=?",
            (candidate_id,),
        ).fetchone()
        if candidate_row:
            candidate_email = dict(candidate_row)["email"]
            if candidate_email.lower() != invite["candidate_email"].lower():
                raise HTTPException(
                    status_code=400,
                    detail="This invite was sent to a different email address",
                )

        # Check if already assigned
        existing = db.execute(
            "SELECT 1 FROM agency_candidates WHERE agency_id=? AND candidate_id=?",
            (invite["agency_id"], candidate_id),
        ).fetchone()
        if existing:
            # Already assigned, just update invite status
            db.execute(
                "UPDATE agency_invites SET status='accepted', candidate_id=?, accepted_at=? WHERE id=?",
                (candidate_id, now, invite["id"]),
            )
            return {"status": "already_assigned", "message": "You are already linked to this agency"}

        # Link candidate to agency
        db.execute(
            "INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at) VALUES (?, ?, ?)",
            (invite["agency_id"], candidate_id, now),
        )

        # Update invite status
        db.execute(
            "UPDATE agency_invites SET status='accepted', candidate_id=?, accepted_at=? WHERE id=?",
            (candidate_id, now, invite["id"]),
        )

    return {"status": "accepted", "message": "You have been linked to the agency. Complete your vetting checks to proceed."}


@router.get("/my-agencies")
async def get_my_agencies(current_user: dict = Depends(get_current_user)):
    """Get agencies that a candidate is linked to."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    with get_db() as db:
        rows = db.execute(
            """SELECT a.id, a.name, a.email, a.contact_name, ac.assigned_at
               FROM agencies a
               JOIN agency_candidates ac ON a.id = ac.agency_id
               WHERE ac.candidate_id=?""",
            (current_user["sub"],),
        ).fetchall()
        return [dict(r) for r in rows]


@router.get("/pending-invites")
async def get_pending_invites(current_user: dict = Depends(get_current_user)):
    """Get pending invites for the current candidate (by their email)."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    with get_db() as db:
        candidate_row = db.execute(
            "SELECT email FROM candidates WHERE id=?", (current_user["sub"],)
        ).fetchone()
        if not candidate_row:
            return []

        candidate_email = dict(candidate_row)["email"]
        rows = db.execute(
            """SELECT ai.*, a.name as agency_name FROM agency_invites ai
               JOIN agencies a ON ai.agency_id = a.id
               WHERE ai.candidate_email=? AND ai.status='pending'""",
            (candidate_email,),
        ).fetchall()
        return [dict(r) for r in rows]
