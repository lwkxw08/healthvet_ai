"""Routes for TrustID check management — manual submission + future API integration."""
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.utils.auth import get_current_user
from app.services.trustid_checks import TrustIDService
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trustid", tags=["TrustID"])


# ── Schemas ───────────────────────────────────────────────────────────

class TrustIDConfigUpdate(BaseModel):
    check_type: str
    submission_mode: str | None = None
    api_key: str | None = None
    api_secret: str | None = None
    environment: str | None = None


class TrustIDSubmitChecks(BaseModel):
    candidate_id: str
    candidate_name: str | None = None
    candidate_email: str | None = None
    candidate_dob: str | None = None


class AdminMarkSubmitted(BaseModel):
    check_id: str
    trustid_reference: str | None = None
    notes: str | None = None


class AdminRecordResult(BaseModel):
    check_id: str
    result: str  # pass, fail, inconclusive, intervention_required
    trustid_reference: str | None = None
    report_document_id: str | None = None
    completed_date: str | None = None
    notes: str | None = None


# ── Configuration Endpoints (Admin only) ──────────────────────────────

@router.get("/config")
async def get_trustid_config(current_user: dict = Depends(get_current_user)):
    """Get TrustID configuration for all check types."""
    return TrustIDService.get_config()


@router.put("/config")
async def update_trustid_config(data: TrustIDConfigUpdate, current_user: dict = Depends(get_current_user)):
    """Update TrustID configuration for a specific check type. Admin only."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return TrustIDService.update_config(
        check_type=data.check_type,
        submission_mode=data.submission_mode,
        api_key=data.api_key,
        api_secret=data.api_secret,
        environment=data.environment,
    )


# ── Check Submission ──────────────────────────────────────────────────

@router.post("/submit-checks")
async def submit_trustid_checks(data: TrustIDSubmitChecks, current_user: dict = Depends(get_current_user)):
    """Submit all three TrustID checks (ID, DBS, RTW) for a candidate.
    Called when candidate completes their Viper AI submission.
    Creates check records in pending_admin status for manual mode."""
    submitted_by = current_user.get("sub", "system")
    results = TrustIDService.submit_all_checks(
        candidate_id=data.candidate_id,
        submitted_by=submitted_by,
        candidate_name=data.candidate_name,
        candidate_email=data.candidate_email,
        candidate_dob=data.candidate_dob,
    )

    # Send confirmation email to candidate
    if data.candidate_email:
        try:
            EmailService.send_trustid_submission_confirmation(
                candidate_email=data.candidate_email,
                candidate_name=data.candidate_name or "Candidate",
                check_types=["identity_verification", "dbs_check", "right_to_work"],
            )
        except Exception as e:
            logger.warning(f"Failed to send TrustID confirmation email: {e}")

    return {"checks": results, "message": "TrustID checks created successfully"}


@router.get("/checks/{candidate_id}")
async def get_candidate_trustid_checks(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get all TrustID checks for a candidate."""
    return TrustIDService.get_checks_for_candidate(candidate_id)


# ── Admin Task Queue ──────────────────────────────────────────────────

@router.get("/admin/tasks")
async def get_admin_tasks(status: str | None = None, current_user: dict = Depends(get_current_user)):
    """Get pending TrustID tasks for admin processing."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return TrustIDService.get_pending_tasks(status=status)


@router.get("/admin/summary")
async def get_task_summary(current_user: dict = Depends(get_current_user)):
    """Get summary counts for the admin TrustID dashboard."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return TrustIDService.get_task_summary()


@router.post("/admin/mark-submitted")
async def admin_mark_submitted(data: AdminMarkSubmitted, current_user: dict = Depends(get_current_user)):
    """Admin marks a check as submitted to TrustID portal."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    admin_user = current_user.get("sub", "admin")
    result = TrustIDService.admin_mark_submitted(
        check_id=data.check_id,
        admin_user=admin_user,
        trustid_reference=data.trustid_reference,
        notes=data.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Check not found")
    return result


@router.post("/admin/record-result")
async def admin_record_result(data: AdminRecordResult, current_user: dict = Depends(get_current_user)):
    """Admin records the final TrustID result (pass/fail/inconclusive)."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    if data.result not in ("pass", "fail", "inconclusive", "intervention_required"):
        raise HTTPException(status_code=400, detail="Invalid result. Must be: pass, fail, inconclusive, intervention_required")
    admin_user = current_user.get("sub", "admin")
    result = TrustIDService.admin_record_result(
        check_id=data.check_id,
        admin_user=admin_user,
        result=data.result,
        trustid_reference=data.trustid_reference,
        report_document_id=data.report_document_id,
        completed_date=data.completed_date,
        notes=data.notes,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Check not found")
    return result
