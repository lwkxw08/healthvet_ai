"""Admin settings, analytics, and pricing routes."""
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
        rows = db.execute("SELECT * FROM pricing_settings ORDER BY check_type").fetchall()
        return [dict(r) for r in rows]


@router.put("/pricing/{check_type}")
async def update_pricing(check_type: str, data: PricingUpdate, current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        row = db.execute("SELECT * FROM pricing_settings WHERE check_type=?", (check_type,)).fetchone()
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
            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            values = list(updates.values()) + [check_type]
            db.execute(f"UPDATE pricing_settings SET {set_clause} WHERE check_type=?", values)
        row = db.execute("SELECT * FROM pricing_settings WHERE check_type=?", (check_type,)).fetchone()
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
        default_row = db.execute("SELECT * FROM pricing_settings WHERE check_type=?", (check_type,)).fetchone()
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
        result = db.execute(
            f"""UPDATE industry_check_pricing
                SET third_party_cost=?, sell_price=?, updated_at=?
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
        pricing_rows = db.execute("SELECT * FROM pricing_settings").fetchall()
        pricing = {dict(r)["check_type"]: dict(r) for r in pricing_rows}

        # Get invoices in range
        query = "SELECT * FROM invoices WHERE created_at >= ? AND created_at <= ?"
        params = [start, end]
        if agency_id:
            query += " AND agency_id = ?"
            params.append(agency_id)
        invoice_rows = db.execute(query, params).fetchall()
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
                agency_row = db.execute("SELECT name FROM agencies WHERE id=?", (aid,)).fetchone()
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
        cand_query = "SELECT * FROM candidates WHERE created_at >= ? AND created_at <= ?"
        cand_params = [start, end]
        candidates = [dict(r) for r in db.execute(cand_query, cand_params).fetchall()]

        if agency_id:
            linked = db.execute(
                "SELECT candidate_id FROM agency_candidates WHERE agency_id=?", (agency_id,)
            ).fetchall()
            linked_ids = {dict(r)["candidate_id"] for r in linked}
            candidates = [c for c in candidates if c["id"] in linked_ids]

        total = len(candidates)
        compliant = sum(1 for c in candidates if c["compliance_status"] == "compliant")
        flagged = sum(1 for c in candidates if c["compliance_status"] in ("incomplete", "flagged"))
        pending = total - compliant - flagged

        # Check completion stats
        id_checks = db.execute(
            "SELECT COUNT(*) as cnt FROM identity_checks WHERE completed_at >= ? AND completed_at <= ?",
            (start, end),
        ).fetchone()
        dbs_checks = db.execute(
            "SELECT COUNT(*) as cnt FROM dbs_checks WHERE completed_at >= ? AND completed_at <= ?",
            (start, end),
        ).fetchone()
        rtw_checks = db.execute(
            "SELECT COUNT(*) as cnt FROM right_to_work_checks WHERE checked_at >= ? AND checked_at <= ?",
            (start, end),
        ).fetchone()
        ref_checks = db.execute(
            "SELECT COUNT(*) as cnt FROM references_ WHERE completed_at >= ? AND completed_at <= ?",
            (start, end),
        ).fetchone()
        emp_checks = db.execute(
            "SELECT COUNT(*) as cnt FROM employment_verifications WHERE completed_at >= ? AND completed_at <= ?",
            (start, end),
        ).fetchone()

        # Average time to complete (simulated from candidate creation to compliance)
        comp_records = db.execute(
            """SELECT cr.last_evaluated, c.created_at
               FROM compliance_records cr
               JOIN candidates c ON cr.candidate_id = c.id
               WHERE cr.overall_status = 'compliant'
               AND cr.last_evaluated >= ? AND cr.last_evaluated <= ?""",
            (start, end),
        ).fetchall()
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
        agencies = [dict(r) for r in db.execute("SELECT * FROM agencies").fetchall()]
        result = []
        for agency in agencies:
            # Get candidates for this agency
            linked = db.execute(
                "SELECT candidate_id FROM agency_candidates WHERE agency_id=?",
                (agency["id"],),
            ).fetchall()
            candidate_ids = [dict(r)["candidate_id"] for r in linked]

            total_candidates = len(candidate_ids)
            compliant = 0
            if candidate_ids:
                placeholders = ",".join("?" for _ in candidate_ids)
                compliant_row = db.execute(
                    f"SELECT COUNT(*) as cnt FROM candidates WHERE id IN ({placeholders}) AND compliance_status='compliant'",
                    candidate_ids,
                ).fetchone()
                compliant = dict(compliant_row)["cnt"] if compliant_row else 0

            # Revenue from invoices
            inv_row = db.execute(
                "SELECT COALESCE(SUM(COALESCE(adjusted_amount, sell_amount)),0) as rev, COALESCE(SUM(cost_amount),0) as cost, COUNT(*) as cnt FROM invoices WHERE agency_id=? AND created_at >= ? AND created_at <= ?",
                (agency["id"], start, end),
            ).fetchone()
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
        query = "SELECT i.*, a.name as agency_name FROM invoices i LEFT JOIN agencies a ON i.agency_id = a.id WHERE i.created_at >= ? AND i.created_at <= ?"
        params = [start, end]
        if agency_id:
            query += " AND i.agency_id = ?"
            params.append(agency_id)
        if status:
            query += " AND i.status = ?"
            params.append(status)
        query += " ORDER BY i.created_at DESC"
        rows = db.execute(query, params).fetchall()
        return [dict(r) for r in rows]


@router.post("/invoices")
async def create_invoice(data: InvoiceCreate, current_user: dict = Depends(get_current_user)):
    require_admin(current_user)
    invoice_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
            (invoice_id, data.agency_id, data.candidate_id, data.check_type, data.description, data.cost_amount, data.sell_amount, now),
        )
        row = db.execute("SELECT i.*, a.name as agency_name, a.email as agency_email FROM invoices i LEFT JOIN agencies a ON i.agency_id = a.id WHERE i.id=?", (invoice_id,)).fetchone()
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
                   VALUES (?, ?, 'agency', 'billing', ?, ?, 0, ?)""",
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
        db.execute("UPDATE invoices SET status='paid', paid_at=? WHERE id=?", (now, invoice_id))
        row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
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
        pricing_rows = db.execute("SELECT * FROM pricing_settings").fetchall()
        pricing = {dict(r)["check_type"]: dict(r) for r in pricing_rows}

        # Get agency candidates
        candidates = db.execute(
            """SELECT c.* FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               WHERE ac.agency_id=?""",
            (agency_id,),
        ).fetchall()

        agency_row = db.execute("SELECT name FROM agencies WHERE id=?", (agency_id,)).fetchone()
        agency_name = dict(agency_row)["name"] if agency_row else "Unknown"

        generated = []
        for cand in candidates:
            c = dict(cand)
            cand_name = f"{c['first_name']} {c['last_name']}"

            # Check each type of check completed
            check_tables = [
                ("identity", "identity_checks", "completed_at"),
                ("dbs", "dbs_checks", "completed_at"),
                ("right_to_work", "right_to_work_checks", "checked_at"),
                ("cv_analysis", "cv_analyses", "analysed_at"),
                ("registration", "registration_checks", "last_checked"),
            ]
            for check_type, table, date_col in check_tables:
                completed = db.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE candidate_id=? AND status IN ('complete','completed','verified','clear')",
                    (c["id"],),
                ).fetchone()
                if completed and dict(completed)["cnt"] > 0:
                    # Check if invoice already exists
                    existing = db.execute(
                        "SELECT id FROM invoices WHERE agency_id=? AND candidate_id=? AND check_type=?",
                        (agency_id, c["id"], check_type),
                    ).fetchone()
                    if not existing and check_type in pricing:
                        p = pricing[check_type]
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                            (inv_id, agency_id, c["id"], check_type,
                             f"{p['label']} - {cand_name}", p["cost_price"], p["sell_price"], now),
                        )
                        generated.append(inv_id)

            # References (per reference)
            refs = db.execute(
                "SELECT COUNT(*) as cnt FROM references_ WHERE candidate_id=? AND status='completed'",
                (c["id"],),
            ).fetchone()
            ref_count = dict(refs)["cnt"] if refs else 0
            if ref_count > 0 and "references" in pricing:
                existing = db.execute(
                    "SELECT id FROM invoices WHERE agency_id=? AND candidate_id=? AND check_type='references'",
                    (agency_id, c["id"]),
                ).fetchone()
                if not existing:
                    p = pricing["references"]
                    inv_id = generate_id()
                    db.execute(
                        """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                        (inv_id, agency_id, c["id"], "references",
                         f"References ({ref_count}x) - {cand_name}", p["cost_price"] * ref_count, p["sell_price"] * ref_count, now),
                    )
                    generated.append(inv_id)

        # Re-vet requests (itemised per section)
            revet_rows = db.execute(
                "SELECT rr.* FROM revet_requests rr WHERE rr.agency_id=? AND rr.candidate_id=? AND rr.status IN ('completed', 'pending')",
                (agency_id, c["id"]),
            ).fetchall()
            for rr in revet_rows:
                rr_data = dict(rr)
                import json as _json
                sections = _json.loads(rr_data["sections"]) if rr_data["sections"] else []
                for sec in sections:
                    existing_revet = db.execute(
                        "SELECT id FROM invoices WHERE agency_id=? AND candidate_id=? AND check_type=? AND description LIKE '%Re-vet%'",
                        (agency_id, c["id"], f"revet_{sec}"),
                    ).fetchone()
                    if not existing_revet and sec in pricing:
                        p = pricing[sec]
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
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
        pricing_rows = db.execute("SELECT * FROM pricing_settings").fetchall()
        pricing = {dict(r)["check_type"]: dict(r) for r in pricing_rows}

        agency_row = db.execute("SELECT * FROM agencies WHERE id=?", (data.agency_id,)).fetchone()
        if not agency_row:
            raise HTTPException(status_code=404, detail="Agency not found")
        agency = dict(agency_row)
        agency_name = agency["name"]
        discount = agency.get("discount_percent") or 0

        # Get agency candidates
        candidates = db.execute(
            """SELECT c.* FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               WHERE ac.agency_id=?""",
            (data.agency_id,),
        ).fetchall()

        generated = []
        line_items = []

        for cand in candidates:
            c = dict(cand)
            cand_name = f"{c['first_name']} {c['last_name']}"
            cand_email = c.get("email", "")

            # Check each type of check completed within the date range
            check_tables = [
                ("identity", "identity_checks", "completed_at"),
                ("dbs", "dbs_checks", "completed_at"),
                ("right_to_work", "right_to_work_checks", "checked_at"),
                ("cv_analysis", "cv_analyses", "analysed_at"),
                ("registration", "registration_checks", "last_checked"),
            ]
            for check_type, table, date_col in check_tables:
                completed = db.execute(
                    f"SELECT COUNT(*) as cnt FROM {table} WHERE candidate_id=? AND status IN ('complete','completed','verified','clear') AND {date_col} >= ? AND {date_col} <= ?",
                    (c["id"], data.date_from, data.date_to),
                ).fetchone()
                if completed and dict(completed)["cnt"] > 0:
                    existing = db.execute(
                        "SELECT id FROM invoices WHERE agency_id=? AND candidate_id=? AND check_type=?",
                        (data.agency_id, c["id"], check_type),
                    ).fetchone()
                    if not existing and check_type in pricing:
                        p = pricing[check_type]
                        sell = p["sell_price"]
                        if discount > 0:
                            sell = round(sell * (1 - discount / 100), 2)
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, candidate_email, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
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
            refs = db.execute(
                "SELECT COUNT(*) as cnt FROM references_ WHERE candidate_id=? AND status='completed' AND completed_at >= ? AND completed_at <= ?",
                (c["id"], data.date_from, data.date_to),
            ).fetchone()
            ref_count = dict(refs)["cnt"] if refs else 0
            if ref_count > 0 and "references" in pricing:
                existing = db.execute(
                    "SELECT id FROM invoices WHERE agency_id=? AND candidate_id=? AND check_type='references'",
                    (data.agency_id, c["id"]),
                ).fetchone()
                if not existing:
                    p = pricing["references"]
                    sell = p["sell_price"] * ref_count
                    cost = p["cost_price"] * ref_count
                    if discount > 0:
                        sell = round(sell * (1 - discount / 100), 2)
                    inv_id = generate_id()
                    db.execute(
                        """INSERT INTO invoices (id, agency_id, candidate_id, candidate_email, check_type, description, cost_amount, sell_amount, status, created_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                        (inv_id, data.agency_id, c["id"], cand_email, "references",
                         f"References ({ref_count}x) - {cand_name}", cost, sell, now),
                    )
                    generated.append(inv_id)
                    line_items.append({
                        "invoice_id": inv_id, "candidate": cand_name, "candidate_email": cand_email,
                        "check_type": "references", "description": f"References ({ref_count}x)",
                        "cost": cost, "sell": sell,
                    })

            # Re-vet requests within date range
            revet_rows = db.execute(
                "SELECT rr.* FROM revet_requests rr WHERE rr.agency_id=? AND rr.candidate_id=? AND rr.status IN ('completed', 'pending') AND rr.created_at >= ? AND rr.created_at <= ?",
                (data.agency_id, c["id"], data.date_from, data.date_to),
            ).fetchall()
            for rr in revet_rows:
                rr_data = dict(rr)
                import json as _json
                sections = _json.loads(rr_data["sections"]) if rr_data["sections"] else []
                for sec in sections:
                    existing_revet = db.execute(
                        "SELECT id FROM invoices WHERE agency_id=? AND candidate_id=? AND check_type=? AND description LIKE '%Re-vet%'",
                        (data.agency_id, c["id"], f"revet_{sec}"),
                    ).fetchone()
                    if not existing_revet and sec in pricing:
                        p = pricing[sec]
                        sell = p["sell_price"]
                        if discount > 0:
                            sell = round(sell * (1 - discount / 100), 2)
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, candidate_email, check_type, description, cost_amount, sell_amount, status, created_at)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
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
