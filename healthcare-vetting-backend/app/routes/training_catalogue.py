"""Training catalogue API routes.

Two groupings:
  - Public (candidate/agency-readable): GET the catalogue + per-candidate view
  - Admin: CRUD courses, CSV import, set per-industry training policy

Phase 1-4 of the training overhaul.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Body, UploadFile, File, Form
from pydantic import BaseModel

from app.utils.auth import get_current_user
from app.services import training_catalogue as tc


router = APIRouter(tags=["Training Catalogue"])


# ── Public (read) ────────────────────────────────────────────────

@router.get("/api/training-courses")
async def list_training_courses(
    industry_template_id: Optional[str] = Query(None),
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """List training courses. Filter by industry_template_id if provided.
    Candidates / agencies see active-only by default."""
    if not (current_user.get("type") == "admin") and include_inactive:
        include_inactive = False
    courses = tc.list_courses(
        industry_template_id=industry_template_id,
        include_inactive=include_inactive,
    )
    return {"courses": courses}


@router.get("/api/training-courses/for-candidate/{candidate_id}")
async def courses_for_candidate(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Return the courses applicable to a candidate based on their agency's
    industry template, plus the current training policy."""
    # Candidates can only view their own; admin/agency always can
    if current_user.get("type") == "candidate" and current_user.get("sub") != candidate_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return tc.list_courses_for_candidate(candidate_id)


@router.get("/api/training-courses/self")
async def courses_for_self(current_user: dict = Depends(get_current_user)):
    """Convenience endpoint for the candidate UI — returns the courses for
    the currently authenticated candidate."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Candidate only")
    return tc.list_courses_for_candidate(current_user["sub"])


# ── Admin (write) ────────────────────────────────────────────────

class CreateCourseIn(BaseModel):
    industry_template_id: str
    name: str
    aliases: list[str] = []
    category: str = "mandatory"
    description: Optional[str] = None
    default_validity_months: int = 12
    is_mandatory: bool = False
    is_active: bool = True
    sort_order: int = 0


class UpdateCourseIn(BaseModel):
    name: Optional[str] = None
    aliases: Optional[list[str]] = None
    category: Optional[str] = None
    description: Optional[str] = None
    default_validity_months: Optional[int] = None
    is_mandatory: Optional[bool] = None
    is_active: Optional[bool] = None
    sort_order: Optional[int] = None
    industry_template_id: Optional[str] = None


def _require_admin(current_user: dict) -> None:
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


@router.post("/api/admin/training-courses")
async def create_training_course(
    body: CreateCourseIn,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    course = tc.create_course(**body.model_dump())
    return course


@router.patch("/api/admin/training-courses/{course_id}")
async def update_training_course(
    course_id: str,
    body: UpdateCourseIn,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = tc.get_course(course_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Course not found")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    return tc.update_course(course_id, **updates)


@router.delete("/api/admin/training-courses/{course_id}")
async def delete_training_course(
    course_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    existing = tc.get_course(course_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Course not found")
    tc.delete_course(course_id)
    return {"deleted": True, "id": course_id}


@router.post("/api/admin/training-courses/import")
async def import_training_courses(
    industry_template_id: str = Form(...),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        raw = await file.read()
        csv_text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")
    result = tc.import_courses_csv(industry_template_id, csv_text)
    return result


class SetPolicyIn(BaseModel):
    policy: str  # "pass_fail" | "informational"


@router.get("/api/admin/industry-templates/{template_id}/training-policy")
async def get_training_policy(
    template_id: str,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    return {
        "industry_template_id": template_id,
        "training_policy": tc.get_training_policy(template_id),
    }


@router.patch("/api/admin/industry-templates/{template_id}/training-policy")
async def set_training_policy(
    template_id: str,
    body: SetPolicyIn,
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    try:
        return tc.set_training_policy(template_id, body.policy)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
