"""
3.2 Reporting & Analytics Dashboard API Routes

Agency-level KPIs, time-to-clear metrics, response rates,
expiry forecasting, CSV export, check volume trends, and scheduled reports.
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io

from app.database import get_db
from app.utils.auth import get_current_user, get_current_admin, generate_id

router = APIRouter(prefix="/api/analytics", tags=["Analytics & Reporting"])


@router.get("/kpis/{agency_id}")
async def get_agency_kpis(agency_id: str, user=Depends(get_current_user)):
    """Get compliance KPI dashboard for an agency."""
    from app.services.analytics_reporting import AnalyticsReportingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    return AnalyticsReportingService.get_agency_kpis(real_id)


@router.get("/time-to-clear")
async def get_time_to_clear(agency_id: str = None, user=Depends(get_current_user)):
    """Get average time-to-clear metrics per check type."""
    from app.services.analytics_reporting import AnalyticsReportingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    return AnalyticsReportingService.get_time_to_clear(real_id)


@router.get("/response-rates")
async def get_response_rates(agency_id: str = None, user=Depends(get_current_user)):
    """Get verification response rate analytics."""
    from app.services.analytics_reporting import AnalyticsReportingService
    return AnalyticsReportingService.get_verification_response_rates(agency_id)


@router.get("/expiry-forecast")
async def get_expiry_forecast(agency_id: str = None, days_ahead: int = 90,
                               user=Depends(get_current_user)):
    """Forecast upcoming expiries in the next N days."""
    from app.services.analytics_reporting import AnalyticsReportingService
    return AnalyticsReportingService.get_expiry_forecast(agency_id, days_ahead)


@router.get("/check-volume-trend")
async def get_check_volume_trend(agency_id: str = None, months: int = 6,
                                  user=Depends(get_current_user)):
    """Get monthly check volume trend."""
    from app.services.analytics_reporting import AnalyticsReportingService
    return AnalyticsReportingService.get_check_volume_trend(agency_id, months)


@router.get("/export/compliance-csv")
async def export_compliance_csv(agency_id: str = None, user=Depends(get_current_user)):
    """Export compliance data as CSV."""
    from app.services.analytics_reporting import AnalyticsReportingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    csv_data = AnalyticsReportingService.generate_compliance_csv(real_id)
    return StreamingResponse(
        io.BytesIO(csv_data.encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=compliance_report.csv"},
    )


# ── Scheduled Reports ─────────────────────────────────────────────────────────

@router.get("/scheduled-reports")
async def list_scheduled_reports(user=Depends(get_current_user)):
    """List scheduled reports for the authenticated agency."""
    agency_id = user["sub"]
    with get_db() as db:
        db.execute(
            "SELECT * FROM scheduled_reports WHERE agency_id=%s ORDER BY created_at DESC",
            (agency_id,),
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


@router.post("/scheduled-reports")
async def create_scheduled_report(data: dict, user=Depends(get_current_user)):
    """Create a new scheduled report."""
    agency_id = user["sub"]
    report_type = data.get("report_type", "compliance_summary")
    frequency = data.get("frequency", "weekly")
    recipients = data.get("recipients", [])

    if frequency not in ("daily", "weekly", "monthly"):
        raise HTTPException(status_code=400, detail="Frequency must be daily, weekly, or monthly")

    report_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            """INSERT INTO scheduled_reports
               (id, agency_id, report_type, frequency, recipients, is_active, created_at)
               VALUES (%s, %s, %s, %s, %s, 1, %s)""",
            (report_id, agency_id, report_type, frequency, json.dumps(recipients), now),
        )

    return {"id": report_id, "report_type": report_type, "frequency": frequency,
            "recipients": recipients, "status": "active"}


@router.put("/scheduled-reports/{report_id}")
async def update_scheduled_report(report_id: str, data: dict, user=Depends(get_current_user)):
    """Update a scheduled report."""
    agency_id = user["sub"]
    with get_db() as db:
        db.execute(
            "SELECT id FROM scheduled_reports WHERE id=%s AND agency_id=%s",
            (report_id, agency_id),
        )
        existing = db.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Report not found")

        updates = []
        params = []
        for field in ["report_type", "frequency", "is_active"]:
            if field in data:
                updates.append(f"{field}=%s")
                params.append(data[field])
        if "recipients" in data:
            updates.append("recipients=%s")
            params.append(json.dumps(data["recipients"]))

        if updates:
            params.append(report_id)
            db.execute(
                f"UPDATE scheduled_reports SET {', '.join(updates)} WHERE id=%s",
                tuple(params),
            )

    return {"updated": True, "id": report_id}


@router.delete("/scheduled-reports/{report_id}")
async def delete_scheduled_report(report_id: str, user=Depends(get_current_user)):
    """Delete a scheduled report."""
    agency_id = user["sub"]
    with get_db() as db:
        db.execute(
            "DELETE FROM scheduled_reports WHERE id=%s AND agency_id=%s",
            (report_id, agency_id),
        )
    return {"deleted": True, "id": report_id}


# ── Admin: Platform-wide analytics ────────────────────────────────────────────

@router.get("/admin/overview")
async def admin_analytics_overview(user=Depends(get_current_admin)):
    """Get platform-wide analytics overview (admin only)."""
    from app.services.analytics_reporting import AnalyticsReportingService

    with get_db() as db:
        db.execute("SELECT COUNT(*) AS cnt FROM agencies")
        row = db.fetchone()
        total_agencies = row["cnt"] if row else 0
        db.execute("SELECT COUNT(*) AS cnt FROM candidates")
        row = db.fetchone()
        total_candidates = row["cnt"] if row else 0
        total_checks = 0
        for table in ["identity_checks", "dbs_checks", "right_to_work_checks", "registration_checks"]:
            try:
                db.execute(f"SELECT COUNT(*) AS cnt FROM {table}")
                row = db.fetchone()
                total_checks += row["cnt"] if row else 0
            except Exception:
                pass

        db.execute(
            "SELECT COUNT(*) AS cnt FROM agency_subscriptions WHERE status='active'"
        )
        row = db.fetchone()
        active_subs = row["cnt"] if row else 0

    time_to_clear = AnalyticsReportingService.get_time_to_clear()
    response_rates = AnalyticsReportingService.get_verification_response_rates()
    volume_trend = AnalyticsReportingService.get_check_volume_trend(months=12)

    return {
        "total_agencies": total_agencies,
        "total_candidates": total_candidates,
        "total_checks": total_checks,
        "active_subscriptions": active_subs,
        "time_to_clear": time_to_clear,
        "response_rates": response_rates,
        "volume_trend": volume_trend,
    }
