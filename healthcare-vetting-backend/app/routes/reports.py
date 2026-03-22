"""
API Routes for Reports, Audit Packs, Training Certificates, Fraud Detection,
Billing/Subscriptions, Email Notifications, and Scheduler Management.
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io

from app.database import get_db
from app.utils.auth import get_current_user, get_current_admin, generate_id

router = APIRouter(prefix="/api", tags=["reports"])


# ============================================================
# CQC AUDIT PACK ENDPOINTS
# ============================================================

@router.get("/audit/candidate/{candidate_id}")
async def generate_candidate_audit_pack(candidate_id: str, user=Depends(get_current_user)):
    """Generate a CQC audit pack PDF for a candidate."""
    from app.services.audit_pack import AuditPackService
    try:
        pdf_bytes = AuditPackService.generate_candidate_audit(candidate_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=audit_pack_{candidate_id[:8]}.pdf"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate audit pack: {str(e)}")


@router.get("/audit/agency/{agency_id}")
async def generate_agency_audit_pack(agency_id: str, user=Depends(get_current_user)):
    """Generate an agency-wide audit summary PDF."""
    from app.services.audit_pack import AuditPackService
    real_id = user["sub"] if agency_id == "me" else agency_id
    try:
        pdf_bytes = AuditPackService.generate_agency_audit(real_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=agency_audit_{agency_id[:8]}.pdf"},
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate agency audit: {str(e)}")


@router.post("/audit/bulk-candidates")
async def generate_bulk_candidate_audit(data: dict, user=Depends(get_current_user)):
    """Generate a combined CQC audit pack PDF for multiple selected candidates."""
    from app.services.audit_pack import AuditPackService
    candidate_ids = data.get("candidate_ids", [])
    if not candidate_ids:
        raise HTTPException(status_code=400, detail="candidate_ids list is required")
    try:
        pdf_bytes = AuditPackService.generate_bulk_audit(candidate_ids)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=bulk_audit_pack.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate bulk audit pack: {str(e)}")


# ============================================================
# PDF REPORT EXPORTS
# ============================================================

@router.get("/reports/financial")
async def export_financial_report(period: str = "all", date_from: str = None,
                                   date_to: str = None, user=Depends(get_current_user)):
    """Generate a financial report PDF."""
    from app.services.report_exports import ReportService
    try:
        pdf_bytes = ReportService.generate_financial_report(period, date_from, date_to)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=financial_report_{period}.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@router.get("/reports/compliance")
async def export_compliance_report(agency_id: str = None, user=Depends(get_current_user)):
    """Generate a compliance summary PDF."""
    from app.services.report_exports import ReportService
    try:
        pdf_bytes = ReportService.generate_compliance_summary(agency_id)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=compliance_summary.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


# ============================================================
# TRAINING CERTIFICATES
# ============================================================

@router.get("/training/standards")
async def get_standard_certificates():
    """Get list of standard healthcare training certificates."""
    from app.services.training_certificates import TrainingCertificateService
    return TrainingCertificateService.get_standard_certificates()


@router.get("/training/{candidate_id}")
async def get_training_certificates(candidate_id: str, user=Depends(get_current_user)):
    """Get all training certificates for a candidate."""
    from app.services.training_certificates import TrainingCertificateService
    return TrainingCertificateService.get_certificates(candidate_id)


@router.post("/training/{candidate_id}")
async def add_training_certificate(candidate_id: str, data: dict, user=Depends(get_current_user)):
    """Add a training certificate for a candidate."""
    from app.services.training_certificates import TrainingCertificateService
    if "certificate_name" not in data:
        raise HTTPException(status_code=400, detail="certificate_name is required")
    return TrainingCertificateService.add_certificate(candidate_id, data)


@router.put("/training/cert/{cert_id}")
async def update_training_certificate(cert_id: str, data: dict, user=Depends(get_current_user)):
    """Update a training certificate."""
    from app.services.training_certificates import TrainingCertificateService
    result = TrainingCertificateService.update_certificate(cert_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Certificate not found")
    return result


@router.delete("/training/cert/{cert_id}")
async def delete_training_certificate(cert_id: str, user=Depends(get_current_user)):
    """Delete a training certificate."""
    from app.services.training_certificates import TrainingCertificateService
    TrainingCertificateService.delete_certificate(cert_id)
    return {"status": "deleted"}


@router.get("/training/{candidate_id}/compliance")
async def get_training_compliance(candidate_id: str, user=Depends(get_current_user)):
    """Check training compliance for a candidate."""
    from app.services.training_certificates import TrainingCertificateService
    return TrainingCertificateService.get_training_compliance(candidate_id)


# ============================================================
# FRAUD DETECTION
# ============================================================

@router.post("/fraud/scan")
async def run_fraud_scan(user=Depends(get_current_admin)):
    """Run a full cross-candidate fraud detection scan (admin only)."""
    from app.services.fraud_detection import FraudDetectionService
    return FraudDetectionService.run_full_scan()


@router.get("/fraud/flags")
async def get_fraud_flags(candidate_id: str = None, user=Depends(get_current_user)):
    """Get fraud flags, optionally filtered by candidate."""
    from app.services.fraud_detection import FraudDetectionService
    return FraudDetectionService.get_fraud_flags(candidate_id)


@router.get("/fraud/summary")
async def get_fraud_summary(user=Depends(get_current_user)):
    """Get fraud scan summary."""
    from app.services.fraud_detection import FraudDetectionService
    return FraudDetectionService.get_scan_summary()


@router.post("/fraud/flags/{flag_id}/resolve")
async def resolve_fraud_flag(flag_id: str, user=Depends(get_current_admin)):
    """Resolve a fraud flag (admin only)."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "UPDATE fraud_flags SET is_resolved=1, resolved_at=?, resolved_by=? WHERE id=?",
            (now, "admin", flag_id),
        )
        row = db.execute("SELECT * FROM fraud_flags WHERE id=?", (flag_id,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Flag not found")
        return dict(row)


# ============================================================
# BILLING & SUBSCRIPTIONS
# ============================================================

@router.get("/billing/tiers")
async def get_subscription_tiers():
    """Get available subscription tiers."""
    from app.services.billing import BillingService
    return BillingService.get_tiers()


@router.put("/billing/tiers/{tier_key}")
async def update_subscription_tier(tier_key: str, data: dict, user=Depends(get_current_admin)):
    """Update a subscription tier's pricing and configuration (admin only)."""
    from app.services.billing import SUBSCRIPTION_TIERS
    if tier_key not in SUBSCRIPTION_TIERS:
        raise HTTPException(status_code=404, detail=f"Tier not found: {tier_key}")

    tier = SUBSCRIPTION_TIERS[tier_key]
    if "name" in data:
        tier["name"] = data["name"]
    if "monthly_price" in data:
        tier["monthly_price"] = float(data["monthly_price"])
    if "per_worker_price" in data:
        tier["per_worker_price"] = float(data["per_worker_price"])
    if "max_workers" in data:
        tier["max_workers"] = int(data["max_workers"])
    if "features" in data and isinstance(data["features"], list):
        tier["features"] = data["features"]
    if "monthly_checks" in data:
        tier["monthly_checks"] = int(data["monthly_checks"])

    # Also persist to DB for durability
    with get_db() as db:
        now_str = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()
        existing = db.execute("SELECT id FROM subscription_tier_config WHERE tier_key=?", (tier_key,)).fetchone()
        import json as _json
        if existing:
            db.execute(
                "UPDATE subscription_tier_config SET name=?, monthly_price=?, per_worker_price=?, max_workers=?, monthly_checks=?, features=?, updated_at=? WHERE tier_key=?",
                (tier["name"], tier["monthly_price"], tier["per_worker_price"], tier["max_workers"],
                 tier.get("monthly_checks", 0), _json.dumps(tier["features"]), now_str, tier_key),
            )
        else:
            from app.utils.auth import generate_id as _gen_id
            db.execute(
                "INSERT INTO subscription_tier_config (id, tier_key, name, monthly_price, per_worker_price, max_workers, monthly_checks, features, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (_gen_id(), tier_key, tier["name"], tier["monthly_price"], tier["per_worker_price"],
                 tier["max_workers"], tier.get("monthly_checks", 0), _json.dumps(tier["features"]), now_str),
            )

    return {"tier_key": tier_key, **tier}


@router.get("/billing/subscription/{agency_id}")
async def get_agency_subscription(agency_id: str, user=Depends(get_current_user)):
    """Get current subscription for an agency."""
    from app.services.billing import BillingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    sub = BillingService.get_agency_subscription(real_id)
    return sub or {"status": "none", "message": "No active subscription"}


@router.post("/billing/subscribe")
async def create_subscription(data: dict, user=Depends(get_current_user)):
    """Create a new subscription for an agency."""
    from app.services.billing import BillingService
    agency_id = data.get("agency_id")
    if agency_id == "me":
        agency_id = user["sub"]
    tier = data.get("tier")
    billing_method = data.get("billing_method", "stripe")
    if not agency_id or not tier:
        raise HTTPException(status_code=400, detail="agency_id and tier are required")
    try:
        return BillingService.create_subscription(
            agency_id, tier, billing_method,
            data.get("stripe_payment_method_id"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/billing/cancel/{agency_id}")
async def cancel_subscription(agency_id: str, user=Depends(get_current_user)):
    """Cancel an agency's subscription."""
    from app.services.billing import BillingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    return BillingService.cancel_subscription(real_id)


@router.get("/billing/history/{agency_id}")
async def get_billing_history(agency_id: str, user=Depends(get_current_user)):
    """Get billing history for an agency."""
    from app.services.billing import BillingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    return BillingService.get_billing_history(real_id)


@router.post("/billing/pay/{invoice_id}")
async def pay_invoice(invoice_id: str, user=Depends(get_current_user)):
    """Simulate paying an invoice (Stripe or mark as paid)."""
    from app.services.billing import BillingService
    result = BillingService.simulate_stripe_payment(invoice_id)
    if not result:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return result


@router.post("/billing/generate-recurring")
async def generate_recurring_invoices(user=Depends(get_current_admin)):
    """Generate recurring invoices for due subscriptions (admin only)."""
    from app.services.billing import BillingService
    return BillingService.generate_recurring_invoices()


@router.get("/billing/remaining-checks/{agency_id}")
async def get_remaining_checks(agency_id: str, user=Depends(get_current_user)):
    """Get remaining check credits for a subscription agency."""
    from app.services.billing import BillingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    return BillingService.get_remaining_checks(real_id)


@router.post("/billing/use-check")
async def use_subscription_check(data: dict, user=Depends(get_current_user)):
    """Use a subscription check credit for a candidate vetting."""
    from app.services.billing import BillingService
    agency_id = data.get("agency_id")
    if agency_id == "me":
        agency_id = user["sub"]
    candidate_id = data.get("candidate_id")
    description = data.get("description", "Vetting check")
    sell_amount = float(data.get("sell_amount", 0))
    cost_amount = float(data.get("cost_amount", 0))
    if not agency_id:
        raise HTTPException(status_code=400, detail="agency_id is required")
    return BillingService.use_subscription_check(agency_id, candidate_id, description, sell_amount, cost_amount)


# ============================================================
# EMAIL NOTIFICATIONS
# ============================================================

@router.get("/notifications")
async def get_notifications(recipient_email: str = None, notification_type: str = None,
                            limit: int = 50, user=Depends(get_current_user)):
    """Get email notifications."""
    from app.services.email_service import EmailService
    return EmailService.get_notifications(recipient_email, notification_type, limit)


# ============================================================
# SCHEDULER MANAGEMENT
# ============================================================

@router.get("/scheduler/status")
async def get_scheduler_status(user=Depends(get_current_admin)):
    """Get scheduler status and job list."""
    from app.services.scheduler import get_scheduler
    scheduler = get_scheduler()
    jobs = []
    if scheduler.running:
        for job in scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "trigger": str(job.trigger),
            })
    return {
        "running": scheduler.running,
        "jobs": jobs,
    }


@router.post("/scheduler/trigger/{job_name}")
async def trigger_scheduled_job(job_name: str, user=Depends(get_current_admin)):
    """Manually trigger a scheduled job (admin only)."""
    from app.services.scheduler import run_scheduled_monitoring, run_expiry_warnings, run_fraud_scan
    jobs = {
        "monitoring": run_scheduled_monitoring,
        "expiry_warnings": run_expiry_warnings,
        "fraud_scan": run_fraud_scan,
    }
    if job_name not in jobs:
        raise HTTPException(status_code=400, detail=f"Unknown job: {job_name}. Valid: {list(jobs.keys())}")
    try:
        jobs[job_name]()
        return {"status": "completed", "job": job_name}
    except Exception as e:
        return {"status": "error", "job": job_name, "error": str(e)}
