"""
API Routes for Reports, Audit Packs, Training Certificates, Fraud Detection,
Billing/Subscriptions, Email Notifications, and Scheduler Management.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import io
import logging

from app.database import get_db
from app.utils.auth import get_current_user, get_current_admin

logger = logging.getLogger(__name__)

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
# CSV / EXCEL EXPORT ENDPOINTS
# ============================================================

@router.get("/reports/financial/csv")
async def export_financial_csv(period: str = "all", date_from: str = None,
                                date_to: str = None, user=Depends(get_current_user)):
    """Export financial data as CSV."""
    from app.services.report_exports import ReportService
    csv_bytes = ReportService.export_financial_csv(period, date_from, date_to)
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=financial_report_{period}.csv"},
    )


@router.get("/reports/financial/excel")
async def export_financial_excel(period: str = "all", date_from: str = None,
                                  date_to: str = None, user=Depends(get_current_user)):
    """Export financial data as Excel (.xlsx)."""
    from app.services.report_exports import ReportService
    xlsx_bytes = ReportService.export_financial_excel(period, date_from, date_to)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=financial_report_{period}.xlsx"},
    )


@router.get("/reports/compliance/csv")
async def export_compliance_csv(agency_id: str = None, user=Depends(get_current_user)):
    """Export compliance data as CSV."""
    from app.services.report_exports import ReportService
    csv_bytes = ReportService.export_compliance_csv(agency_id)
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=compliance_report.csv"},
    )


@router.get("/reports/compliance/excel")
async def export_compliance_excel(agency_id: str = None, user=Depends(get_current_user)):
    """Export compliance data as Excel (.xlsx)."""
    from app.services.report_exports import ReportService
    xlsx_bytes = ReportService.export_compliance_excel(agency_id)
    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=compliance_report.xlsx"},
    )


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
            "UPDATE fraud_flags SET is_resolved=1, resolved_at=%s, resolved_by=%s WHERE id=%s",
            (now, "admin", flag_id),
        )
        db.execute("SELECT * FROM fraud_flags WHERE id=%s", (flag_id,))
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Flag not found")
        return dict(row)


# ============================================================
# BILLING & SUBSCRIPTIONS
# ============================================================

@router.get("/billing/tiers")
async def get_subscription_tiers(current_user: dict = Depends(get_current_user)):
    """Get available subscription tiers.

    For agency users, returns only industry-specific plans linked to the agency's
    industry template (with custom pricing overrides).  Falls back to generic tiers
    if no industry plans are configured.
    """
    from app.services.billing import BillingService

    # If the caller is an agency, filter tiers by their industry
    if current_user.get("type") == "agency":
        agency_id = current_user["sub"]
        with get_db() as db:
            # Resolve agency's industry template
            db.execute(
                "SELECT industry_template_id FROM agencies WHERE id=%s", (agency_id,)
            )
            agency_row = db.fetchone()
            template_id = dict(agency_row).get("industry_template_id") if agency_row else None

            if template_id:
                # Get industry plan links for this template
                db.execute(
                    """SELECT ipl.*, stc.name as tier_name, stc.monthly_price as base_price,
                              stc.monthly_checks as base_credits, stc.per_worker_price
                       FROM industry_plan_links ipl
                       JOIN subscription_tier_config stc ON ipl.tier_key = stc.tier_key
                       WHERE ipl.industry_template_id=%s AND stc.is_active=1
                       ORDER BY COALESCE(ipl.custom_monthly_price, stc.monthly_price) ASC""",
                    (template_id,),
                )
                links = db.fetchall()
                if links:
                    tiers = {}
                    for row in links:
                        r = dict(row)
                        price = r["custom_monthly_price"] if r["custom_monthly_price"] is not None else r["base_price"]
                        credits = r["custom_monthly_checks"] if r["custom_monthly_checks"] is not None else r["base_credits"]
                        per_credit = round(float(price) / int(credits), 2) if credits and int(credits) > 0 else 0
                        tiers[r["tier_key"]] = {
                            "name": r["tier_name"],
                            "tier_key": r["tier_key"],
                            "pack_price": float(price),
                            "credits_included": int(credits),
                            "per_credit_cost": per_credit,
                            "monthly_price": float(price),
                            "monthly_checks": int(credits),
                            "validity_months": 12,
                        }
                    return {"tiers": list(tiers.values())}

    # Fallback: return all generic tiers
    all_tiers = BillingService.get_tiers()
    # Convert dict to array format for frontend
    tiers_list = []
    for key, val in all_tiers.items():
        val["tier_key"] = key
        val["credits_included"] = val.get("credits") or val.get("monthly_checks") or 0
        tiers_list.append(val)
    return {"tiers": tiers_list}


@router.put("/billing/tiers/{tier_key}")
async def update_subscription_tier(tier_key: str, data: dict, user=Depends(get_current_admin)):
    """Update a subscription tier's pricing and configuration (admin only)."""
    from app.services.billing import BillingService
    try:
        return BillingService.update_tier(tier_key, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/billing/tiers")
async def create_subscription_tier(data: dict, user=Depends(get_current_admin)):
    """Create a new subscription tier (admin only)."""
    from app.services.billing import BillingService
    try:
        return BillingService.create_tier(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/billing/tiers/{tier_key}")
async def delete_subscription_tier(tier_key: str, user=Depends(get_current_admin)):
    """Delete (deactivate) a subscription tier (admin only)."""
    from app.services.billing import BillingService
    try:
        return BillingService.delete_tier(tier_key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/billing/partial-credit-rates")
async def get_partial_credit_rates(user=Depends(get_current_admin)):
    """Get all partial credit rate configurations (admin only)."""
    from app.services.billing import BillingService
    return BillingService.get_partial_credit_rates()


@router.put("/billing/partial-credit-rates/{check_type}")
async def update_partial_credit_rate(check_type: str, data: dict, user=Depends(get_current_admin)):
    """Update a partial credit rate (admin only)."""
    from app.services.billing import BillingService
    try:
        return BillingService.update_partial_credit_rate(check_type, data)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/billing/partial-credit-rates")
async def create_partial_credit_rate(data: dict, user=Depends(get_current_admin)):
    """Create a new partial credit rate (admin only)."""
    from app.services.billing import BillingService
    try:
        return BillingService.create_partial_credit_rate(data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/billing/partial-credit-rates/{check_type}")
async def delete_partial_credit_rate(check_type: str, user=Depends(get_current_admin)):
    """Delete a partial credit rate (admin only)."""
    from app.services.billing import BillingService
    try:
        return BillingService.delete_partial_credit_rate(check_type)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/billing/credit-transactions/{agency_id}")
async def get_credit_transactions(agency_id: str, limit: int = 50, user=Depends(get_current_user)):
    """Get credit transaction history for an agency."""
    from app.services.billing import BillingService
    real_id = user["sub"] if agency_id == "me" else agency_id
    return BillingService.get_credit_transactions(real_id, limit)


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


@router.post("/billing/topup")
async def topup_credits(data: dict, user=Depends(get_current_user)):
    """Manual top-up: purchase a new credit pack. Also tops up £ balance with tier discount."""
    from app.services.billing import BillingService
    from app.services.balance_billing import BalanceBillingService
    agency_id = data.get("agency_id")
    if agency_id == "me":
        agency_id = user["sub"]
    tier = data.get("tier")
    billing_method = data.get("billing_method", "stripe")
    # Support both old format (tier only) and new format (amount + tier_key)
    amount = data.get("amount")
    tier_key = data.get("tier_key") or tier
    if not agency_id and not amount:
        raise HTTPException(status_code=400, detail="agency_id and tier are required")
    if not agency_id:
        agency_id = user.get("agency_id") or user.get("id") or user.get("sub")
    try:
        # If amount is provided directly (new £ balance topup format)
        if amount and float(amount) > 0:
            return BalanceBillingService.topup_balance(
                agency_id, float(amount), tier_key,
                payment_method=data.get("payment_method", billing_method or "stripe"),
            )
        # Otherwise use existing credit pack flow + top up £ balance
        if not tier_key:
            raise HTTPException(status_code=400, detail="tier is required")
        result = BillingService.topup_credits(agency_id, tier_key, billing_method)
        # Also top up £ balance using the pack's price from subscription_tier_config
        try:
            from app.database import get_db
            with get_db() as db:
                db.execute("SELECT monthly_price FROM subscription_tier_config WHERE tier_key=%s", (tier_key,))
                tier_row = db.fetchone()
                if tier_row:
                    pack_price = float(dict(tier_row).get("monthly_price") or 0)
                    if pack_price > 0:
                        BalanceBillingService.topup_balance(
                            agency_id, pack_price, tier_key, payment_method=billing_method or "stripe"
                        )
        except Exception as e:
            logger.warning(f"Failed to top up £ balance alongside credit pack: {e}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.put("/billing/auto-topup")
async def update_auto_topup(data: dict, user=Depends(get_current_user)):
    """Enable or disable auto top-up for an agency's credit pack."""
    from app.services.billing import BillingService
    agency_id = data.get("agency_id")
    if agency_id == "me":
        agency_id = user["sub"]
    enabled = data.get("enabled", False)
    tier = data.get("tier")
    if not agency_id:
        raise HTTPException(status_code=400, detail="agency_id is required")
    try:
        return BillingService.update_auto_topup(agency_id, enabled, tier)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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


@router.get("/billing/invoices/{invoice_id}/pdf")
async def download_invoice_pdf(invoice_id: str, user=Depends(get_current_user)):
    """Download a professional PDF invoice for a specific invoice."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable,
    )

    with get_db() as db:
        db.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
        inv = db.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        invoice = dict(inv)

        # Verify access: user must be admin or belong to the agency
        user_type = user.get("type")
        if user_type == "agency" and invoice.get("agency_id") != user["sub"]:
            raise HTTPException(status_code=403, detail="Access denied")

        # Get agency details
        agency = None
        if invoice.get("agency_id"):
            db.execute("SELECT * FROM agencies WHERE id=%s", (invoice["agency_id"],))
            agency_row = db.fetchone()
            if agency_row:
                agency = dict(agency_row)

        # Get candidate details if applicable
        candidate = None
        if invoice.get("candidate_id"):
            db.execute("SELECT * FROM candidates WHERE id=%s", (invoice["candidate_id"],))
            cand_row = db.fetchone()
            if cand_row:
                candidate = dict(cand_row)

    # Build PDF
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=20*mm, bottomMargin=20*mm,
                            leftMargin=15*mm, rightMargin=15*mm)

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('InvTitle', parent=styles['Title'],
                                  fontSize=20, textColor=colors.HexColor('#1e3a5f'))
    heading_style = ParagraphStyle('InvHeading', parent=styles['Heading2'],
                                    textColor=colors.HexColor('#1e3a5f'), fontSize=12)
    normal_style = styles['Normal']
    small_style = ParagraphStyle('InvSmall', parent=normal_style, fontSize=8,
                                  textColor=colors.grey)
    _bold_style = ParagraphStyle('InvBold', parent=normal_style,  # noqa: F841
                                  fontName='Helvetica-Bold', fontSize=10)

    elements = []

    # Header
    elements.append(Paragraph("Viper AI", title_style))
    elements.append(Paragraph("Healthcare Compliance Vetting Platform", small_style))
    elements.append(Spacer(1, 5*mm))
    elements.append(HRFlowable(width="100%", color=colors.HexColor('#1e3a5f'), thickness=2))
    elements.append(Spacer(1, 8*mm))

    # Invoice details
    elements.append(Paragraph("INVOICE", ParagraphStyle('InvLabel', parent=styles['Heading1'],
                                                          fontSize=24, textColor=colors.HexColor('#1e3a5f'))))
    elements.append(Spacer(1, 5*mm))

    inv_info = [
        ["Invoice ID:", invoice.get("id", "N/A")],
        ["Date:", (invoice.get("created_at") or "N/A")[:10]],
        ["Status:", (invoice.get("status") or "N/A").upper()],
    ]
    if invoice.get("paid_at"):
        inv_info.append(["Paid At:", invoice["paid_at"][:10]])
    if invoice.get("payment_method"):
        inv_info.append(["Payment Method:", invoice["payment_method"].title()])

    t = Table(inv_info, colWidths=[35*mm, 80*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 8*mm))

    # Bill To
    if agency:
        elements.append(Paragraph("Bill To:", heading_style))
        bill_to = [
            ["Agency:", agency.get("name", "N/A")],
            ["Email:", agency.get("email", "N/A")],
        ]
        if agency.get("phone"):
            bill_to.append(["Phone:", agency["phone"]])
        if agency.get("address"):
            bill_to.append(["Address:", agency["address"]])
        t = Table(bill_to, colWidths=[25*mm, 90*mm])
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 8*mm))

    # Line items
    elements.append(Paragraph("Line Items", heading_style))
    elements.append(Spacer(1, 3*mm))

    line_data = [["Description", "Type", "Cost", "Amount"]]
    desc = invoice.get("description") or "Vetting Service"
    check_type = invoice.get("check_type") or "N/A"
    cost_amount = float(invoice.get("cost_amount") or 0)
    sell_amount = float(invoice.get("sell_amount") or 0)

    if candidate:
        desc += f" — {candidate.get('first_name', '')} {candidate.get('last_name', '')}"

    line_data.append([
        desc[:60],
        check_type,
        f"\u00a3{cost_amount:,.2f}",
        f"\u00a3{sell_amount:,.2f}",
    ])

    t = Table(line_data, colWidths=[75*mm, 30*mm, 30*mm, 30*mm])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e3a5f')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f0f4f8')]),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 5*mm))

    # Total
    adjusted = invoice.get("adjusted_amount")
    total = float(adjusted) if adjusted else sell_amount
    total_data = [["Total:", f"\u00a3{total:,.2f}"]]
    if adjusted and float(adjusted) != sell_amount:
        total_data = [
            ["Subtotal:", f"\u00a3{sell_amount:,.2f}"],
            ["Adjusted Total:", f"\u00a3{float(adjusted):,.2f}"],
        ]
    t = Table(total_data, colWidths=[130*mm, 35*mm])
    t.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('LINEABOVE', (0, 0), (-1, 0), 1, colors.HexColor('#1e3a5f')),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(t)

    # Footer
    elements.append(Spacer(1, 20*mm))
    elements.append(HRFlowable(width="100%", color=colors.HexColor('#1e3a5f')))
    elements.append(Paragraph(
        f"Generated by Viper AI on {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}.",
        small_style,
    ))
    elements.append(Paragraph("This is a computer-generated invoice. No signature required.", small_style))

    doc.build(elements)
    pdf_bytes = buffer.getvalue()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice_id[:8]}.pdf"},
    )


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
    """Use a subscription check credit for a candidate vetting. Supports fractional credits via check_type."""
    from app.services.billing import BillingService
    agency_id = data.get("agency_id")
    if agency_id == "me":
        agency_id = user["sub"]
    candidate_id = data.get("candidate_id")
    description = data.get("description", "Vetting check")
    sell_amount = float(data.get("sell_amount", 0))
    cost_amount = float(data.get("cost_amount", 0))
    check_type = data.get("check_type", "full_vetting")
    if not agency_id:
        raise HTTPException(status_code=400, detail="agency_id is required")
    return BillingService.use_subscription_check(agency_id, candidate_id, description, sell_amount, cost_amount, check_type)


# ============================================================
# EMAIL NOTIFICATIONS
# ============================================================

@router.get("/email-notifications")
async def get_email_notifications(recipient_email: str = None, notification_type: str = None,
                            limit: int = 50, user=Depends(get_current_user)):
    """Get email notifications (sent emails log)."""
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


# ============================================================
# £ BALANCE BILLING — ADMIN FINANCIAL REPORTS
# ============================================================

@router.get("/admin/financial/revenue-report")
async def get_revenue_report(start_date: str = None, end_date: str = None, user=Depends(get_current_admin)):
    """Admin report: actual revenue received vs balance consumed across all agencies.
    Shows REAL financial data — money in vs money spent."""
    from app.services.balance_billing import BalanceBillingService
    return BalanceBillingService.get_revenue_report(start_date, end_date)


@router.get("/admin/financial/pack-performance")
async def get_pack_performance(user=Depends(get_current_admin)):
    """Admin report: revenue and usage performance by credit pack tier.
    Shows which pack tiers generate the most revenue and which are most used."""
    from app.services.balance_billing import BalanceBillingService
    return BalanceBillingService.get_pack_performance_report()


@router.get("/admin/financial/agency/{agency_id}")
async def get_agency_financial_detail(agency_id: str, user=Depends(get_current_admin)):
    """Admin view: detailed financial summary for a specific agency.
    Shows actual money paid in, actual money spent, balance, and usage breakdown."""
    from app.services.balance_billing import BalanceBillingService
    result = BalanceBillingService.get_agency_financial_summary(agency_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/admin/financial/all-agencies")
async def get_all_agencies_financial(user=Depends(get_current_admin)):
    """Admin report: financial overview of all agencies with balances."""
    from app.database import get_db
    with get_db() as db:
        db.execute(
            """SELECT id, name, balance_amount, total_topup_amount, total_spent_amount, discount_percent
               FROM agencies WHERE status='active'
               ORDER BY total_topup_amount DESC"""
        )
        rows = db.fetchall()
        agencies = []
        for row in rows:
            r = dict(row)
            agencies.append({
                "agency_id": r["id"],
                "agency_name": r["name"],
                "balance": round(float(r.get("balance_amount") or 0), 2),
                "total_paid_in": round(float(r.get("total_topup_amount") or 0), 2),
                "total_spent": round(float(r.get("total_spent_amount") or 0), 2),
                "discount_percent": float(r.get("discount_percent") or 0),
            })
        return {"agencies": agencies, "count": len(agencies)}


# ============================================================
# £ BALANCE BILLING — AGENCY BALANCE ENDPOINTS
# ============================================================

@router.get("/billing/balance")
async def get_my_balance(user=Depends(get_current_user)):
    """Agency endpoint: get current balance and billing summary."""
    agency_id = user.get("agency_id") or user.get("sub") or user.get("id")
    from app.services.balance_billing import BalanceBillingService
    return BalanceBillingService.get_agency_balance(agency_id)


@router.post("/billing/balance-topup")
async def topup_balance(data: dict, user=Depends(get_current_user)):
    """Direct balance top-up (admin or API use). For agency pack purchases, use POST /billing/topup."""
    agency_id = user.get("agency_id") or user.get("id") or user.get("sub")
    amount = data.get("amount")
    tier_key = data.get("tier_key")
    if not amount or float(amount) <= 0:
        raise HTTPException(status_code=400, detail="amount must be a positive number")
    from app.services.balance_billing import BalanceBillingService
    try:
        return BalanceBillingService.topup_balance(
            agency_id, float(amount), tier_key,
            payment_method=data.get("payment_method", "stripe"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/billing/transactions")
async def get_my_transactions(limit: int = 50, transaction_type: str = None, user=Depends(get_current_user)):
    """Agency endpoint: get balance transaction history."""
    agency_id = user.get("agency_id") or user.get("sub") or user.get("id")
    from app.services.balance_billing import BalanceBillingService
    return BalanceBillingService.get_transactions(agency_id, limit, transaction_type)


@router.get("/billing/check-prices")
async def get_check_prices(user=Depends(get_current_user)):
    """Get all check prices (gross). Agency can see their discounted price based on tier."""
    from app.services.balance_billing import BalanceBillingService
    agency_id = user.get("agency_id") or user.get("sub") or user.get("id")
    prices = BalanceBillingService.get_check_prices(agency_id)
    # Get agency discount
    balance_info = BalanceBillingService.get_agency_balance(agency_id)
    discount_pct = balance_info.get("discount_percent", 0)
    result = []
    for p in prices:
        gross = float(p.get("third_party_cost") or p.get("gross_price") or 0)
        discount_amt = round(gross * (discount_pct / 100), 2)
        net = round(gross - discount_amt, 2)
        result.append({
            "check_type": p.get("check_type"),
            "label": p.get("label"),
            "gross_price": gross,
            "your_discount_percent": discount_pct,
            "your_price": net,
        })
    return {"prices": result, "discount_percent": discount_pct}


# ============================================================
# ADMIN — CREDIT PACK TIER MANAGEMENT (with discount %)
# ============================================================

@router.put("/admin/tiers/{tier_key}/discount")
async def update_tier_discount(tier_key: str, data: dict, user=Depends(get_current_admin)):
    """Admin: update the discount percentage for a credit pack tier."""
    discount_percent = data.get("discount_percent")
    if discount_percent is None:
        raise HTTPException(status_code=400, detail="discount_percent is required")
    if not (0 <= float(discount_percent) <= 100):
        raise HTTPException(status_code=400, detail="discount_percent must be between 0 and 100")

    from app.database import get_db
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "SELECT id FROM subscription_tier_config WHERE tier_key=%s", (tier_key,)
        )
        if not db.fetchone():
            raise HTTPException(status_code=404, detail=f"Tier '{tier_key}' not found")
        db.execute(
            "UPDATE subscription_tier_config SET discount_percent=%s, updated_at=%s WHERE tier_key=%s",
            (float(discount_percent), now, tier_key),
        )
        db.execute("SELECT * FROM subscription_tier_config WHERE tier_key=%s", (tier_key,))
        row = db.fetchone()
        return dict(row)
