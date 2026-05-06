"""Agency management and invite routes."""
import logging
import os
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


def _resolve_agency_template_id(db, agency_id: str) -> Optional[str]:
    """Return the agency's industry_template_id, or the default template id."""
    db.execute("SELECT industry_template_id FROM agencies WHERE id=%s", (agency_id,))
    agency = db.fetchone()
    if agency and dict(agency).get("industry_template_id"):
        return dict(agency)["industry_template_id"]
    db.execute(
        "SELECT id FROM industry_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
    )
    default_tmpl = db.fetchone()
    if default_tmpl:
        return dict(default_tmpl)["id"]
    return None


def _calculate_agency_vetting_cost(
    db, agency_id: str, include_monitoring: bool = False
) -> tuple[float, float, Optional[str]]:
    """Single source of truth for vetting + monitoring cost.

    Uses industry_check_pricing for the agency's industry template (same source
    as the Confirm Vetting Cost popup). Monitoring comes from pricing_settings.
    Returns (vetting_total, monitoring_cost, template_id). Discount is NOT
    applied here — caller applies any agency-level discount after.
    """
    template_id = _resolve_agency_template_id(db, agency_id)
    vetting_total = 0.0
    if template_id:
        from app.routes.subscription_plans import _sync_industry_pricing
        _sync_industry_pricing(db, template_id)
        db.execute(
            "SELECT sell_price FROM industry_check_pricing "
            "WHERE industry_template_id=%s AND is_active=1",
            (template_id,),
        )
        for row in db.fetchall():
            vetting_total += float(dict(row).get("sell_price") or 0)

    monitoring_cost = 0.0
    if include_monitoring:
        db.execute("SELECT sell_price FROM pricing_settings WHERE check_type='monitoring'")
        mrow = db.fetchone()
        if mrow:
            monitoring_cost = float(dict(mrow).get("sell_price") or 0)

    return round(vetting_total, 2), round(monitoring_cost, 2), template_id


