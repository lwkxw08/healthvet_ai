"""Candidate management routes."""
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.utils.auth import get_current_user, verify_agency_owns_candidate
from app.schemas.candidates import CandidateResponse, CandidateUpdate

router = APIRouter(prefix="/api/candidates", tags=["Candidates"])


@router.get("/me", response_model=CandidateResponse)
async def get_my_profile(current_user: dict = Depends(get_current_user)):
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    with get_db() as db:
        row = db.execute("SELECT * FROM candidates WHERE id=?", (current_user["sub"],)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return dict(row)


@router.put("/me", response_model=CandidateResponse)
async def update_my_profile(data: CandidateUpdate, current_user: dict = Depends(get_current_user)):
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{k}=?" for k in updates.keys())
    values = list(updates.values()) + [current_user["sub"]]

    with get_db() as db:
        db.execute(f"UPDATE candidates SET {set_clause} WHERE id=?", values)
        row = db.execute("SELECT * FROM candidates WHERE id=?", (current_user["sub"],)).fetchone()
        return dict(row)


@router.get("", response_model=list[CandidateResponse])
async def list_candidates(current_user: dict = Depends(get_current_user)):
    """List candidates - for agencies and admin."""
    if current_user["type"] not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Agencies and admin only")

    with get_db() as db:
        if current_user["type"] == "agency":
            rows = db.execute(
                """SELECT c.* FROM candidates c
                   JOIN agency_candidates ac ON c.id = ac.candidate_id
                   WHERE ac.agency_id=?
                   ORDER BY c.created_at DESC""",
                (current_user["sub"],),
            ).fetchall()
        else:
            rows = db.execute("SELECT * FROM candidates ORDER BY created_at DESC").fetchall()

        return [dict(r) for r in rows]


@router.get("/{candidate_id}", response_model=CandidateResponse)
async def get_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    with get_db() as db:
        row = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found")
        return dict(row)


@router.post("/{candidate_id}/assign-agency/{agency_id}")
async def assign_to_agency(candidate_id: str, agency_id: str, current_user: dict = Depends(get_current_user)):
    """Assign a candidate to an agency."""
    if current_user["type"] not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Not authorized")

    with get_db() as db:
        try:
            db.execute(
                "INSERT INTO agency_candidates (agency_id, candidate_id) VALUES (?, ?)",
                (agency_id, candidate_id),
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Assignment already exists")

    return {"message": "Candidate assigned to agency"}
