"""Admin settings, analytics, and pricing routes."""
import io
import base64
import logging
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, List
from app.database import get_db
from app.utils.auth import get_current_user, generate_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


def require_admin(current_user: dict):
    if current_user["type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


# ── Pricing Settings ──────────────────────────────────────────────

class PricingUpdate(BaseModel):
    cost_price: Optional[float] = None
    sell_price: Optional[float] = None
    label: Optional[str] = None


@router.get("/pricing")
async def get_pricing(current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    with get_db() as db:
        db.execute("SELECT * FROM pricing_settings ORDER BY check_type")
        rows = db.fetchall()
        return [dict(r) for r in rows]


@router.put("/pricing/{check_type}")
async def update_pricing(check_type: str, data: PricingUpdate, current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("SELECT * FROM pricing_settings WHERE check_type=%s", (check_type,))
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Pricing setting not found")
        updates = {}
        if data.cost_price is not None:
            updates["cost_price"] = data.cost_price
        if data.sell_price is not None:
            updates["sell_price"] = data.sell_price
        if data.label is not None:
            updates["label"] = data.label
        if updates:
            updates["updated_at"] = now
            set_clause = ", ".join(f"{k}=%s" for k in updates.keys())
            values = list(updates.values()) + [check_type]
            db.execute(f"UPDATE pricing_settings SET {set_clause} WHERE check_type=%s", values)
        db.execute("SELECT * FROM pricing_settings WHERE check_type=%s", (check_type,))
        row = db.fetchone()
        return dict(row)


@router.post("/pricing/{check_type}/push-to-industries")
async def push_pricing_to_industries(check_type: str, current_user: dict = Depends(get_current_user)):
    """Push updated default pricing to all industry_check_pricing rows that match this check type.
    Uses the reverse mapping from pricing_settings check_type → template check_keys."""
    require_admin(current_user)
    from app.routes.subscription_plans import CHECK_KEY_TO_PRICING_TYPE

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        # Get the new default pricing
        db.execute("SELECT * FROM pricing_settings WHERE check_type=%s", (check_type,))
        default_row = db.fetchone()
        if not default_row:
            raise HTTPException(status_code=404, detail="Pricing setting not found")
        default = dict(default_row)
        new_cost = default.get("cost_price", 0)
        new_sell = default.get("sell_price", 0)

        # Build reverse mapping: pricing_settings check_type → list of template check_keys
        matching_check_keys = [ck for ck, pt in CHECK_KEY_TO_PRICING_TYPE.items() if pt == check_type]
        # Also include the check_type itself (some industry rows use check_type directly as check_type)
        matching_check_keys.append(check_type)
        matching_check_keys = list(set(matching_check_keys))

        # Update all matching industry_check_pricing rows
        placeholders = ",".join("?" for _ in matching_check_keys)
        db.execute(
            f"""UPDATE industry_check_pricing
                SET third_party_cost=%s, sell_price=%s, updated_at=%s
                WHERE check_type IN ({placeholders})""",
            [new_cost, new_sell, now] + matching_check_keys,
        )
        updated_count = result.rowcount

        return {"updated": updated_count, "check_type": check_type, "new_cost_price": new_cost, "new_sell_price": new_sell}


# ── Revenue & Financial Analytics ─────────────────────────────────

def _parse_date_range(period: str, date_from: str = None, date_to: str = None):
    """Return (start_date, end_date) as ISO strings based on period filter."""
    now = datetime.now(timezone.utc)
    if period == "mtd":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "ytd":
        start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "fytd":
        # UK financial year starts April 1
        if now.month >= 4:
            start = now.replace(month=4, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            start = now.replace(year=now.year - 1, month=4, day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif period == "custom" and date_from and date_to:
        start = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
    else:
        # Default: all time
        start = datetime(2020, 1, 1, tzinfo=timezone.utc)
        end = now
    return start.isoformat(), end.isoformat()


@router.get("/analytics/revenue")
async def get_revenue_analytics(
    period: str = "all",
    date_from: str = None,
    date_to: str = None,
    agency_id: str = None,
    current_user: dict = Depends(get_current_user),
):
    require_admin(current_user)
    start, end = _parse_date_range(period, date_from, date_to)

    with get_db() as db:
        # Get pricing for calculations
        db.execute("SELECT * FROM pricing_settings")
        pricing_rows = db.fetchall()
        pricing = {dict(r)["check_type"]: dict(r) for r in pricing_rows}

        # Get invoices in range
        query = "SELECT * FROM invoices WHERE created_at >= %s AND created_at <= %s"
        params = [start, end]
        if agency_id:
            query += " AND agency_id = %s"
            params.append(agency_id)
        db.execute(query, params)
        invoice_rows = db.fetchall()
        invoices = [dict(r) for r in invoice_rows]

        # Use adjusted_amount if admin has adjusted, otherwise use sell_amount
        def effective_revenue(inv):
            adj = inv.get("adjusted_amount")
            return adj if adj is not None else inv["sell_amount"]

        total_revenue = sum(effective_revenue(i) for i in invoices)
        total_cost = sum(i["cost_amount"] for i in invoices)
        total_margin = total_revenue - total_cost
        margin_pct = round((total_margin / total_revenue * 100) if total_revenue > 0 else 0, 1)

        # Revenue by check type
        by_check_type = {}
        for inv in invoices:
            ct = inv["check_type"] or "other"
            if ct not in by_check_type:
                by_check_type[ct] = {"revenue": 0.0, "cost": 0.0, "count": 0, "label": pricing.get(ct, {}).get("label", ct)}
            by_check_type[ct]["revenue"] += effective_revenue(inv)
            by_check_type[ct]["cost"] += inv["cost_amount"]
            by_check_type[ct]["count"] += 1

        # Revenue by agency
        by_agency = {}
        for inv in invoices:
            aid = inv["agency_id"]
            if aid not in by_agency:
                db.execute("SELECT name FROM agencies WHERE id=%s", (aid,))
                agency_row = db.fetchone()
                by_agency[aid] = {
                    "agency_name": dict(agency_row)["name"] if agency_row else "Unknown",
                    "revenue": 0.0, "cost": 0.0, "count": 0,
                }
            by_agency[aid]["revenue"] += effective_revenue(inv)
            by_agency[aid]["cost"] += inv["cost_amount"]
            by_agency[aid]["count"] += 1

        # Monthly breakdown
        monthly = {}
        for inv in invoices:
            month_key = inv["created_at"][:7] if inv["created_at"] else "unknown"
            if month_key not in monthly:
                monthly[month_key] = {"revenue": 0.0, "cost": 0.0, "count": 0}
            monthly[month_key]["revenue"] += effective_revenue(inv)
            monthly[month_key]["cost"] += inv["cost_amount"]
            monthly[month_key]["count"] += 1

        return {
            "period": period,
            "date_from": start,
            "date_to": end,
            "total_revenue": round(total_revenue, 2),
            "total_cost": round(total_cost, 2),
            "total_margin": round(total_margin, 2),
            "margin_percentage": margin_pct,
            "invoice_count": len(invoices),
            "by_check_type": by_check_type,
            "by_agency": by_agency,
            "monthly": dict(sorted(monthly.items())),
        }


@router.get("/analytics/operations")
async def get_operations_analytics(
    period: str = "all",
    date_from: str = None,
    date_to: str = None,
    agency_id: str = None,
    current_user: dict = Depends(get_current_user),
):
    require_admin(current_user)
    start, end = _parse_date_range(period, date_from, date_to)

    with get_db() as db:
        # Total candidates in period
        cand_query = "SELECT * FROM candidates WHERE created_at >= %s AND created_at <= %s"
        cand_params = [start, end]
        db.execute(cand_query, cand_params)
        candidates = [dict(r) for r in db.fetchall()]

        if agency_id:
            db.execute(
                "SELECT candidate_id FROM agency_candidates WHERE agency_id=%s", (agency_id,)
            )
            linked = db.fetchone()
            linked = db.fetchall()
            linked_ids = {dict(r)["candidate_id"] for r in linked}
            candidates = [c for c in candidates if c["id"] in linked_ids]

        total = len(candidates)
        compliant = sum(1 for c in candidates if c["compliance_status"] == "compliant")
        flagged = sum(1 for c in candidates if c["compliance_status"] in ("incomplete", "flagged"))
        pending = total - compliant - flagged

        # Check completion stats
        db.execute(
            "SELECT COUNT(*) as cnt FROM identity_checks WHERE completed_at >= %s AND completed_at <= %s",
            (start, end),
        )
        id_checks = db.fetchone()
        db.execute(
            "SELECT COUNT(*) as cnt FROM dbs_checks WHERE completed_at >= %s AND completed_at <= %s",
            (start, end),
        )
        dbs_checks = db.fetchone()
        db.execute(
            "SELECT COUNT(*) as cnt FROM right_to_work_checks WHERE checked_at >= %s AND checked_at <= %s",
            (start, end),
        )
        rtw_checks = db.fetchone()
        db.execute(
            "SELECT COUNT(*) as cnt FROM references_ WHERE completed_at >= %s AND completed_at <= %s",
            (start, end),
        )
        ref_checks = db.fetchone()
        db.execute(
            "SELECT COUNT(*) as cnt FROM employment_verifications WHERE completed_at >= %s AND completed_at <= %s",
            (start, end),
        )
        emp_checks = db.fetchone()

        # Average time to complete (simulated from candidate creation to compliance)
        db.execute(
            """SELECT cr.last_evaluated, c.created_at
               FROM compliance_records cr
               JOIN candidates c ON cr.candidate_id = c.id
               WHERE cr.overall_status = 'compliant'
               AND cr.last_evaluated >= %s AND cr.last_evaluated <= %s""",
            (start, end),
        )
        comp_records = db.fetchall()
        avg_hours = 0.0
        if comp_records:
            total_hours = 0.0
            count = 0
            for row in comp_records:
                r = dict(row)
                try:
                    created = datetime.fromisoformat(r["created_at"])
                    evaluated = datetime.fromisoformat(r["last_evaluated"])
                    hours = (evaluated - created).total_seconds() / 3600
                    if hours > 0:
                        total_hours += hours
                        count += 1
                except (ValueError, TypeError):
                    continue
            avg_hours = round(total_hours / count, 1) if count > 0 else 0.0

        success_rate = round((compliant / total * 100) if total > 0 else 0, 1)

        return {
            "period": period,
            "date_from": start,
            "date_to": end,
            "total_candidates": total,
            "compliant": compliant,
            "pending": pending,
            "flagged": flagged,
            "success_rate": success_rate,
            "avg_completion_hours": avg_hours,
            "checks_completed": {
                "identity": dict(id_checks)["cnt"] if id_checks else 0,
                "dbs": dict(dbs_checks)["cnt"] if dbs_checks else 0,
                "right_to_work": dict(rtw_checks)["cnt"] if rtw_checks else 0,
                "references": dict(ref_checks)["cnt"] if ref_checks else 0,
                "employment": dict(emp_checks)["cnt"] if emp_checks else 0,
            },
        }


@router.get("/analytics/agencies")
async def get_agency_analytics(
    period: str = "all",
    date_from: str = None,
    date_to: str = None,
    current_user: dict = Depends(get_current_user),
):
    require_admin(current_user)
    start, end = _parse_date_range(period, date_from, date_to)

    with get_db() as db:
        db.execute("SELECT * FROM agencies")
        agencies = [dict(r) for r in db.fetchall()]
        result = []
        for agency in agencies:
            # Get candidates for this agency
            db.execute(
                "SELECT candidate_id FROM agency_candidates WHERE agency_id=%s",
                (agency["id"],),
            )
            linked = db.fetchone()
            linked = db.fetchall()
            candidate_ids = [dict(r)["candidate_id"] for r in linked]

            total_candidates = len(candidate_ids)
            compliant = 0
            if candidate_ids:
                placeholders = ",".join("%s" for _ in candidate_ids)
                db.execute(
                    f"SELECT COUNT(*) as cnt FROM candidates WHERE id IN ({placeholders}) AND compliance_status='compliant'",
                    candidate_ids,
                )
                compliant_row = db.fetchone()
                compliant = dict(compliant_row)["cnt"] if compliant_row else 0

            # Revenue from invoices
            db.execute(
                "SELECT COALESCE(SUM(COALESCE(adjusted_amount, sell_amount)),0) as rev, COALESCE(SUM(cost_amount),0) as cost, COUNT(*) as cnt FROM invoices WHERE agency_id=%s AND created_at >= %s AND created_at <= %s",
                (agency["id"], start, end),
            )
            inv_row = db.fetchone()
            inv = dict(inv_row) if inv_row else {"rev": 0, "cost": 0, "cnt": 0}

            result.append({
                "agency_id": agency["id"],
                "agency_name": agency["name"],
                "email": agency["email"],
                "plan": agency["plan"],
                "monthly_fee": agency["monthly_fee"],
                "total_candidates": total_candidates,
                "compliant_candidates": compliant,
                "revenue": round(inv["rev"], 2),
                "cost": round(inv["cost"], 2),
                "margin": round(inv["rev"] - inv["cost"], 2),
                "invoice_count": inv["cnt"],
            })
        return result


# ── Invoice Management ────────────────────────────────────────────

class InvoiceCreate(BaseModel):
    agency_id: str
    candidate_id: Optional[str] = None
    check_type: Optional[str] = None
    description: str
    cost_amount: float = 0.0
    sell_amount: float = 0.0


@router.get("/invoices")
async def list_invoices(
    period: str = "all",
    date_from: str = None,
    date_to: str = None,
    agency_id: str = None,
    status: str = None,
    current_user: dict = Depends(get_current_user),
):
    require_admin(current_user)
    start, end = _parse_date_range(period, date_from, date_to)

    with get_db() as db:
        query = "SELECT i.*, a.name as agency_name FROM invoices i LEFT JOIN agencies a ON i.agency_id = a.id WHERE i.created_at >= %s AND i.created_at <= %s"
        params = [start, end]
        if agency_id:
            query += " AND i.agency_id = %s"
            params.append(agency_id)
        if status:
            query += " AND i.status = %s"
            params.append(status)
        query += " ORDER BY i.created_at DESC"
        db.execute(query, params)
        rows = db.fetchall()
        return [dict(r) for r in rows]


@router.post("/invoices")
async def create_invoice(data: InvoiceCreate, current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    invoice_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
            (invoice_id, data.agency_id, data.candidate_id, data.check_type, data.description, data.cost_amount, data.sell_amount, now),
        )
        db.execute("SELECT i.*, a.name as agency_name, a.email as agency_email FROM invoices i LEFT JOIN agencies a ON i.agency_id = a.id WHERE i.id=%s", (invoice_id,))
        row = db.fetchone()
        invoice = dict(row)

        # Send invoice notification email to agency
        agency_email = invoice.get("agency_email")
        if agency_email:
            try:
                from app.services.email_service import EmailService
                EmailService.send_invoice_notification(
                    agency_email=agency_email,
                    agency_name=invoice.get("agency_name", "Agency"),
                    invoice_id=invoice_id,
                    amount=data.sell_amount,
                    description=data.description,
                )
                logger.info(f"Invoice email sent to {agency_email} for invoice {invoice_id}")
            except Exception as e:
                logger.error(f"Failed to send invoice email: {e}")

        # Create a notification for the agency
        try:
            notif_id = generate_id()
            db.execute(
                """INSERT INTO notifications (id, user_id, user_type, category, title, message, is_read, created_at)
                   VALUES (%s, %s, 'agency', 'billing', %s, %s, 0, %s)""",
                (notif_id, data.agency_id, f"New Invoice: £{data.sell_amount:.2f}",
                 f"{data.description} - Please review and pay in your Billing tab.", now),
            )
        except Exception as e:
            logger.error(f"Failed to create invoice notification: {e}")

        return invoice


@router.post("/invoices/{invoice_id}/mark-paid")
async def mark_invoice_paid(invoice_id: str, current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("UPDATE invoices SET status='paid', paid_at=%s WHERE id=%s", (now, invoice_id))
        db.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invoice not found")
        return dict(row)


@router.post("/invoices/generate")
async def generate_invoices_for_agency(
    agency_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Generate invoices for all completed checks for an agency's candidates."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        # Get pricing
        db.execute("SELECT * FROM pricing_settings")
        pricing_rows = db.fetchall()
        pricing = {dict(r)["check_type"]: dict(r) for r in pricing_rows}

        # Get agency candidates
        db.execute(
            """SELECT c.* FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               WHERE ac.agency_id=%s""",
            (agency_id,),
        )
        candidates = db.fetchall()

        db.execute("SELECT name FROM agencies WHERE id=%s", (agency_id,))
        agency_row = db.fetchone()
        agency_name = dict(agency_row)["name"] if agency_row else "Unknown"

        generated = []
        for cand in candidates:
            c = dict(cand)
            cand_name = f"{c['first_name']} {c['last_name']}"

            # If candidate already has a full_vetting invoice from the invite
            # flow, skip per-check line items (but still generate re-vet invoices)
            db.execute(
                "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type='full_vetting'",
                (agency_id, c["id"]),
            )
            has_full_vetting = db.fetchone()

            # Per-check line items — only for candidates without a full_vetting charge
            if not has_full_vetting:
              # Check each type of check completed
              check_tables = [
                ("identity", "identity_checks", "completed_at"),
                ("dbs", "dbs_checks", "completed_at"),
                ("right_to_work", "right_to_work_checks", "checked_at"),
                ("cv_analysis", "cv_analyses", "analysed_at"),
                ("registration", "registration_checks", "last_checked"),
              ]
              for check_type, table, date_col in check_tables:
                db.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE candidate_id=%s AND status IN ('complete','completed','verified','clear')",
                    (c["id"],),
                )
                completed = db.fetchone()
                if completed and dict(completed)["cnt"] > 0:
                    # Check if invoice already exists
                    db.execute(
                        "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type=%s",
                        (agency_id, c["id"], check_type),
                    )
                    existing = db.fetchone()
                    if not existing and check_type in pricing:
                        p = pricing[check_type]
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                            (inv_id, agency_id, c["id"], check_type,
                             f"{p['label']} - {cand_name}", p["cost_price"], p["sell_price"], now),
                        )
                        generated.append(inv_id)

              # References (per reference)
              db.execute(
                "SELECT COUNT(*) as cnt FROM references_ WHERE candidate_id=%s AND status='completed'",
                (c["id"],),
              )
              refs = db.fetchone()
              ref_count = dict(refs)["cnt"] if refs else 0
              if ref_count > 0 and "references" in pricing:
                db.execute(
                    "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type='references'",
                    (agency_id, c["id"]),
                )
                existing = db.fetchone()
                if not existing:
                    p = pricing["references"]
                    inv_id = generate_id()
                    db.execute(
                        """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                        (inv_id, agency_id, c["id"], "references",
                         f"References ({ref_count}x) - {cand_name}", p["cost_price"] * ref_count, p["sell_price"] * ref_count, now),
                    )
                    generated.append(inv_id)

            # Re-vet requests (itemised per section) — always generated regardless of full_vetting
            db.execute(
                "SELECT rr.* FROM revet_requests rr WHERE rr.agency_id=%s AND rr.candidate_id=%s AND rr.status IN ('completed', 'pending')",
                (agency_id, c["id"]),
            )
            revet_rows = db.fetchall()
            for rr in revet_rows:
                rr_data = dict(rr)
                import json as _json
                sections = _json.loads(rr_data["sections"]) if rr_data["sections"] else []
                for sec in sections:
                    db.execute(
                        "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type=%s AND description LIKE '%Re-vet%'",
                        (agency_id, c["id"], f"revet_{sec}"),
                    )
                    existing_revet = db.fetchone()
                    if not existing_revet and sec in pricing:
                        p = pricing[sec]
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                            (inv_id, agency_id, c["id"], f"revet_{sec}",
                             f"Re-vet: {p['label']} - {cand_name}", p["cost_price"], p["sell_price"], now),
                        )
                        generated.append(inv_id)

        return {"generated": len(generated), "agency": agency_name, "invoice_ids": generated}


class GroupedInvoiceRequest(BaseModel):
    agency_id: str
    date_from: str
    date_to: str


@router.post("/invoices/generate-grouped")
async def generate_grouped_invoice(
    data: GroupedInvoiceRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a grouped/consolidated invoice for an agency within a date range.
    Groups all uninvoiced completed checks within the date range into itemised line items."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        # Get pricing
        db.execute("SELECT * FROM pricing_settings")
        pricing_rows = db.fetchall()
        pricing = {dict(r)["check_type"]: dict(r) for r in pricing_rows}

        db.execute("SELECT * FROM agencies WHERE id=%s", (data.agency_id,))
        agency_row = db.fetchone()
        if not agency_row:
            raise HTTPException(status_code=404, detail="Agency not found")
        agency = dict(agency_row)
        agency_name = agency["name"]
        discount = agency.get("discount_percent") or 0

        # Get agency candidates
        db.execute(
            """SELECT c.* FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               WHERE ac.agency_id=%s""",
            (data.agency_id,),
        )
        candidates = db.fetchall()

        generated = []
        line_items = []

        for cand in candidates:
            c = dict(cand)
            cand_name = f"{c['first_name']} {c['last_name']}"
            cand_email = c.get("email", "")

            # If candidate already has a full_vetting invoice from the invite
            # flow, skip per-check line items (but still generate re-vet invoices)
            db.execute(
                "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type='full_vetting'",
                (data.agency_id, c["id"]),
            )
            has_full_vetting = db.fetchone()

            # Per-check line items — only for candidates without a full_vetting charge
            if not has_full_vetting:
              # Check each type of check completed within the date range
              check_tables = [
                ("identity", "identity_checks", "completed_at"),
                ("dbs", "dbs_checks", "completed_at"),
                ("right_to_work", "right_to_work_checks", "checked_at"),
                ("cv_analysis", "cv_analyses", "analysed_at"),
                ("registration", "registration_checks", "last_checked"),
              ]
              for check_type, table, date_col in check_tables:
                db.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE candidate_id=%s AND status IN ('complete','completed','verified','clear') AND {date_col} >= %s AND {date_col} <= %s",
                    (c["id"], data.date_from, data.date_to),
                )
                completed = db.fetchone()
                if completed and dict(completed)["cnt"] > 0:
                    db.execute(
                        "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type=%s",
                        (data.agency_id, c["id"], check_type),
                    )
                    existing = db.fetchone()
                    if not existing and check_type in pricing:
                        p = pricing[check_type]
                        sell = p["sell_price"]
                        if discount > 0:
                            sell = round(sell * (1 - discount / 100), 2)
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, candidate_email, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                            (inv_id, data.agency_id, c["id"], cand_email, check_type,
                             f"{p['label']} - {cand_name}", p["cost_price"], sell, now),
                        )
                        generated.append(inv_id)
                        line_items.append({
                            "invoice_id": inv_id, "candidate": cand_name, "candidate_email": cand_email,
                            "check_type": check_type, "description": p["label"],
                            "cost": p["cost_price"], "sell": sell,
                        })

              # References
              db.execute(
                "SELECT COUNT(*) as cnt FROM references_ WHERE candidate_id=%s AND status='completed' AND completed_at >= %s AND completed_at <= %s",
                (c["id"], data.date_from, data.date_to),
              )
              refs = db.fetchone()
              ref_count = dict(refs)["cnt"] if refs else 0
              if ref_count > 0 and "references" in pricing:
                db.execute(
                    "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type='references'",
                    (data.agency_id, c["id"]),
                )
                existing = db.fetchone()
                if not existing:
                    p = pricing["references"]
                    sell = p["sell_price"] * ref_count
                    cost = p["cost_price"] * ref_count
                    if discount > 0:
                        sell = round(sell * (1 - discount / 100), 2)
                    inv_id = generate_id()
                    db.execute(
                        """INSERT INTO invoices (id, agency_id, candidate_id, candidate_email, check_type, description, cost_amount, sell_amount, status, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                        (inv_id, data.agency_id, c["id"], cand_email, "references",
                         f"References ({ref_count}x) - {cand_name}", cost, sell, now),
                    )
                    generated.append(inv_id)
                    line_items.append({
                        "invoice_id": inv_id, "candidate": cand_name, "candidate_email": cand_email,
                        "check_type": "references", "description": f"References ({ref_count}x)",
                        "cost": cost, "sell": sell,
                    })

            # Re-vet requests within date range — always generated regardless of full_vetting
            db.execute(
                "SELECT rr.* FROM revet_requests rr WHERE rr.agency_id=%s AND rr.candidate_id=%s AND rr.status IN ('completed', 'pending') AND rr.created_at >= %s AND rr.created_at <= %s",
                (data.agency_id, c["id"], data.date_from, data.date_to),
            )
            revet_rows = db.fetchall()
            for rr in revet_rows:
                rr_data = dict(rr)
                import json as _json
                sections = _json.loads(rr_data["sections"]) if rr_data["sections"] else []
                for sec in sections:
                    db.execute(
                        "SELECT id FROM invoices WHERE agency_id=%s AND candidate_id=%s AND check_type=%s AND description LIKE '%Re-vet%'",
                        (data.agency_id, c["id"], f"revet_{sec}"),
                    )
                    existing_revet = db.fetchone()
                    if not existing_revet and sec in pricing:
                        p = pricing[sec]
                        sell = p["sell_price"]
                        if discount > 0:
                            sell = round(sell * (1 - discount / 100), 2)
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, candidate_email, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                            (inv_id, data.agency_id, c["id"], cand_email, f"revet_{sec}",
                             f"Re-vet: {p['label']} - {cand_name}", p["cost_price"], sell, now),
                        )
                        generated.append(inv_id)
                        line_items.append({
                            "invoice_id": inv_id, "candidate": cand_name, "candidate_email": cand_email,
                            "check_type": f"revet_{sec}", "description": f"Re-vet: {p['label']}",
                            "cost": p["cost_price"], "sell": sell,
                        })

        total_cost = sum(li["cost"] for li in line_items)
        total_sell = sum(li["sell"] for li in line_items)

        return {
            "generated": len(generated),
            "agency": agency_name,
            "agency_id": data.agency_id,
            "date_from": data.date_from,
            "date_to": data.date_to,
            "discount_percent": discount,
            "invoice_ids": generated,
            "line_items": line_items,
            "total_cost": round(total_cost, 2),
            "total_sell": round(total_sell, 2),
        }


# ── One-Time Migration: Sync completed TrustID checks to legacy tables ──

@router.post("/migrate/trustid-to-legacy")
async def migrate_trustid_to_legacy(current_user: dict = Depends(get_current_user)):
    """One-time migration: for all completed TrustID checks with result='pass',
    insert corresponding records into legacy check tables (identity_checks,
    right_to_work_checks, dbs_checks) so the compliance engine recognises them.
    Then re-evaluate compliance for all affected candidates."""
    require_admin(current_user)
    import json as _json
    from app.services.trustid_checks import TrustIDService

    now = datetime.now(timezone.utc).isoformat()
    synced = []
    candidate_ids = set()

    with get_db() as db:
        db.execute(
            "SELECT * FROM trustid_checks WHERE status='completed' AND result='pass'"
        )
        completed = db.fetchall()

        for row in completed:
            check = dict(row)
            candidate_id = check["candidate_id"]
            check_type = check["check_type"]
            ref = check.get("trustid_reference")
            notes = check.get("admin_notes")

            # Check if a legacy record already exists for this candidate+check_type
            already_exists = False
            if check_type == "identity_verification":
                db.execute(
                    "SELECT id FROM identity_checks WHERE candidate_id=%s AND provider='trustid'",
                    (candidate_id,),
                )
                existing = db.fetchone()
                already_exists = existing is not None
            elif check_type == "right_to_work":
                db.execute(
                    "SELECT id FROM right_to_work_checks WHERE candidate_id=%s AND verification_method='trustid'",
                    (candidate_id,),
                )
                existing = db.fetchone()
                already_exists = existing is not None
            elif check_type == "dbs_check":
                db.execute(
                    "SELECT id FROM dbs_checks WHERE candidate_id=%s AND provider='trustid'",
                    (candidate_id,),
                )
                existing = db.fetchone()
                already_exists = existing is not None

            if already_exists:
                continue

            TrustIDService._sync_to_legacy_check_table(
                db, candidate_id, check_type, now, ref, notes,
            )
            synced.append({"candidate_id": candidate_id, "check_type": check_type, "trustid_check_id": check["id"]})
            candidate_ids.add(candidate_id)

    # Re-evaluate compliance for all affected candidates
    from app.services.compliance_engine import ComplianceEngine
    evaluated = []
    for cid in candidate_ids:
        try:
            ComplianceEngine.evaluate_candidate(cid)
            evaluated.append(cid)
        except Exception as e:
            logger.warning(f"Compliance re-evaluation failed for {cid}: {e}")

    return {
        "synced_count": len(synced),
        "synced": synced,
        "candidates_re_evaluated": evaluated,
    }


# ── Invoice Settings (company info, bank details) ─────────────────────

@router.get("/invoice-settings")
async def get_invoice_settings_endpoint(current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    from app.services.email_templates import get_invoice_settings
    return get_invoice_settings()


class InvoiceSettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    company_address: Optional[str] = None
    company_email: Optional[str] = None
    company_phone: Optional[str] = None
    company_reg_info: Optional[str] = None
    vat_number: Optional[str] = None
    vat_rate: Optional[str] = None
    bank_account_name: Optional[str] = None
    bank_sort_code: Optional[str] = None
    bank_account_number: Optional[str] = None
    bank_iban: Optional[str] = None
    payment_terms: Optional[str] = None


@router.put("/invoice-settings")
async def update_invoice_settings_endpoint(
    data: InvoiceSettingsUpdate, current_user: dict = Depends(get_current_user)
):
    require_admin(current_user)
    updates = {k: v for k, v in data.dict().items() if v is not None}
    with get_db() as db:
        for key, value in updates.items():
            db.execute(
                """INSERT INTO system_settings (setting_key, setting_value, updated_at)
                   VALUES (%s, %s, NOW()::text)
                   ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value,
                   updated_at=excluded.updated_at""",
                (f"invoice_{key}", value),
            )
        # commit handled by get_db() context manager
    from app.services.email_templates import get_invoice_settings
    return get_invoice_settings()


# ── Send Itemised Invoice Email ───────────────────────────────────────

class SendInvoiceRequest(BaseModel):
    invoice_ids: List[str]


@router.post("/invoices/send-email")
async def send_invoice_email(
    data: SendInvoiceRequest, current_user: dict = Depends(get_current_user)
):
    """Send an itemised invoice email to the agency for the given invoice IDs."""
    require_admin(current_user)
    from app.services.email_templates import get_invoice_settings, EmailTemplateService

    if not data.invoice_ids:
        raise HTTPException(status_code=400, detail="No invoice IDs provided")

    with get_db() as db:
        # Fetch invoices
        placeholders = ",".join("%s" for _ in data.invoice_ids)
        db.execute(
            f"SELECT * FROM invoices WHERE id IN ({placeholders})",
            data.invoice_ids,
        )
        invoices = db.fetchall()
        invoices = [dict(r) for r in invoices]

        if not invoices:
            raise HTTPException(status_code=404, detail="No invoices found")

        # All invoices must belong to the same agency
        agency_ids = set(inv["agency_id"] for inv in invoices)
        if len(agency_ids) > 1:
            raise HTTPException(status_code=400, detail="All invoices must belong to the same agency")

        agency_id = agency_ids.pop()
        db.execute("SELECT * FROM agencies WHERE id=%s", (agency_id,))
        agency = db.fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")
        agency = dict(agency)

        # Build line items
        line_items_html = ""
        line_items_text = ""
        subtotal = 0.0
        for inv in invoices:
            sell = inv.get("sell_amount") or inv.get("cost_amount") or 0.0
            subtotal += sell
            desc = inv.get("description") or inv.get("check_type") or "Vetting Service"
            # Get candidate name if available
            candidate_name = ""
            if inv.get("candidate_id"):
                db.execute(
                    "SELECT first_name, last_name FROM candidates WHERE id=%s", (inv["candidate_id"],)
                )
                cand = db.fetchone()
                if cand:
                    cand_d = dict(cand)
                    candidate_name = f"{cand_d.get('first_name', '')} {cand_d.get('last_name', '')}".strip()

            line_items_html += (
                f'<tr>'
                f'<td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 13px;">{desc}</td>'
                f'<td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 13px;">{candidate_name}</td>'
                f'<td style="padding: 10px; border-bottom: 1px solid #e2e8f0; font-size: 13px; text-align: right;">\u00a3{sell:.2f}</td>'
                f'</tr>'
            )
            line_items_text += f"  {desc:<40} {candidate_name:<20} \u00a3{sell:.2f}\n"

    # Get invoice settings
    settings = get_invoice_settings()
    vat_rate_pct = float(settings.get("vat_rate") or "0")
    vat_amount = subtotal * (vat_rate_pct / 100)
    total_due = subtotal + vat_amount

    # Build a grouped invoice reference from the first invoice ID
    invoice_ref = invoices[0]["id"][:8].upper()
    now = datetime.now(timezone.utc)
    invoice_date = now.strftime("%d %B %Y")

    # Calculate due date from payment terms
    terms = settings.get("payment_terms", "Net 30")
    try:
        days = int("".join(c for c in terms if c.isdigit()) or "30")
    except ValueError:
        days = 30
    due_date = (now + timedelta(days=days)).strftime("%d %B %Y")

    agency_email = agency.get("email") or agency.get("contact_email") or ""
    if not agency_email:
        raise HTTPException(status_code=400, detail="Agency has no email address configured")

    variables = {
        "invoice_ref": invoice_ref,
        "invoice_date": invoice_date,
        "due_date": due_date,
        "payment_terms": terms,
        "agency_name": agency.get("name") or agency.get("company_name") or "Agency",
        "agency_email": agency_email,
        "line_items_html": line_items_html,
        "line_items_text": line_items_text,
        "subtotal": f"\u00a3{subtotal:.2f}",
        "vat_rate": f"{vat_rate_pct:.0f}%",
        "vat_amount": f"\u00a3{vat_amount:.2f}",
        "total_due": f"\u00a3{total_due:.2f}",
        "company_name": settings.get("company_name", ""),
        "company_address": settings.get("company_address", ""),
        "company_email": settings.get("company_email", ""),
        "company_phone": settings.get("company_phone", ""),
        "company_reg_info": settings.get("company_reg_info", ""),
        "vat_number": settings.get("vat_number", ""),
        "bank_account_name": settings.get("bank_account_name", ""),
        "bank_sort_code": settings.get("bank_sort_code", ""),
        "bank_account_number": settings.get("bank_account_number", ""),
    }

    fallback_subject = f"Invoice #{invoice_ref} - \u00a3{total_due:.2f}"
    fallback_body = f"Dear {variables['agency_name']},\n\nPlease find attached invoice #{invoice_ref} for \u00a3{total_due:.2f}.\n\nBest regards,\n{settings.get('company_name', 'Viper AI')}"

    # Generate PDF invoice
    pdf_attachments = []
    try:
        pdf_bytes = _generate_invoice_pdf(
            invoice_ref=invoice_ref,
            invoice_date=invoice_date,
            due_date=due_date,
            agency_name=variables["agency_name"],
            agency_email=agency_email,
            invoices=invoices,
            subtotal=subtotal,
            vat_rate_pct=vat_rate_pct,
            vat_amount=vat_amount,
            total_due=total_due,
            settings=settings,
            terms=terms,
        )
        pdf_attachments = [{
            "content": base64.b64encode(pdf_bytes).decode("utf-8"),
            "filename": f"Invoice-{invoice_ref}.pdf",
            "type": "application/pdf",
        }]
    except Exception as e:
        logger.warning(f"PDF generation failed, sending email without attachment: {e}")

    try:
        EmailTemplateService.send_email(
            template_key="invoice_notification",
            recipient_email=agency_email,
            recipient_name=variables["agency_name"],
            variables=variables,
            attachments=pdf_attachments if pdf_attachments else None,
        )
    except Exception as e:
        logger.error(f"Failed to send invoice email: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    return {
        "success": True,
        "message": f"Invoice email sent to {agency_email}" + (" with PDF attached" if pdf_attachments else ""),
        "invoice_ref": invoice_ref,
        "total_due": f"\u00a3{total_due:.2f}",
        "line_items_count": len(invoices),
        "pdf_attached": bool(pdf_attachments),
    }


def _generate_invoice_pdf(
    invoice_ref: str, invoice_date: str, due_date: str,
    agency_name: str, agency_email: str,
    invoices: list, subtotal: float, vat_rate_pct: float,
    vat_amount: float, total_due: float, settings: dict, terms: str,
) -> bytes:
    """Generate an itemised PDF invoice using reportlab."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=20*mm, rightMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("InvTitle", parent=styles["Heading1"],
                                  fontSize=22, textColor=colors.HexColor("#1e293b"))
    company_style = ParagraphStyle("Company", parent=styles["Normal"],
                                    fontSize=10, textColor=colors.HexColor("#64748b"))
    label_style = ParagraphStyle("Label", parent=styles["Normal"],
                                  fontSize=9, textColor=colors.HexColor("#64748b"))
    value_style = ParagraphStyle("Value", parent=styles["Normal"],
                                  fontSize=10, textColor=colors.HexColor("#1e293b"))

    elements = []

    # Header
    company_name = settings.get("company_name", "Viper AI")
    elements.append(Paragraph(f"<b>{company_name}</b>", title_style))
    addr = settings.get("company_address", "")
    if addr:
        elements.append(Paragraph(addr.replace("\n", "<br/>"), company_style))
    comp_email = settings.get("company_email", "")
    comp_phone = settings.get("company_phone", "")
    if comp_email or comp_phone:
        elements.append(Paragraph(f"{comp_email}  {comp_phone}", company_style))
    reg = settings.get("company_reg_info", "")
    vat_num = settings.get("vat_number", "")
    if reg:
        elements.append(Paragraph(reg, company_style))
    if vat_num:
        elements.append(Paragraph(f"VAT: {vat_num}", company_style))
    elements.append(Spacer(1, 8*mm))

    # Invoice details
    elements.append(Paragraph("<b>INVOICE</b>", ParagraphStyle(
        "InvLabel", parent=styles["Heading2"], fontSize=16,
        textColor=colors.HexColor("#0f172a"))))
    elements.append(Spacer(1, 3*mm))

    info_data = [
        [Paragraph("<b>Invoice #:</b>", label_style), Paragraph(invoice_ref, value_style),
         Paragraph("<b>Bill To:</b>", label_style), Paragraph(agency_name, value_style)],
        [Paragraph("<b>Date:</b>", label_style), Paragraph(invoice_date, value_style),
         Paragraph("<b>Email:</b>", label_style), Paragraph(agency_email, value_style)],
        [Paragraph("<b>Due Date:</b>", label_style), Paragraph(due_date, value_style),
         Paragraph("<b>Terms:</b>", label_style), Paragraph(terms, value_style)],
    ]
    info_table = Table(info_data, colWidths=[65, 120, 55, 200])
    info_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 8*mm))

    # Line items table
    header_row = ["Description", "Candidate", "Amount"]
    table_data = [header_row]
    for inv in invoices:
        sell = inv.get("sell_amount") or inv.get("cost_amount") or 0.0
        desc = inv.get("description") or inv.get("check_type") or "Vetting Service"
        cand = inv.get("candidate_name", "")
        table_data.append([desc, cand, f"\u00a3{sell:.2f}"])

    # Totals
    table_data.append(["", "Subtotal:", f"\u00a3{subtotal:.2f}"])
    if vat_rate_pct > 0:
        table_data.append(["", f"VAT ({vat_rate_pct:.0f}%):", f"\u00a3{vat_amount:.2f}"])
    table_data.append(["", "TOTAL DUE:", f"\u00a3{total_due:.2f}"])

    col_widths = [220, 160, 80]
    t = Table(table_data, colWidths=col_widths)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("GRID", (0, 0), (-1, len(invoices)), 0.5, colors.HexColor("#e2e8f0")),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 6),
        ("TOPPADDING", (0, 1), (-1, -1), 6),
    ]
    # Bold totals
    total_start = len(invoices) + 1
    style_cmds.append(("FONTNAME", (1, total_start), (-1, -1), "Helvetica-Bold"))
    style_cmds.append(("LINEABOVE", (1, total_start), (-1, total_start), 1, colors.HexColor("#1e293b")))
    t.setStyle(TableStyle(style_cmds))
    elements.append(t)
    elements.append(Spacer(1, 10*mm))

    # Bank details
    bank_name = settings.get("bank_account_name", "")
    bank_sort = settings.get("bank_sort_code", "")
    bank_acct = settings.get("bank_account_number", "")
    if bank_name or bank_sort or bank_acct:
        elements.append(Paragraph("<b>Payment Details</b>", value_style))
        elements.append(Spacer(1, 2*mm))
        if bank_name:
            elements.append(Paragraph(f"Account Name: {bank_name}", company_style))
        if bank_sort:
            elements.append(Paragraph(f"Sort Code: {bank_sort}", company_style))
        if bank_acct:
            elements.append(Paragraph(f"Account Number: {bank_acct}", company_style))

    doc.build(elements)
    return buf.getvalue()
