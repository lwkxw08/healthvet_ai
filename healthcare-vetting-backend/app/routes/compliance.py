"""Compliance and monitoring routes."""
from fastapi import APIRouter, HTTPException, Depends
from app.utils.auth import get_current_user, verify_agency_owns_candidate
from app.schemas.checks import ComplianceResponse, MonitoringAlertResponse, DashboardStats
from app.services.compliance_engine import ComplianceEngine
from app.services.monitoring import MonitoringService

router = APIRouter(prefix="/api", tags=["Compliance & Monitoring"])


# ── Compliance ─────────────────────────────────────────────────────
@router.post("/compliance/evaluate/{candidate_id}", response_model=ComplianceResponse)
async def evaluate_compliance(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    result = ComplianceEngine.evaluate_candidate(candidate_id)
    return result


@router.get("/compliance/{candidate_id}", response_model=ComplianceResponse)
async def get_compliance(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    # Always re-evaluate to ensure compliance data reflects latest check results
    try:
        result = ComplianceEngine.evaluate_candidate(candidate_id)
        if result:
            return result
    except Exception:
        pass
    # Fallback to cached record if re-evaluation fails
    result = ComplianceEngine.get_compliance(candidate_id)
    if not result:
        raise HTTPException(status_code=404, detail="No compliance record found")
    return result


@router.get("/compliance/{candidate_id}/audit-log")
async def get_audit_log(candidate_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["type"] not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Agencies and admin only")
    verify_agency_owns_candidate(current_user, candidate_id)
    return ComplianceEngine.get_audit_log(candidate_id)


# ── Monitoring ─────────────────────────────────────────────────────
@router.get("/monitoring/alerts", response_model=list[MonitoringAlertResponse])
async def get_alerts(candidate_id: str = None, current_user: dict = Depends(get_current_user)):
    if candidate_id:
        verify_agency_owns_candidate(current_user, candidate_id)
    elif current_user["type"] == "agency":
        # Agencies without a candidate_id filter get alerts for their candidates only
        from app.database import get_db
        with get_db() as db:
            db.execute(
                "SELECT candidate_id FROM agency_candidates WHERE agency_id=%s",
                (current_user["sub"],),
            )
            rows = db.fetchall()
            candidate_ids = [dict(r)["candidate_id"] for r in rows]
            if not candidate_ids:
                return []
            return MonitoringService.get_alerts_for_candidates(candidate_ids)
    return MonitoringService.get_alerts(candidate_id=candidate_id)


@router.post("/monitoring/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["type"] not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Agencies and admin only")
    result = MonitoringService.resolve_alert(alert_id)
    if not result:
        raise HTTPException(status_code=404, detail="Alert not found")
    return result


@router.post("/monitoring/run-checks")
async def run_monitoring_checks(current_user: dict = Depends(get_current_user)):
    """Trigger all monitoring checks. In production, this runs on a schedule."""
    if current_user["type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")
    return MonitoringService.run_all_checks()


# ── Dashboard ──────────────────────────────────────────────────────
@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    agency_id = current_user["sub"] if current_user["type"] == "agency" else None
    return MonitoringService.get_dashboard_stats(agency_id=agency_id)
