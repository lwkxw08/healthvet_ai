"""Agency management and invite routes."""
import logging
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.utils.auth import get_current_user, generate_id
from app.schemas.agencies import InviteCreate, InviteResponse
from app.services.email_templates import EmailTemplateService, reload_email_config

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agencies", tags=["Agencies"])


def _get_agency_template_check_keys(db, agency_id: str) -> list[str]:
    """Get the list of enabled check_keys from the agency's industry template.
    Falls back to the default template, then to hardcoded defaults."""
    template_id = None

    # 1. Agency-level template
    agency = db.execute(
        "SELECT industry_template_id FROM agencies WHERE id=?", (agency_id,)
    ).fetchone()
    if agency and dict(agency).get("industry_template_id"):
        template_id = dict(agency)["industry_template_id"]

    # 2. Fall back to default template
    if not template_id:
        default_tmpl = db.execute(
            "SELECT id FROM industry_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
        ).fetchone()
        if default_tmpl:
            template_id = dict(default_tmpl)["id"]

    # 3. Load check keys from template
    if template_id:
        checks = db.execute(
            "SELECT check_key FROM industry_template_checks WHERE template_id=? AND is_enabled=1",
            (template_id,),
        ).fetchall()
        if checks:
            return [dict(c)["check_key"] for c in checks]

    # 4. Hardcoded fallback (all standard checks)
    return [
        "identity_verified", "dbs_valid", "right_to_work_valid",
        "cv_validated", "registration_active", "references_verified",
        "employment_verified", "training_compliant",
    ]