def _get_agency_template_check_keys(db, agency_id: str) -> list[str]:
    """Get the list of enabled check_keys from the agency's industry template.
    Falls back to the default template, then to hardcoded defaults."""
    template_id = None

    # 1. Agency-level template
    db.execute(
        "SELECT industry_template_id FROM agencies WHERE id=%s", (agency_id,)
    )
    agency = db.fetchone()
    if agency and dict(agency).get("industry_template_id"):
        template_id = dict(agency)["industry_template_id"]

    # 2. Fall back to default template
    if not template_id:
        db.execute(
            "SELECT id FROM industry_templates WHERE is_default=1 AND is_active=1 LIMIT 1"
        )
        default_tmpl = db.fetchone()
        if default_tmpl:
            template_id = dict(default_tmpl)["id"]

    # 3. Load check keys from template
    if template_id:
        db.execute(
            "SELECT check_key FROM industry_template_checks WHERE template_id=%s AND is_enabled=1",
            (template_id,),
        )
        checks = db.fetchall()
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
        vetting_total, monitoring_price, template_id = _calculate_agency_vetting_cost(
            db, agency_id, include_monitoring=True
        )
        line_items: list[dict] = []
        if template_id:
            db.execute(
                "SELECT check_type, label, sell_price FROM industry_check_pricing "
                "WHERE industry_template_id=%s AND is_active=1",
                (template_id,),
            )
            for row in db.fetchall():
                p = dict(row)
                line_items.append({
                    "check_type": p["check_type"],
                    "label": p["label"],
                    "sell_price": p.get("sell_price") or 0,
                })
        return {
            "vetting_total": vetting_total,
            "monitoring_annual_price": monitoring_price,
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
        db.execute(
            "SELECT name, billing_mode, stripe_customer_id, discount_percent FROM agencies WHERE id=%s",
            (agency_id,),
        )
        agency_row = db.fetchone()
        agency_data = dict(agency_row) if agency_row else {}
        agency_name = agency_data.get("name", "Unknown Agency")
        billing_mode = agency_data.get("billing_mode") or "manual_invoicing"
        discount_pct = float(agency_data.get("discount_percent") or 0)

        # Check if there's already a pending invite for this email from this agency
        db.execute(
            "SELECT id FROM agency_invites WHERE agency_id=%s AND candidate_email=%s AND status='pending'",
            (agency_id, data.candidate_email),
        )
        existing = db.fetchone()
        if existing:
            raise HTTPException(
                status_code=400,
                detail="A pending invite already exists for this email",
            )

        # Calculate vetting cost from the SAME source the cost-confirmation popup
        # reads (industry_check_pricing). This keeps the quoted price and the
        # billed amount in sync.
        # First year monitoring is always included in the full vetting price.
        vetting_cost, monitoring_cost, _template_id = _calculate_agency_vetting_cost(
            db, agency_id, include_monitoring=True
        )

        # Apply agency discount if set
        if discount_pct > 0:
            vetting_cost = vetting_cost * (1 - discount_pct / 100)
            monitoring_cost = monitoring_cost * (1 - discount_pct / 100)

        db.execute(
            """INSERT INTO agency_invites (id, agency_id, candidate_email, invite_code, status, created_at, include_monitoring, vetting_cost, monitoring_cost, sub_account_id)
               VALUES (%s, %s, %s, %s, 'pending', %s, %s, %s, %s, %s)""",
            (invite_id, agency_id, data.candidate_email, invite_code, now,
             1, round(vetting_cost, 2), round(monitoring_cost, 2),
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
                invite_id=invite_id,
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
                """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at, invite_id)
                   VALUES (%s, %s, 'full_vetting', 'Full Automated Vetting - ' || %s, %s, %s, 'pending', 'stripe', %s, %s, %s)""",
                (inv_id, agency_id, data.candidate_email, cost_amount,
                 round(vetting_cost, 2), due_date, now, invite_id),
            )
            # First year monitoring is included in the full vetting price — no separate invoice
            payment_info["payment_required"] = True
            payment_info["status"] = "awaiting_payment"
            payment_info["invoice_id"] = inv_id
            payment_info["amount"] = round(vetting_cost, 2)

        else:
            # manual_invoicing — create pending invoice, no Stripe redirect
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at, invite_id)
                   VALUES (%s, %s, 'full_vetting', 'Full Automated Vetting - ' || %s, %s, %s, 'pending', 'manual', %s, %s, %s)""",
                (inv_id, agency_id, data.candidate_email, cost_amount,
                 round(vetting_cost, 2), due_date, now, invite_id),
            )
            # First year monitoring is included in the full vetting price — no separate invoice
            payment_info["status"] = "invoice_created"
            payment_info["invoice_id"] = inv_id

    # Send candidate invite email
    try:
        reload_email_config()
        base_url = os.environ.get("BASE_URL", str(request.base_url).rstrip("/"))
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
        db.execute("SELECT name FROM agencies WHERE id=%s", (agency_id,))
        agency_row = db.fetchone()
        agency_name = dict(agency_row)["name"] if agency_row else "Unknown Agency"

        db.execute(
            "SELECT * FROM agency_invites WHERE agency_id=%s ORDER BY created_at DESC",
            (agency_id,),
        )
        rows = db.fetchall()

        results = []
        for row in rows:
            d = dict(row)
            d["agency_name"] = agency_name
            results.append(d)
        return results


@router.delete("/invites/{invite_id}")
async def revoke_invite(invite_id: str, current_user: dict = Depends(get_current_user)):
    """Revoke a pending invite and cancel/refund the associated billing line.

    Billing lifecycle on revoke:
    - manual_invoicing: any pending invoice for this invite is marked cancelled
      so it isn't included in the next manual bill.
    - credit_pack / subscription: credits consumed by the invite are refunded
      (credits_used decremented, paid invoice marked cancelled, reverse credit
      transaction recorded). Takes effect immediately.
    - online_payment (PAYG):
        * unpaid invoice → cancelled immediately, no charge.
        * paid invoice → flagged refund_status='pending_admin_approval' for an
          admin to approve before Stripe refund is issued.
    """
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    refund_summary: list[dict] = []

    with get_db() as db:
        db.execute(
            "SELECT * FROM agency_invites WHERE id=%s AND agency_id=%s",
            (invite_id, agency_id),
        )
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invite not found")
        invite = dict(row)
        if invite["status"] != "pending":
            raise HTTPException(status_code=400, detail="Can only revoke pending invites")

        db.execute(
            "SELECT billing_mode FROM agencies WHERE id=%s", (agency_id,)
        )
        arow = db.fetchone()
        billing_mode = (dict(arow).get("billing_mode") if arow else None) or "manual_invoicing"

        # Cancel / refund associated invoices
        db.execute(
            "SELECT * FROM invoices WHERE invite_id=%s AND agency_id=%s",
            (invite_id, agency_id),
        )
        invoices = [dict(r) for r in db.fetchall()]

        for inv in invoices:
            status = (inv.get("status") or "").lower()
            if status in ("cancelled", "void", "refunded"):
                continue

            if status == "paid":
                # Already paid — refund flow depends on how it was paid.
                if billing_mode in ("subscription", "credit_pack"):
                    # Credit-pack paid: refund credits and cancel the invoice now.
                    db.execute(
                        """UPDATE invoices
                           SET status='cancelled', cancelled_at=%s,
                               refund_status='refunded', refund_resolved_at=%s
                           WHERE id=%s""",
                        (now, now, inv["id"]),
                    )
                    refund_summary.append({
                        "invoice_id": inv["id"],
                        "action": "credit_refunded",
                        "sell_amount": inv.get("sell_amount") or 0,
                    })
                else:
                    # PAYG paid: requires admin approval before a real refund is issued.
                    db.execute(
                        """UPDATE invoices
                           SET refund_status='pending_admin_approval',
                               refund_requested_at=%s
                           WHERE id=%s""",
                        (now, inv["id"]),
                    )
                    refund_summary.append({
                        "invoice_id": inv["id"],
                        "action": "payg_refund_pending_admin_approval",
                        "sell_amount": inv.get("sell_amount") or 0,
                    })
            else:
                # Pending / unpaid invoice — cancel outright.
                db.execute(
                    "UPDATE invoices SET status='cancelled', cancelled_at=%s WHERE id=%s",
                    (now, inv["id"]),
                )
                refund_summary.append({
                    "invoice_id": inv["id"],
                    "action": "cancelled",
                    "sell_amount": inv.get("sell_amount") or 0,
                })

        # Reverse any credit consumption for this invite
        db.execute(
            "SELECT * FROM credit_transactions WHERE invite_id=%s AND agency_id=%s "
            "AND (reversed_at IS NULL) AND (is_overage IS NULL OR is_overage=0)",
            (invite_id, agency_id),
        )
        txns = [dict(r) for r in db.fetchall()]
        credits_refunded = 0.0
        for txn in txns:
            consumed = float(txn.get("credits_consumed") or 0)
            if consumed <= 0:
                continue
            db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=%s AND status='active' "
                "ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            )
            sub_row = db.fetchone()
            if sub_row:
                sub = dict(sub_row)
                new_used = max(0.0, float(sub.get("credits_used") or 0) - consumed)
                db.execute(
                    "UPDATE agency_subscriptions SET credits_used=%s WHERE id=%s",
                    (new_used, sub["id"]),
                )
                balance_after = max(0.0, float(sub.get("credits_total") or 0) - new_used)
            else:
                balance_after = 0.0

            db.execute(
                "UPDATE credit_transactions SET reversed_at=%s WHERE id=%s",
                (now, txn["id"]),
            )
            # Record the reversal as its own transaction for audit.
            db.execute(
                """INSERT INTO credit_transactions
                   (id, agency_id, candidate_id, check_type, credits_consumed, credit_balance_after,
                    unit_cost, charge_amount, is_overage, description, created_at, invite_id)
                   VALUES (%s, %s, %s, %s, %s, %s, 0, 0, 0, %s, %s, %s)""",
                (generate_id(), agency_id, txn.get("candidate_id"),
                 txn.get("check_type") or "full_vetting",
                 -consumed, balance_after,
                 f"Refund (invite revoked) — {invite.get('candidate_email','')}",
                 now, invite_id),
            )
            credits_refunded += consumed

        db.execute(
            "UPDATE agency_invites SET status='revoked' WHERE id=%s",
            (invite_id,),
        )

    return {
        "status": "revoked",
        "billing_mode": billing_mode,
        "invoices_updated": refund_summary,
        "credits_refunded": round(credits_refunded, 2),
    }


@router.post("/invites/{invite_id}/resend")
async def resend_invite(invite_id: str, request: Request, current_user: dict = Depends(get_current_user)):
    """Resend the invite email for a pending invite."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    with get_db() as db:
        db.execute(
            "SELECT * FROM agency_invites WHERE id=%s AND agency_id=%s",
            (invite_id, agency_id),
        )
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invite not found")
        invite = dict(row)
        if invite["status"] not in ("pending", "sent"):
            raise HTTPException(status_code=400, detail="Can only resend pending or sent invites")

        db.execute("SELECT name FROM agencies WHERE id=%s", (agency_id,))
        agency_row = db.fetchone()
        agency_name = dict(agency_row)["name"] if agency_row else "Unknown Agency"

        # Send the invite email again
        try:
            reload_email_config()
            base_url = os.environ.get("BASE_URL", str(request.base_url).rstrip("/"))
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
        db.execute(
            """SELECT ai.*, a.name as agency_name FROM agency_invites ai
               JOIN agencies a ON ai.agency_id = a.id
               WHERE ai.invite_code=%s AND ai.status='pending'""",
            (invite_code,),
        )
        row = db.fetchone()
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
        db.execute(
            "SELECT * FROM agency_invites WHERE invite_code=%s AND status='pending'",
            (invite_code,),
        )
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invalid or expired invite code")

        invite = dict(row)

        # Verify the candidate email matches the invite
        db.execute(
            "SELECT email FROM candidates WHERE id=%s",
            (candidate_id,),
        )
        candidate_row = db.fetchone()
        if candidate_row:
            candidate_email = dict(candidate_row)["email"]
            if candidate_email.lower() != invite["candidate_email"].lower():
                raise HTTPException(
                    status_code=400,
                    detail="This invite was sent to a different email address",
                )

        # Check if already assigned
        db.execute(
            "SELECT 1 FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
            (invite["agency_id"], candidate_id),
        )
        existing = db.fetchone()
        if existing:
            # Already assigned, just update invite status
            db.execute(
                "UPDATE agency_invites SET status='accepted', candidate_id=%s, accepted_at=%s WHERE id=%s",
                (candidate_id, now, invite["id"]),
            )
            return {"status": "already_assigned", "message": "You are already linked to this agency"}

        # Link candidate to agency with monitoring preferences from invite
        include_monitoring = invite.get("include_monitoring", 0)
        vetting_cost = invite.get("vetting_cost", 0)
        monitoring_cost = invite.get("monitoring_cost", 0)
        sub_account_id = invite.get("sub_account_id")

        # If monitoring included, first year is covered by the full vetting credit
        monitoring_started = now if include_monitoring else None
        monitoring_expires = None
        if include_monitoring:
            from datetime import timedelta as _td
            monitoring_expires = (datetime.fromisoformat(now.replace("Z", "+00:00")) + _td(days=365)).isoformat()

        db.execute(
            """INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at, annual_monitoring, vetting_cost_accepted, monitoring_cost_accepted, invited_by_sub_account_id, monitoring_active, monitoring_started_at, monitoring_expires_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (invite["agency_id"], candidate_id, now, include_monitoring, vetting_cost, monitoring_cost, sub_account_id,
             1 if include_monitoring else 0, monitoring_started, monitoring_expires),
        )

        # Update invite status
        db.execute(
            "UPDATE agency_invites SET status='accepted', candidate_id=%s, accepted_at=%s WHERE id=%s",
            (candidate_id, now, invite["id"]),
        )

        # Link existing full_vetting invoices (created at invite time without candidate_id)
        # to this candidate so billing guards work correctly
        candidate_email_lower = invite["candidate_email"].lower()
        db.execute(
            """UPDATE invoices SET candidate_id=%s
               WHERE agency_id=%s AND check_type IN ('full_vetting', 'vetting')
               AND (candidate_id IS NULL OR candidate_id = '')
               AND LOWER(description) LIKE %s""",
            (candidate_id, invite["agency_id"], f"%{candidate_email_lower}%"),
        )
        # Also link annual_monitoring invoices
        db.execute(
            """UPDATE invoices SET candidate_id=%s
               WHERE agency_id=%s AND check_type='annual_monitoring'
               AND (candidate_id IS NULL OR candidate_id = '')
               AND LOWER(description) LIKE %s""",
            (candidate_id, invite["agency_id"], f"%{candidate_email_lower}%"),
        )

    return {"status": "accepted", "message": "You have been linked to the agency. Complete your vetting checks to proceed."}


@router.get("/my-agencies")
async def get_my_agencies(current_user: dict = Depends(get_current_user)):
    """Get agencies that a candidate is linked to."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    with get_db() as db:
        db.execute(
            """SELECT a.id, a.name, a.email, a.contact_name, ac.assigned_at
               FROM agencies a
               JOIN agency_candidates ac ON a.id = ac.agency_id
               WHERE ac.candidate_id=%s""",
            (current_user["sub"],),
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


@router.get("/pending-invites")
async def get_pending_invites(current_user: dict = Depends(get_current_user)):
    """Get pending invites for the current candidate (by their email)."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    with get_db() as db:
        db.execute(
            "SELECT email FROM candidates WHERE id=%s", (current_user["sub"],)
        )
        candidate_row = db.fetchone()
        if not candidate_row:
            return []

        candidate_email = dict(candidate_row)["email"]
        db.execute(
            """SELECT ai.*, a.name as agency_name FROM agency_invites ai
               JOIN agencies a ON ai.agency_id = a.id
               WHERE ai.candidate_email=%s AND ai.status='pending'""",
            (candidate_email,),
        )
        rows = db.fetchall()
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
        db.execute(
            "SELECT * FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
            (agency_id, candidate_id),
        )
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found in your agency")

        db.execute(
            "UPDATE agency_candidates SET employment_status=%s, employment_status_updated_at=%s WHERE agency_id=%s AND candidate_id=%s",
            (data.employment_status, now, agency_id, candidate_id),
        )

    return {"status": "updated", "employment_status": data.employment_status}


# ── Agency Services / Billing Breakdown ──────────────────────────

@router.get("/my-services")
async def get_my_services(current_user: dict = Depends(get_current_user)):
    """Get the agency's services rendered breakdown based on completed vetting checks."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]

    with get_db() as db:
        # Get all candidate IDs for this agency
        db.execute(
            "SELECT candidate_id FROM agency_candidates WHERE agency_id=%s",
            (agency_id,),
        )
        cand_rows = db.fetchall()
        candidate_ids = [dict(r)["candidate_id"] for r in cand_rows]

        if not candidate_ids:
            return {"services": [], "total_cost": 0, "total_revenue": 0, "total_margin": 0}

        # Load industry pricing for the agency
        from app.routes.subscription_plans import _sync_industry_pricing
        template_id = _resolve_agency_template_id(db, agency_id)

        # Build pricing lookup
        pricing = {}
        if template_id:
            _sync_industry_pricing(db, template_id)
            db.execute(
                "SELECT check_type, label, sell_price, third_party_cost FROM industry_check_pricing "
                "WHERE industry_template_id=%s AND is_active=1",
                (template_id,),
            )
            for row in db.fetchall():
                p = dict(row)
                pricing[p["check_type"]] = p
        # Fallback to pricing_settings
        db.execute("SELECT check_type, label, sell_price, cost_price FROM pricing_settings")
        for row in db.fetchall():
            p = dict(row)
            if p["check_type"] not in pricing:
                pricing[p["check_type"]] = {
                    "check_type": p["check_type"],
                    "label": p["label"],
                    "sell_price": p["sell_price"],
                    "third_party_cost": p.get("cost_price", 0),
                }

        # Count completed checks per type across all candidates
        placeholders = ",".join(["%s"] * len(candidate_ids))
        services_map = {}

        # Identity checks
        db.execute(
            f"SELECT COUNT(*) as cnt FROM identity_checks WHERE candidate_id IN ({placeholders}) AND result IS NOT NULL",
            candidate_ids,
        )
        cnt = dict(db.fetchone())["cnt"]
        if cnt > 0:
            p = pricing.get("identity", pricing.get("identity_verified", {}))
            services_map["identity"] = {"check_type": "identity", "label": p.get("label", "Identity Verification"), "count": cnt, "sell_price": float(p.get("sell_price", 0)), "third_party_cost": float(p.get("third_party_cost", 0))}

        # Right to Work
        db.execute(
            f"SELECT COUNT(*) as cnt FROM right_to_work_checks WHERE candidate_id IN ({placeholders}) AND verified=1",
            candidate_ids,
        )
        cnt = dict(db.fetchone())["cnt"]
        if cnt > 0:
            p = pricing.get("right_to_work", pricing.get("right_to_work_valid", {}))
            services_map["right_to_work"] = {"check_type": "right_to_work", "label": p.get("label", "Right to Work"), "count": cnt, "sell_price": float(p.get("sell_price", 0)), "third_party_cost": float(p.get("third_party_cost", 0))}

        # DBS
        db.execute(
            f"SELECT COUNT(*) as cnt FROM dbs_checks WHERE candidate_id IN ({placeholders}) AND result IS NOT NULL",
            candidate_ids,
        )
        cnt = dict(db.fetchone())["cnt"]
        if cnt > 0:
            p = pricing.get("dbs", pricing.get("dbs_enhanced", pricing.get("dbs_valid", {})))
            services_map["dbs"] = {"check_type": "dbs", "label": p.get("label", "DBS Check"), "count": cnt, "sell_price": float(p.get("sell_price", 0)), "third_party_cost": float(p.get("third_party_cost", 0))}

        # CV Analysis
        db.execute(
            f"SELECT COUNT(*) as cnt FROM cv_analyses WHERE candidate_id IN ({placeholders}) AND status IS NOT NULL",
            candidate_ids,
        )
        cnt = dict(db.fetchone())["cnt"]
        if cnt > 0:
            p = pricing.get("cv_analysis", pricing.get("cv_validated", {}))
            services_map["cv_analysis"] = {"check_type": "cv_analysis", "label": p.get("label", "CV Analysis"), "count": cnt, "sell_price": float(p.get("sell_price", 0)), "third_party_cost": float(p.get("third_party_cost", 0))}

        # Employment Verification
        db.execute(
            f"SELECT COUNT(*) as cnt FROM employment_verifications WHERE candidate_id IN ({placeholders}) AND status IN ('verified','completed')",
            candidate_ids,
        )
        cnt = dict(db.fetchone())["cnt"]
        if cnt > 0:
            p = pricing.get("employment", pricing.get("employment_verified", {}))
            services_map["employment"] = {"check_type": "employment", "label": p.get("label", "Employment Verification"), "count": cnt, "sell_price": float(p.get("sell_price", 0)), "third_party_cost": float(p.get("third_party_cost", 0))}

        # References
        db.execute(
            f"SELECT COUNT(*) as cnt FROM references_ WHERE candidate_id IN ({placeholders}) AND status IN ('completed','verified')",
            candidate_ids,
        )
        cnt = dict(db.fetchone())["cnt"]
        if cnt > 0:
            p = pricing.get("references", pricing.get("references_verified", {}))
            services_map["references"] = {"check_type": "references", "label": p.get("label", "Professional References"), "count": cnt, "sell_price": float(p.get("sell_price", 0)), "third_party_cost": float(p.get("third_party_cost", 0))}

        # Registration
        db.execute(
            f"SELECT COUNT(*) as cnt FROM registration_checks WHERE candidate_id IN ({placeholders}) AND is_active=1",
            candidate_ids,
        )
        cnt = dict(db.fetchone())["cnt"]
        if cnt > 0:
            p = pricing.get("registration", pricing.get("registration_active", {}))
            services_map["registration"] = {"check_type": "registration", "label": p.get("label", "Professional Registration"), "count": cnt, "sell_price": float(p.get("sell_price", 0)), "third_party_cost": float(p.get("third_party_cost", 0))}

        # Build services array
        services = []
        total_cost = 0.0
        total_revenue = 0.0
        for svc in services_map.values():
            total_sell = round(svc["count"] * svc["sell_price"], 2)
            total_cost_item = round(svc["count"] * svc["third_party_cost"], 2)
            services.append({
                "check_type": svc["check_type"],
                "label": svc["label"],
                "count": svc["count"],
                "sell_price": svc["sell_price"],
                "total_sell": total_sell,
                "third_party_cost": svc["third_party_cost"],
                "total_cost": total_cost_item,
            })
            total_revenue += total_sell
            total_cost += total_cost_item

        return {
            "services": services,
            "total_cost": round(total_cost, 2),
            "total_revenue": round(total_revenue, 2),
            "total_margin": round(total_revenue - total_cost, 2),
        }


# ── Partial Re-vetting ────────────────────────────────────────────

class RevetRequest(BaseModel):
    sections: list[str]  # e.g. ["dbs"], ["dbs", "training"]


@router.get("/revet-pricing")
async def get_revet_pricing(current_user: dict = Depends(get_current_user)):
    """Get re-vet check pricing for the agency (uses industry pricing matrix)."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")
    agency_id = current_user["sub"]
    with get_db() as db:
        db.execute("SELECT industry_template_id, discount_percent, billing_mode FROM agencies WHERE id=%s", (agency_id,))
        ag = db.fetchone()
        ag_data = dict(ag) if ag else {}
        template_id = ag_data.get("industry_template_id")
        discount_pct = float(ag_data.get("discount_percent") or 0)
        billing_mode = ag_data.get("billing_mode") or "manual_invoicing"

        # Build industry pricing lookup
        industry_pricing: dict[str, dict] = {}
        if template_id:
            db.execute(
                "SELECT check_type, label, sell_price FROM industry_check_pricing "
                "WHERE industry_template_id=%s AND is_active=1",
                (template_id,),
            )
            for ipr in db.fetchall():
                ip = dict(ipr)
                industry_pricing[ip["check_type"]] = ip

        # Map re-vet section keys to industry_check_pricing check_type keys
        # Industry pricing uses status-based keys like identity_verified, dbs_valid, etc.
        section_to_industry_key = {
            "identity": "identity_verified", "rtw": "right_to_work_valid",
            "dbs": "dbs_valid", "cv": "cv_validated",
            "registration": "registration_active", "references": "references_verified",
            "training": "training_compliant", "monitoring": "monitoring",
        }
        # Fallback keys for pricing_settings table
        section_to_pricing_key = {
            "identity": "identity", "rtw": "right_to_work",
            "dbs": "enhanced_dbs", "cv": "cv_analysis",
            "registration": "registration", "references": "references",
            "training": "training_verification", "monitoring": "monitoring",
        }

        sections = []
        for section_key, industry_key in section_to_industry_key.items():
            ip = industry_pricing.get(industry_key)
            if ip:
                price = float(ip.get("sell_price") or 0)
                label = ip.get("label") or industry_key.replace("_", " ").title()
            else:
                fallback_key = section_to_pricing_key.get(section_key, section_key)
                db.execute("SELECT sell_price, label FROM pricing_settings WHERE check_type=%s", (fallback_key,))
                pr = db.fetchone()
                if pr:
                    pd = dict(pr)
                    price = float(pd.get("sell_price") or 0)
                    label = pd.get("label") or section_key.replace("_", " ").title()
                else:
                    price = 0
                    label = section_key.replace("_", " ").title()
            if discount_pct > 0:
                price = price * (1 - discount_pct / 100)
            sections.append({"key": section_key, "label": label, "price": round(price, 2)})

        # Credit pack info
        credit_info = None
        if billing_mode in ("subscription", "credit_pack"):
            from app.services.billing import BillingService
            credit_info = BillingService.get_remaining_checks(agency_id)

        return {
            "sections": sections,
            "billing_mode": billing_mode,
            "credit_info": credit_info,
        }


@router.post("/candidates/{candidate_id}/request-revet")
async def request_revet(
    candidate_id: str,
    data: RevetRequest,
    current_user: dict = Depends(get_current_user),
):
    """Agency requests partial re-vetting for a hired candidate."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    valid_sections = {"identity", "rtw", "dbs", "cv", "registration", "references", "training", "monitoring"}
    for s in data.sections:
        if s not in valid_sections:
            raise HTTPException(status_code=400, detail=f"Invalid section: {s}. Valid: {', '.join(valid_sections)}")

    agency_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    token = secrets.token_urlsafe(24)

    import json
    with get_db() as db:
        # Verify agency owns the candidate
        db.execute(
            "SELECT * FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
            (agency_id, candidate_id),
        )
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Candidate not found in your agency")

        # Get candidate info
        db.execute("SELECT first_name, last_name, email FROM candidates WHERE id=%s", (candidate_id,))
        cand = db.fetchone()
        cand_data = dict(cand) if cand else {}

        # Get agency name
        db.execute("SELECT name, industry_template_id, discount_percent FROM agencies WHERE id=%s", (agency_id,))
        agency = db.fetchone()
        agency_data = dict(agency) if agency else {}
        agency_name = agency_data.get("name") or "Unknown"
        template_id = agency_data.get("industry_template_id")
        discount_pct = float(agency_data.get("discount_percent") or 0)

        # Build industry pricing lookup (preferred) with fallback to pricing_settings
        industry_pricing: dict[str, dict] = {}
        if template_id:
            db.execute(
                "SELECT check_type, label, sell_price FROM industry_check_pricing "
                "WHERE industry_template_id=%s AND is_active=1",
                (template_id,),
            )
            for ipr in db.fetchall():
                ip = dict(ipr)
                industry_pricing[ip["check_type"]] = ip

        # Map re-vet section keys to industry_check_pricing check_type keys
        # Industry pricing uses status-based keys like identity_verified, dbs_valid, etc.
        section_to_industry_key = {
            "identity": "identity_verified", "rtw": "right_to_work_valid",
            "dbs": "dbs_valid", "cv": "cv_validated",
            "registration": "registration_active", "references": "references_verified",
            "training": "training_compliant", "monitoring": "monitoring",
        }
        section_to_pricing_key = {
            "identity": "identity", "rtw": "right_to_work",
            "dbs": "enhanced_dbs", "cv": "cv_analysis",
            "registration": "registration", "references": "references",
            "training": "training_verification", "monitoring": "monitoring",
        }

        # Get pricing for the sections using industry pricing first, then fallback
        total_cost = 0.0
        section_costs = []
        for section in data.sections:
            industry_key = section_to_industry_key.get(section, section)
            ip = industry_pricing.get(industry_key)
            if ip:
                price = float(ip.get("sell_price") or 0)
                label = ip.get("label") or section.replace("_", " ").title()
            else:
                fallback_key = section_to_pricing_key.get(section, section)
                db.execute(
                    "SELECT sell_price, label FROM pricing_settings WHERE check_type=%s", (fallback_key,)
                )
                price_row = db.fetchone()
                if price_row:
                    pd = dict(price_row)
                    price = float(pd.get("sell_price") or 0)
                    label = pd.get("label") or section.replace("_", " ").title()
                else:
                    price = 0
                    label = section.replace("_", " ").title()
            if discount_pct > 0:
                price = price * (1 - discount_pct / 100)
            section_costs.append({"section": section, "label": label, "cost": round(price, 2)})
            total_cost += price

        revet_id = generate_id()
        db.execute(
            """INSERT INTO revet_requests (id, agency_id, candidate_id, sections, token, status, created_at)
               VALUES (%s, %s, %s, %s, %s, 'pending', %s)""",
            (revet_id, agency_id, candidate_id, json.dumps(data.sections), token, now),
        )

        # Bill the agency based on their payment method
        db.execute("SELECT billing_mode FROM agencies WHERE id=%s", (agency_id,))
        bm_row = db.fetchone()
        billing_mode = dict(bm_row).get("billing_mode") or "manual_invoicing" if bm_row else "manual_invoicing"

        payment_info: dict = {"billing_mode": billing_mode}
        due_date = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
        candidate_name = f"{cand_data.get('first_name', '')} {cand_data.get('last_name', '')}".strip()

        if billing_mode in ("subscription", "credit_pack"):
            from app.services.billing import BillingService
            # Deduct from credit pack — use partial credit rates for each section
            pcr_map = {
                "dbs": "dbs_recheck", "rtw": "rtw_recheck",
                "registration": "registration_check", "references": "reference_recheck",
                "training": "training_update", "monitoring": "monitoring_renewal",
            }
            total_deducted = 0.0
            credits_remaining = 0
            for sc in section_costs:
                pcr_key = pcr_map.get(sc["section"], sc["section"])
                desc = f"Re-Vet {sc['label']} — {candidate_name}"
                result = BillingService.use_subscription_check(
                    agency_id, candidate_id, desc,
                    round(sc["cost"], 2), 0, pcr_key,
                )
                if result.get("within_credit"):
                    total_deducted += result.get("credits_used", 0)
                    credits_remaining = result.get("credits_remaining", 0)
            payment_info["status"] = "paid_by_subscription"
            payment_info["credits_deducted"] = round(total_deducted, 4)
            payment_info["credits_remaining"] = credits_remaining

        elif billing_mode == "online_payment":
            inv_id = generate_id()
            description = f"Re-Vet ({len(data.sections)} checks) — {candidate_name}"
            db.execute(
                """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description,
                   cost_amount, sell_amount, status, payment_method, due_date, created_at)
                   VALUES (%s,%s,%s,'revet',%s,0,%s,'pending','stripe',%s,%s)""",
                (inv_id, agency_id, candidate_id, description,
                 round(total_cost, 2), due_date, now),
            )
            payment_info["status"] = "awaiting_payment"
            payment_info["invoice_id"] = inv_id
            payment_info["amount"] = round(total_cost, 2)
        else:
            inv_id = generate_id()
            description = f"Re-Vet ({len(data.sections)} checks) — {candidate_name}"
            db.execute(
                """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description,
                   cost_amount, sell_amount, status, payment_method, due_date, created_at)
                   VALUES (%s,%s,%s,'revet',%s,0,%s,'pending','manual',%s,%s)""",
                (inv_id, agency_id, candidate_id, description,
                 round(total_cost, 2), due_date, now),
            )
            payment_info["status"] = "invoice_created"
            payment_info["invoice_id"] = inv_id
            payment_info["amount"] = round(total_cost, 2)

        # If monitoring was selected, activate/extend monitoring
        if "monitoring" in data.sections:
            current_expiry = dict(row).get("monitoring_expires_at")
            if current_expiry:
                try:
                    base = datetime.fromisoformat(current_expiry)
                    now_dt = datetime.now(timezone.utc)
                    new_expiry = (base + timedelta(days=365)).isoformat() if base > now_dt else (now_dt + timedelta(days=365)).isoformat()
                except (ValueError, TypeError):
                    new_expiry = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
            else:
                new_expiry = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
            db.execute(
                """UPDATE agency_candidates SET monitoring_active=1, monitoring_expires_at=%s,
                   monitoring_started_at=COALESCE(monitoring_started_at, %s), annual_monitoring=1
                   WHERE agency_id=%s AND candidate_id=%s""",
                (new_expiry, now, agency_id, candidate_id),
            )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'revet_request', %s, 'created', %s, %s, %s)""",
            (generate_id(), revet_id, agency_id,
             json.dumps({"sections": data.sections, "candidate_id": candidate_id, "billing": payment_info}), now),
        )

    return {
        "id": revet_id,
        "token": token,
        "candidate_name": candidate_name,
        "candidate_email": cand_data.get("email"),
        "agency_name": agency_name,
        "sections": data.sections,
        "section_costs": section_costs,
        "total_cost": round(total_cost, 2),
        "payment": payment_info,
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
        db.execute(
            """SELECT rr.*, c.first_name, c.last_name, c.email
               FROM revet_requests rr
               JOIN candidates c ON rr.candidate_id = c.id
               WHERE rr.agency_id=%s
               ORDER BY rr.created_at DESC""",
            (agency_id,),
        )
        rows = db.fetchall()
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
        db.execute(
            """SELECT c.id, c.first_name, c.last_name, c.email, c.compliance_score,
                      c.compliance_status, c.created_at,
                      ac.employment_status, ac.employment_status_updated_at, ac.assigned_at,
                      ac.annual_monitoring, ac.vetting_cost_accepted, ac.monitoring_cost_accepted,
                      ac.monitoring_active, ac.monitoring_started_at, ac.monitoring_expires_at
               FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               WHERE ac.agency_id=%s
               ORDER BY c.created_at DESC""",
            (agency_id,),
        )
        rows = db.fetchall()
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
        db.execute(
            "SELECT id, agency_id, status FROM invoices WHERE id=%s", (invoice_id,)
        )
        inv = db.fetchone()
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


@router.post("/monitoring/renew/{candidate_id}")
async def renew_monitoring(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Renew annual monitoring for a candidate for another 12 months.
    Billing is routed via the agency's payment method:
    - credit_pack/subscription: deducts monitoring_renewal credits
    - online_payment: creates a pending Stripe invoice
    - manual_invoicing: creates a pending manual invoice
    """
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()
    due_date = (now + timedelta(days=30)).isoformat()

    with get_db() as db:
        # Verify the candidate belongs to this agency
        db.execute(
            """SELECT ac.*, c.first_name, c.last_name, c.email
               FROM agency_candidates ac
               JOIN candidates c ON ac.candidate_id = c.id
               WHERE ac.agency_id=%s AND ac.candidate_id=%s""",
            (agency_id, candidate_id),
        )
        ac_row = db.fetchone()
        if not ac_row:
            raise HTTPException(status_code=404, detail="Candidate not found in your agency")
        ac = dict(ac_row)

        # Get monitoring price from pricing_settings
        db.execute("SELECT sell_price, cost_price FROM pricing_settings WHERE check_type='monitoring'")
        pricing_row = db.fetchone()
        sell_price = float(dict(pricing_row).get("sell_price") or 50.0) if pricing_row else 50.0
        cost_price = float(dict(pricing_row).get("cost_price") or 5.0) if pricing_row else 5.0

        # Apply agency discount
        db.execute("SELECT discount_percent, billing_mode FROM agencies WHERE id=%s", (agency_id,))
        agency_row = db.fetchone()
        agency_data = dict(agency_row) if agency_row else {}
        discount_pct = float(agency_data.get("discount_percent") or 0)
        billing_mode = agency_data.get("billing_mode") or "manual_invoicing"

        if discount_pct > 0:
            sell_price = sell_price * (1 - discount_pct / 100)

        candidate_name = f"{ac.get('first_name', '')} {ac.get('last_name', '')}".strip()
        description = f"Annual Monitoring Renewal - {candidate_name}"

        # Calculate new expiry: extend from current expiry if still active, or from now
        current_expiry = ac.get("monitoring_expires_at")
        if current_expiry:
            try:
                base = datetime.fromisoformat(current_expiry)
                if base > now:
                    new_expiry = (base + timedelta(days=365)).isoformat()
                else:
                    new_expiry = (now + timedelta(days=365)).isoformat()
            except (ValueError, TypeError):
                new_expiry = (now + timedelta(days=365)).isoformat()
        else:
            new_expiry = (now + timedelta(days=365)).isoformat()

        payment_info = {"billing_mode": billing_mode, "payment_required": False}

        if billing_mode in ("subscription", "credit_pack"):
            from app.services.billing import BillingService
            result = BillingService.use_subscription_check(
                agency_id, candidate_id, description,
                round(sell_price, 2), round(cost_price, 2),
                "monitoring_renewal",
            )
            payment_info["subscription_result"] = result
            if result.get("within_credit"):
                payment_info["status"] = "paid_by_subscription"
                payment_info["credits_remaining"] = result.get("credits_remaining", 0)
            else:
                payment_info["payment_required"] = True
                payment_info["status"] = "credits_exceeded"
                payment_info["invoice_id"] = result.get("invoice_id")
                payment_info["amount"] = round(sell_price, 2)

        elif billing_mode == "online_payment":
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at)
                   VALUES (%s, %s, %s, 'monitoring_renewal', %s, %s, %s, 'pending', 'stripe', %s, %s)""",
                (inv_id, agency_id, candidate_id, description,
                 round(cost_price, 2), round(sell_price, 2), due_date, now_str),
            )
            payment_info["payment_required"] = True
            payment_info["status"] = "awaiting_payment"
            payment_info["invoice_id"] = inv_id
            payment_info["amount"] = round(sell_price, 2)

        else:
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, payment_method, due_date, created_at)
                   VALUES (%s, %s, %s, 'monitoring_renewal', %s, %s, %s, 'pending', 'manual', %s, %s)""",
                (inv_id, agency_id, candidate_id, description,
                 round(cost_price, 2), round(sell_price, 2), due_date, now_str),
            )
            payment_info["status"] = "invoice_created"
            payment_info["invoice_id"] = inv_id

        # Activate/extend monitoring
        db.execute(
            """UPDATE agency_candidates
               SET monitoring_active = 1,
                   monitoring_started_at = COALESCE(monitoring_started_at, %s),
                   monitoring_expires_at = %s,
                   annual_monitoring = 1
               WHERE agency_id=%s AND candidate_id=%s""",
            (now_str, new_expiry, agency_id, candidate_id),
        )

    return {
        "status": "renewed",
        "candidate_id": candidate_id,
        "monitoring_expires_at": new_expiry,
        "sell_price": round(sell_price, 2),
        "payment": payment_info,
    }
