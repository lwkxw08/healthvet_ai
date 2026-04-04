"""
3.4 Audit Trail & Compliance Reporting API Routes

Query audit trail, verify chain integrity, export CQC audit reports,
GDPR SAR reports, data access logs, and retention reporting.
"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io
import json

from app.utils.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/audit-trail", tags=["Audit Trail"])


@router.get("/log")
async def get_audit_log(entity_type: str = None, entity_id: str = None,
                        actor: str = None, action: str = None,
                        date_from: str = None, date_to: str = None,
                        limit: int = 100, offset: int = 0,
                        user=Depends(get_current_admin)):
    """Query the audit trail with filters (admin only)."""
    from app.services.audit_trail import AuditTrailService
    return AuditTrailService.get_audit_log(
        entity_type, entity_id, actor, action, date_from, date_to, limit, offset
    )


@router.get("/verify-integrity")
async def verify_chain_integrity(limit: int = 1000, user=Depends(get_current_admin)):
    """Verify the tamper-evident hash chain integrity (admin only)."""
    from app.services.audit_trail import AuditTrailService
    return AuditTrailService.verify_chain_integrity(limit)


@router.get("/data-access-log")
async def get_data_access_log(entity_type: str = None, entity_id: str = None,
                               accessor: str = None, date_from: str = None,
                               date_to: str = None, limit: int = 100,
                               user=Depends(get_current_admin)):
    """Query data access logs for GDPR SAR compliance (admin only)."""
    from app.services.audit_trail import AuditTrailService
    return AuditTrailService.get_data_access_log(
        entity_type, entity_id, accessor, date_from, date_to, limit
    )


@router.get("/export/cqc")
async def export_cqc_audit(agency_id: str = None, date_from: str = None,
                            date_to: str = None, user=Depends(get_current_admin)):
    """Export a comprehensive CQC audit report (admin only)."""
    from app.services.audit_trail import AuditTrailService
    report = AuditTrailService.generate_cqc_audit_export(agency_id, date_from, date_to)
    return report


@router.get("/export/cqc/download")
async def download_cqc_audit(agency_id: str = None, date_from: str = None,
                              date_to: str = None, user=Depends(get_current_admin)):
    """Download CQC audit report as JSON file (admin only)."""
    from app.services.audit_trail import AuditTrailService
    report = AuditTrailService.generate_cqc_audit_export(agency_id, date_from, date_to)
    content = json.dumps(report, indent=2, default=str).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=cqc_audit_report.json"},
    )


@router.get("/sar/{candidate_email}")
async def generate_sar_report(candidate_email: str, user=Depends(get_current_admin)):
    """Generate a Subject Access Request report for a candidate (admin only)."""
    from app.services.audit_trail import AuditTrailService
    report = AuditTrailService.generate_sar_report(candidate_email)
    if report.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Candidate with email {candidate_email} not found")
    return report


@router.get("/retention-report")
async def get_retention_report(user=Depends(get_current_admin)):
    """Get retention policy enforcement report (admin only)."""
    from app.services.audit_trail import AuditTrailService
    return AuditTrailService.get_retention_report()