@router.get("/vetting-pricing")
async def get_vetting_pricing(current_user: dict = Depends(get_current_user)):
    """Get the total vetting cost and annual monitoring cost for the cost confirmation modal.
    Reads per-check pricing from industry_check_pricing for the agency's template.
    Monitoring is always a separate optional item from pricing_settings."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    with get_db() as db:
        # Resolve the agency's industry template
        template_id = None
        agency = db.execute(
            "SELECT industry_template_id FROM agencies WHERE id=?", (agency_id,)
        ).fetchone()
        if agency and dict(agency).get("industry_template_id"):
            template_id = dict(agency)["industry_template_id"]
        if not template_id:
            default_tmpl = db.execute(
                "SELECT id FROM industry_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
            ).fetchone()
            if default_tmpl:
                template_id = dict(default_tmpl)["id"]

        vetting_total = 0.0
        line_items = []

        if template_id:
            # Trigger auto-sync so pricing rows exist for all enabled template checks
            from app.routes.subscription_plans import _sync_industry_pricing
            _sync_industry_pricing(db, template_id)

            # Read per-check pricing from industry_check_pricing
            pricing_rows = db.execute(
                "SELECT check_type, label, sell_price FROM industry_check_pricing WHERE industry_template_id=? AND is_active=1",
                (template_id,)
            ).fetchall()
            for row in pricing_rows:
                p = dict(row)
                vetting_total += p["sell_price"] or 0
                line_items.append({"check_type": p["check_type"], "label": p["label"], "sell_price": p["sell_price"] or 0})

        # Get monitoring price separately (always from pricing_settings, not per-industry)
        monitoring_row = db.execute(
            "SELECT sell_price FROM pricing_settings WHERE check_type='monitoring'"
        ).fetchone()
        monitoring_price = dict(monitoring_row)["sell_price"] if monitoring_row else 0.0

        return {
            "vetting_total": round(vetting_total, 2),
            "monitoring_annual_price": round(monitoring_price, 2),
            "line_items": line_items,
        }


@router.post("/invites")
async def create_invite(data: InviteCreate, request: Request, current_user: dict = Depends(get_current_user)):
    """Agency creates an invite for a candidate email.
    Routes payment based on agency billing_mode:
    - manual_invoicing: creates pending invoice (no Stripe)
    - online_payment: creates invoice + returns Stripe checkout info for PAYG
    - subscription: uses credits first, falls back to PAYG if exceeded
    """
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    invite_code = secrets.token_urlsafe(16)
    invite_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    due_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    with get_db() as db:
        # Get agency details including billing_mode
        agency_row = db.execute(
            "SELECT name, billing_mode, stripe_customer_id, discount_percent FROM agencies WHERE id=?",
            (agency_id,),
        ).fetchone()
        agency_data = dict(agency_row) if agency_row else {}
        agency_name = agency_data.get("name", "Unknown Agency")
        billing_mode = agency_data.get("billing_mode") or "manual_invoicing"
        discount_pct = float(agency_data.get("discount_percent") or 0)

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

        # Calculate vetting cost based on agency's industry template (not all pricing items)
        rows = db.execute("SELECT check_type, sell_price FROM pricing_settings").fetchall()
        pricing_map = {dict(r)["check_type"]: dict(r) for r in rows}
        template_checks = _get_agency_template_check_keys(db, agency_id)
        check_key_to_pricing = {
            "identity_verified": "identity", "dbs_valid": "dbs",
            "right_to_work_valid": "right_to_work", "cv_validated": "cv_analysis",
            "registration_active": "registration", "references_verified": "references",
            "employment_verified": "employment", "training_compliant": None,
        }
        vetting_cost = 0.0
        for ck in template_checks:
            pk = check_key_to_pricing.get(ck)
            if pk and pk in pricing_map:
                vetting_cost += pricing_map[pk]["sell_price"]
        checks = [dict(r) for r in rows]  # keep for cost_amount calc below
        monitoring_cost = 0.0
        if data.include_monitoring and "monitoring" in pricing_map:
            monitoring_cost = pricing_map["monitoring"]["sell_price"]

        # Apply agency discount if set
        if discount_pct > 0:
            vetting_cost = vetting_cost * (1 - discount_pct / 100)
            monitoring_cost = monitoring_cost * (1 - discount_pct / 100)

        db.execute(
            """INSERT INTO agency_invites (id, agency_id, candidate_email, invite_code, status, created_at, include_monitoring, vetting_cost, monitoring_cost, sub_account_id)
               VALUES (?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?)""",
            (invite_id, agency_id, data.candidate_email, invite_code, now,
             1 if data.include_monitoring else 0, round(vetting_cost, 2), round(monitoring_cost, 2),
             data.sub_account_id),
        )

        # Route based on billing_mode
        payment_info = {"billing_mode": billing_mode, "payment_required": False}
        cost_amount = round(vetting_cost * 0.3, 2)

        if billing_mode in ("subscription", "credit_pack"):
            # Try to use subscription credits first
            from app.services.billing import BillingService
            result = BillingService.use_subscription_check(
                agency_id, "", f"Full Automated Vetting - {data.candidate_email}",
                round(vetting_cost, 2), cost_amount, "full_vetting",
            )
            payment_info["subscription_result"] = result
            if result.get("within_credit"):
                # Covered by subscription — auto-paid
                payment_info["status"] = "paid_by_subscription"
                payment_info["credits_remaining"] = result.get("credits_remaining", 0)
            else:
                # Credits exceeded — fall back to PAYG
                payment_info["payment_required"] = True
                payment_info["status"] = "credits_exceeded"
                payment_info["invoice_id"] = result.get("invoice_id")
                payment_info["amount"] = result.get("overage_charge", round(vetting_cost, 2))

        elif billing_mode == "online_payment":
            # PAYG — create invoice and flag for Stripe payment
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at)
                   VALUES (?, ?, 'full_vetting', 'Full Automated Vetting - ' || ?, ?, ?, 'pending', 'stripe', ?, ?)""",
                (inv_id, agency_id, data.candidate_email, cost_amount,
                 round(vetting_cost, 2), due_date, now),
            )
            if data.include_monitoring and monitoring_cost > 0:
                mon_inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at)
                       VALUES (?, ?, 'annual_monitoring', 'Annual Monitoring Service - ' || ?, ?, ?, 'pending', 'stripe', ?, ?)""",
                    (mon_inv_id, agency_id, data.candidate_email,
                     round(monitoring_cost * 0.3, 2), round(monitoring_cost, 2), due_date, now),
                )
            payment_info["payment_required"] = True
            payment_info["status"] = "awaiting_payment"
            payment_info["invoice_id"] = inv_id
            payment_info["amount"] = round(vetting_cost, 2)

        else:
            # manual_invoicing — create pending invoice, no Stripe redirect
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at)
                   VALUES (?, ?, 'full_vetting', 'Full Automated Vetting - ' || ?, ?, ?, 'pending', 'manual', ?, ?)""",
                (inv_id, agency_id, data.candidate_email, cost_amount,
                 round(vetting_cost, 2), due_date, now),
            )
            if data.include_monitoring and monitoring_cost > 0:
                db.execute(
                    """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at)
                       VALUES (?, ?, 'annual_monitoring', 'Annual Monitoring Service - ' || ?, ?, ?, 'pending', 'manual', ?, ?)""",
                    (generate_id(), agency_id, data.candidate_email,
                     round(monitoring_cost * 0.3, 2), round(monitoring_cost, 2), due_date, now),
                )
            payment_info["status"] = "invoice_created"
            payment_info["invoice_id"] = inv_id

    # Send candidate invite email
    try:
        reload_email_config()
        base_url = str(request.base_url).rstrip("/")
        invite_link = f"{base_url}/?invite={invite_code}"
        email_result = EmailTemplateService.send_email(
            template_key="candidate_invite",
            recipient_email=data.candidate_email,
            recipient_name=data.candidate_email.split("@")[0],
            variables={
                "candidate_name": data.candidate_email.split("@")[0].title(),
                "agency_name": agency_name,
                "invite_link": invite_link,
            },
        )
        logger.info(f"Invite email to {data.candidate_email}: {email_result.get('status')}")
    except Exception as e:
        logger.error(f"Failed to send invite email to {data.candidate_email}: {e}")

    return {
        "id": invite_id,
        "agency_id": agency_id,
        "agency_name": agency_name,
        "candidate_email": data.candidate_email,
        "invite_code": invite_code,
        "status": "pending",
        "created_at": now,
        "payment": payment_info,
    }


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


@router.post("/invites/{invite_id}/resend")
async def resend_invite(invite_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Resend the invite email for a pending invite."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM agency_invites WHERE id=? AND agency_id=?",
            (invite_id, agency_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invite not found")
        invite = dict(row)
        if invite["status"] not in ("pending", "sent"):
            raise HTTPException(status_code=400, detail="Can only resend pending or sent invites")

        agency_row = db.execute("SELECT name FROM agencies WHERE id=?", (agency_id,)).fetchone()
        agency_name = dict(agency_row)["name"] if agency_row else "Unknown Agency"

        # Send the invite email again
        try:
            reload_email_config()
            base_url = str(request.base_url).rstrip("/")
            invite_link = f"{base_url}/?invite={invite['invite_code']}"
            email_result = EmailTemplateService.send_email(
                template_key="candidate_invite",
                recipient_email=invite["candidate_email"],
                recipient_name=invite["candidate_email"].split("@")[0],
                variables={
                    "candidate_name": invite["candidate_email"].split("@")[0].title(),
                    "agency_name": agency_name,
                    "invite_link": invite_link,
                },
            )
            logger.info(f"Resent invite email to {invite['candidate_email']}: {email_result.get('status')}")
        except Exception as e:
            logger.error(f"Failed to resend invite email: {e}")
            raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    return {"status": "resent", "candidate_email": invite["candidate_email"]}


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

        # Link candidate to agency with monitoring preferences from invite
        include_monitoring = invite.get("include_monitoring", 0)
        vetting_cost = invite.get("vetting_cost", 0)
        monitoring_cost = invite.get("monitoring_cost", 0)
        sub_account_id = invite.get("sub_account_id")
        db.execute(
            """INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at, annual_monitoring, vetting_cost_accepted, monitoring_cost_accepted, invited_by_sub_account_id)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (invite["agency_id"], candidate_id, now, include_monitoring, vetting_cost, monitoring_cost, sub_account_id),
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


# ── Candidate Employment Status ──────────────────────────────────

class CandidateStatusUpdate(BaseModel):
    employment_status: str  # vetting, hired, rejected, left_business


@router.put("/candidates/{candidate_id}/status")
async def update_candidate_status(
    candidate_id: str,
    data: CandidateStatusUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Agency updates a candidate's employment status."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    valid_statuses = {"vetting", "hired", "rejected", "left_business"}
    if data.employment_status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(valid_statuses)}")

    agency_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM agency_candidates WHERE agency_id=? AND candidate_id=?",
            (agency_id, candidate_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found in your agency")

        db.execute(
            "UPDATE agency_candidates SET employment_status=?, employment_status_updated_at=? WHERE agency_id=? AND candidate_id=?",
            (data.employment_status, now, agency_id, candidate_id),
        )

    return {"status": "updated", "employment_status": data.employment_status}


# ── Agency Services / Billing Breakdown ──────────────────────────

@router.get("/my-services")
async def get_my_services(current_user: dict = Depends(get_current_user)):
    """Get the agency's services rendered breakdown based on admin-set pricing."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]

    with get_db() as db:
        # Get invoices for this agency
        invoices = [dict(r) for r in db.execute(
            "SELECT * FROM invoices WHERE agency_id=? ORDER BY created_at DESC",
            (agency_id,),
        ).fetchall()]

        # Use adjusted_amount if admin has adjusted, otherwise use sell_amount
        def effective_amount(inv):
            adj = inv.get("adjusted_amount")
            return adj if adj is not None else inv["sell_amount"]

        total_billed = sum(effective_amount(i) for i in invoices)
        total_paid = sum(effective_amount(i) for i in invoices if i["status"] == "paid")
        total_outstanding = total_billed - total_paid

        # Breakdown by check type
        by_type = {}
        for inv in invoices:
            ct = inv["check_type"] or "other"
            if ct not in by_type:
                by_type[ct] = {"description": inv["description"] or ct, "count": 0, "total": 0.0}
            by_type[ct]["count"] += 1
            by_type[ct]["total"] += effective_amount(inv)

        # Get candidate count
        cand_count = db.execute(
            "SELECT COUNT(*) as cnt FROM agency_candidates WHERE agency_id=?",
            (agency_id,),
        ).fetchone()

        # Include re-vet requests in the breakdown
        revet_rows = db.execute(
            "SELECT rr.*, c.first_name, c.last_name FROM revet_requests rr JOIN candidates c ON rr.candidate_id = c.id WHERE rr.agency_id=?",
            (agency_id,),
        ).fetchall()

        revet_items = []
        revet_total = 0.0
        import json as _json
        for rr in revet_rows:
            rd = dict(rr)
            sections = _json.loads(rd["sections"]) if rd["sections"] else []
            cand_name = f"{rd['first_name']} {rd['last_name']}"
            for sec in sections:
                price_row = db.execute(
                    "SELECT sell_price, label FROM pricing_settings WHERE check_type=?", (sec,)
                ).fetchone()
                if price_row:
                    pd = dict(price_row)
                    cost = pd["sell_price"]
                    revet_total += cost
                    revet_items.append({
                        "section": sec,
                        "label": f"Re-vet: {pd['label']}",
                        "candidate": cand_name,
                        "cost": cost,
                        "status": rd["status"],
                        "created_at": rd["created_at"],
                    })
                    # Add to by_type
                    ct_key = f"revet_{sec}"
                    if ct_key not in by_type:
                        by_type[ct_key] = {"description": f"Re-vet: {pd['label']}", "count": 0, "total": 0.0}
                    by_type[ct_key]["count"] += 1
                    by_type[ct_key]["total"] += cost

        total_billed += revet_total

        return {
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "total_outstanding": round(total_billed - total_paid, 2),
            "invoice_count": len(invoices),
            "candidate_count": dict(cand_count)["cnt"] if cand_count else 0,
            "by_check_type": by_type,
            "invoices": invoices,
            "revet_items": revet_items,
            "revet_total": round(revet_total, 2),
        }


# ── Partial Re-vetting ────────────────────────────────────────────

class RevetRequest(BaseModel):
    sections: list[str]  # e.g. ["dbs"], ["dbs", "training"]


@router.post("/candidates/{candidate_id}/request-revet")
async def request_revet(
    candidate_id: str,
    data: RevetRequest,
    current_user: dict = Depends(get_current_user),
):
    """Agency requests partial re-vetting for a hired candidate."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    valid_sections = {"identity", "rtw", "dbs", "cv", "registration", "references", "training"}
    for s in data.sections:
        if s not in valid_sections:
            raise HTTPException(status_code=400, detail=f"Invalid section: {s}. Valid: {', '.join(valid_sections)}")

    agency_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    token = secrets.token_urlsafe(24)

    import json
    with get_db() as db:
        # Verify agency owns the candidate
        row = db.execute(
            "SELECT * FROM agency_candidates WHERE agency_id=? AND candidate_id=?",
            (agency_id, candidate_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found in your agency")

        # Get candidate info
        cand = db.execute("SELECT first_name, last_name, email FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        cand_data = dict(cand) if cand else {}

        # Get agency name
        agency = db.execute("SELECT name FROM agencies WHERE id=?", (agency_id,)).fetchone()
        agency_name = dict(agency)["name"] if agency else "Unknown"

        # Get pricing for the sections
        total_cost = 0.0
        section_costs = []
        for section in data.sections:
            price_row = db.execute(
                "SELECT sell_price, label FROM pricing_settings WHERE check_type=?", (section,)
            ).fetchone()
            if price_row:
                pd = dict(price_row)
                section_costs.append({"section": section, "label": pd["label"], "cost": pd["sell_price"]})
                total_cost += pd["sell_price"]

        revet_id = generate_id()
        db.execute(
            """INSERT INTO revet_requests (id, agency_id, candidate_id, sections, token, status, created_at)
               VALUES (?, ?, ?, ?, ?, 'pending', ?)""",
            (revet_id, agency_id, candidate_id, json.dumps(data.sections), token, now),
        )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (?, 'revet_request', ?, 'created', ?, ?, ?)""",
            (generate_id(), revet_id, agency_id,
             json.dumps({"sections": data.sections, "candidate_id": candidate_id}), now),
        )

    return {
        "id": revet_id,
        "token": token,
        "candidate_name": f"{cand_data.get('first_name', '')} {cand_data.get('last_name', '')}".strip(),
        "candidate_email": cand_data.get("email"),
        "agency_name": agency_name,
        "sections": data.sections,
        "section_costs": section_costs,
        "total_cost": round(total_cost, 2),
        "status": "pending",
        "created_at": now,
    }


@router.get("/revet-requests")
async def list_revet_requests(current_user: dict = Depends(get_current_user)):
    """List all re-vet requests for this agency."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    import json
    agency_id = current_user["sub"]
    with get_db() as db:
        rows = db.execute(
            """SELECT rr.*, c.first_name, c.last_name, c.email
               FROM revet_requests rr
               JOIN candidates c ON rr.candidate_id = c.id
               WHERE rr.agency_id=?
               ORDER BY rr.created_at DESC""",
            (agency_id,),
        ).fetchall()
        results = []
        for r in rows:
            d = dict(r)
            d["sections"] = json.loads(d["sections"]) if d["sections"] else []
            d["candidate_name"] = f"{d['first_name']} {d['last_name']}"
            results.append(d)
        return results


@router.get("/candidates-with-status")
async def get_candidates_with_status(current_user: dict = Depends(get_current_user)):
    """Get all agency candidates with their employment status."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    with get_db() as db:
        rows = db.execute(
            """SELECT c.id, c.first_name, c.last_name, c.email, c.compliance_score,
                      c.compliance_status, c.created_at,
                      ac.employment_status, ac.employment_status_updated_at, ac.assigned_at,
                      ac.annual_monitoring, ac.vetting_cost_accepted, ac.monitoring_cost_accepted
               FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               WHERE ac.agency_id=?
               ORDER BY c.created_at DESC""",
            (agency_id,),
        ).fetchall()
        return [dict(r) for r in rows]


# ── Agency Billing Mode & Payment ─────────────────────────────────

@router.get("/billing-mode")
async def get_my_billing_mode(current_user: dict = Depends(get_current_user)):
    """Get the current agency's billing mode."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")
    from app.services.billing import BillingService
    return BillingService.get_agency_billing_mode(current_user["sub"])


@router.post("/billing/pay-invoice/{invoice_id}")
async def pay_invoice(invoice_id: str, current_user: dict = Depends(get_current_user)):
    """Agency pays an outstanding invoice online (simulated Stripe payment).
    Used for the 'Pay Now' button in billing history."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]

    # Verify the invoice belongs to this agency
    with get_db() as db:
        inv = db.execute(
            "SELECT id, agency_id, status FROM invoices WHERE id=?", (invoice_id,)
        ).fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        if dict(inv)["agency_id"] != agency_id:
            raise HTTPException(status_code=403, detail="Not your invoice")

    from app.services.billing import BillingService
    try:
        result = BillingService.pay_invoice_online(invoice_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
