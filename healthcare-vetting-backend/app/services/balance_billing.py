"""
£ Balance Billing Service
Agencies prepay funds onto their account and are charged per-check at discounted rates.
Discount percentage is determined by the credit pack tier they purchased.
Admin reports show ACTUAL revenue (amount paid in) vs amount consumed.
"""
import json
from datetime import datetime, timezone
from typing import Optional
from app.database import get_db
from app.utils.auth import generate_id

import logging
logger = logging.getLogger(__name__)


# Default check prices (gross, before any discount)
DEFAULT_CHECK_PRICES = {
    "full_vetting": 95.00,
    "phase1_refs_only": 28.00,
    "phase2_vetting": 67.00,
    "dbs_check": 52.00,
    "identity_verification": 18.00,
    "right_to_work": 8.00,
    "cv_analysis": 6.00,
    "registration_check": 5.00,
    "training_certificate": 4.00,
    "reference_rechase": 4.00,
    "monitoring_renewal": 12.00,
}


class BalanceBillingService:
    """£ balance billing — agencies prepay, get tier-based discounts on usage."""

    # ── Check Price Management ──────────────────────────────────────

    @staticmethod
    def get_check_prices() -> list:
        """Get all check prices from partial_credit_rates (repurposed as price table)."""
        with get_db() as db:
            db.execute("SELECT * FROM partial_credit_rates ORDER BY check_type")
            rows = db.fetchall()
            if rows:
                return [dict(r) for r in rows]
        return [{"check_type": k, "label": k.replace("_", " ").title(), "gross_price": v}
                for k, v in DEFAULT_CHECK_PRICES.items()]

    @staticmethod
    def get_check_price(check_type: str) -> float:
        """Get the gross price for a specific check type."""
        with get_db() as db:
            db.execute(
                "SELECT third_party_cost, credit_value FROM partial_credit_rates WHERE check_type=%s",
                (check_type,),
            )
            row = db.fetchone()
            if row:
                r = dict(row)
                # Use third_party_cost as gross price in the new model
                return float(r.get("third_party_cost") or DEFAULT_CHECK_PRICES.get(check_type, 95.00))
        return DEFAULT_CHECK_PRICES.get(check_type, 95.00)

    # ── Agency Balance ──────────────────────────────────────────────

    @staticmethod
    def get_agency_balance(agency_id: str) -> dict:
        """Get the current balance and billing summary for an agency."""
        with get_db() as db:
            db.execute(
                "SELECT id, name, balance_amount, total_topup_amount, total_spent_amount, discount_percent FROM agencies WHERE id=%s",
                (agency_id,),
            )
            row = db.fetchone()
            if not row:
                return {"error": "Agency not found"}
            r = dict(row)

            # Get active subscription tier for discount info
            db.execute(
                """SELECT s.tier, stc.name as tier_name, stc.discount_percent as tier_discount
                   FROM agency_subscriptions s
                   JOIN subscription_tier_config stc ON stc.tier_key = s.tier
                   WHERE s.agency_id=%s AND s.status='active'
                   ORDER BY s.created_at DESC LIMIT 1""",
                (agency_id,),
            )
            tier_row = db.fetchone()
            tier_info = dict(tier_row) if tier_row else {}

            return {
                "agency_id": agency_id,
                "agency_name": r.get("name"),
                "balance": round(float(r.get("balance_amount") or 0), 2),
                "total_topped_up": round(float(r.get("total_topup_amount") or 0), 2),
                "total_spent": round(float(r.get("total_spent_amount") or 0), 2),
                "discount_percent": float(tier_info.get("tier_discount") or r.get("discount_percent") or 0),
                "active_tier": tier_info.get("tier"),
                "active_tier_name": tier_info.get("tier_name"),
            }

    # ── Top-Up ──────────────────────────────────────────────────────

    @staticmethod
    def topup_balance(agency_id: str, amount: float, tier_key: str = None,
                      payment_method: str = "stripe") -> dict:
        """Top up an agency's balance. The amount is ACTUAL money paid.
        The tier determines the discount on future usage, NOT bonus balance."""
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Validate tier if provided
            discount_percent = 0.0
            tier_name = None
            if tier_key:
                db.execute(
                    "SELECT * FROM subscription_tier_config WHERE tier_key=%s AND is_active=1",
                    (tier_key,),
                )
                tier_row = db.fetchone()
                if not tier_row:
                    raise ValueError(f"Invalid or inactive pack tier: {tier_key}")
                tier_info = dict(tier_row)
                discount_percent = float(tier_info.get("discount_percent") or 0)
                tier_name = tier_info.get("name")

            # Update agency balance — add the ACTUAL amount paid
            db.execute(
                """UPDATE agencies SET
                   balance_amount = balance_amount + %s,
                   total_topup_amount = total_topup_amount + %s,
                   discount_percent = %s
                   WHERE id=%s""",
                (amount, amount, discount_percent, agency_id),
            )

            # Get updated balance
            db.execute("SELECT balance_amount FROM agencies WHERE id=%s", (agency_id,))
            balance_row = db.fetchone()
            new_balance = float(dict(balance_row)["balance_amount"]) if balance_row else amount

            # Record balance transaction
            txn_id = generate_id()
            db.execute(
                """INSERT INTO balance_transactions
                   (id, agency_id, transaction_type, description, gross_amount, discount_percent,
                    discount_amount, net_amount, balance_after, topup_pack_tier, created_at)
                   VALUES (%s, %s, 'topup', %s, %s, %s, 0, %s, %s, %s, %s)""",
                (txn_id, agency_id,
                 f"Balance top-up{' (' + tier_name + ')' if tier_name else ''}",
                 amount, discount_percent, amount, round(new_balance, 2),
                 tier_key, now),
            )

            # Create/update subscription record for tier tracking
            if tier_key:
                sub_id = generate_id()
                # Deactivate any previous subscription
                db.execute(
                    "UPDATE agency_subscriptions SET status='replaced' WHERE agency_id=%s AND status='active'",
                    (agency_id,),
                )
                db.execute(
                    """INSERT INTO agency_subscriptions
                       (id, agency_id, tier, billing_method, monthly_amount, per_worker_amount,
                        max_workers, monthly_checks, checks_used, credits_total, credits_used,
                        status, pack_name, created_at)
                       VALUES (%s, %s, %s, %s, %s, 0, 99999, 0, 0, %s, 0, 'active', %s, %s)""",
                    (sub_id, agency_id, tier_key, payment_method,
                     amount, amount, tier_name, now),
                )

            # Create invoice for the top-up
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, paid_at, created_at)
                   VALUES (%s, %s, 'balance_topup', %s, 0, %s, 'paid', %s, %s)""",
                (inv_id, agency_id,
                 f"Balance Top-Up - £{amount:.2f}{' (' + tier_name + ' - ' + str(discount_percent) + '% discount tier)' if tier_name else ''}",
                 amount, now, now),
            )

        return {
            "agency_id": agency_id,
            "topped_up": round(amount, 2),
            "new_balance": round(new_balance, 2),
            "discount_percent": discount_percent,
            "tier": tier_key,
            "tier_name": tier_name,
            "transaction_id": txn_id,
            "invoice_id": inv_id,
        }

    # ── Charge (Deduct Balance) ─────────────────────────────────────

    @staticmethod
    def charge_check(agency_id: str, candidate_id: str, check_type: str,
                     description: str = None, submission_id: str = None) -> dict:
        """Charge an agency for a check. Applies their tier discount to the gross price.
        Records ACTUAL spend (net after discount) for financial reporting."""
        now = datetime.now(timezone.utc).isoformat()

        gross_price = BalanceBillingService.get_check_price(check_type)

        with get_db() as db:
            # Get agency discount
            db.execute(
                "SELECT balance_amount, discount_percent FROM agencies WHERE id=%s",
                (agency_id,),
            )
            row = db.fetchone()
            if not row:
                raise ValueError("Agency not found")
            agency_data = dict(row)
            current_balance = float(agency_data.get("balance_amount") or 0)
            discount_pct = float(agency_data.get("discount_percent") or 0)

            # Calculate discounted price
            discount_amount = round(gross_price * (discount_pct / 100), 2)
            net_amount = round(gross_price - discount_amount, 2)

            # Check sufficient balance
            if current_balance < net_amount:
                # Insufficient balance — create pending invoice instead
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description,
                       cost_amount, sell_amount, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'pending', %s)""",
                    (inv_id, agency_id, candidate_id, check_type,
                     description or f"{check_type} (insufficient balance)",
                     0, net_amount, now),
                )
                return {
                    "status": "insufficient_balance",
                    "invoice_id": inv_id,
                    "balance": round(current_balance, 2),
                    "required": net_amount,
                    "message": f"Insufficient balance (£{current_balance:.2f}). £{net_amount:.2f} required. Please top up.",
                }

            # Deduct from balance
            new_balance = round(current_balance - net_amount, 2)
            db.execute(
                """UPDATE agencies SET
                   balance_amount = %s,
                   total_spent_amount = total_spent_amount + %s
                   WHERE id=%s""",
                (new_balance, net_amount, agency_id),
            )

            # Record balance transaction
            txn_id = generate_id()
            db.execute(
                """INSERT INTO balance_transactions
                   (id, agency_id, candidate_id, transaction_type, description,
                    gross_amount, discount_percent, discount_amount, net_amount,
                    balance_after, check_type, submission_id, created_at)
                   VALUES (%s, %s, %s, 'charge', %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (txn_id, agency_id, candidate_id, 'charge',
                 description or check_type.replace("_", " ").title(),
                 gross_price, discount_pct, discount_amount, net_amount,
                 new_balance, check_type, submission_id, now),
            )

            # Record in invoices as paid (for existing billing reporting)
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description,
                   cost_amount, sell_amount, status, paid_at, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, 'paid', %s, %s)""",
                (inv_id, agency_id, candidate_id, check_type,
                 description or check_type.replace("_", " ").title(),
                 0, net_amount, now, now),
            )

        return {
            "status": "charged",
            "transaction_id": txn_id,
            "invoice_id": inv_id,
            "check_type": check_type,
            "gross_price": gross_price,
            "discount_percent": discount_pct,
            "discount_amount": discount_amount,
            "net_charged": net_amount,
            "balance_remaining": new_balance,
            "message": f"Charged £{net_amount:.2f} (£{gross_price:.2f} less {discount_pct}% discount). Balance: £{new_balance:.2f}",
        }

    # ── Transaction History ─────────────────────────────────────────

    @staticmethod
    def get_transactions(agency_id: str, limit: int = 50,
                         transaction_type: str = None) -> list:
        """Get balance transaction history for an agency."""
        with get_db() as db:
            if transaction_type:
                db.execute(
                    """SELECT * FROM balance_transactions
                       WHERE agency_id=%s AND transaction_type=%s
                       ORDER BY created_at DESC LIMIT %s""",
                    (agency_id, transaction_type, limit),
                )
            else:
                db.execute(
                    """SELECT * FROM balance_transactions
                       WHERE agency_id=%s ORDER BY created_at DESC LIMIT %s""",
                    (agency_id, limit),
                )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    # ── Admin Financial Reporting ───────────────────────────────────

    @staticmethod
    def get_revenue_report(start_date: str = None, end_date: str = None) -> dict:
        """Admin report: actual revenue received vs balance consumed.
        Shows REAL money in (top-ups) vs REAL money charged (net after discounts)."""
        with get_db() as db:
            date_filter = ""
            params = []
            if start_date:
                date_filter += " AND created_at >= %s"
                params.append(start_date)
            if end_date:
                date_filter += " AND created_at <= %s"
                params.append(end_date)

            # Total revenue (top-ups received)
            db.execute(
                f"SELECT COALESCE(SUM(net_amount), 0) as total FROM balance_transactions WHERE transaction_type='topup'{date_filter}",
                params,
            )
            total_revenue = float(db.fetchone()["total"])

            # Total consumed (charges)
            db.execute(
                f"SELECT COALESCE(SUM(net_amount), 0) as total FROM balance_transactions WHERE transaction_type='charge'{date_filter}",
                params,
            )
            total_consumed = float(db.fetchone()["total"])

            # Total discount given
            db.execute(
                f"SELECT COALESCE(SUM(discount_amount), 0) as total FROM balance_transactions WHERE transaction_type='charge'{date_filter}",
                params,
            )
            total_discount = float(db.fetchone()["total"])

            # Gross value of checks performed (before discount)
            db.execute(
                f"SELECT COALESCE(SUM(gross_amount), 0) as total FROM balance_transactions WHERE transaction_type='charge'{date_filter}",
                params,
            )
            total_gross = float(db.fetchone()["total"])

            # Outstanding balances across all agencies
            db.execute("SELECT COALESCE(SUM(balance_amount), 0) as total FROM agencies WHERE balance_amount > 0")
            outstanding_balance = float(db.fetchone()["total"])

            return {
                "total_revenue_received": round(total_revenue, 2),
                "total_consumed_net": round(total_consumed, 2),
                "total_gross_value": round(total_gross, 2),
                "total_discount_given": round(total_discount, 2),
                "outstanding_balances": round(outstanding_balance, 2),
                "unspent_revenue": round(total_revenue - total_consumed, 2),
                "effective_margin_percent": round(
                    ((total_consumed / total_gross) * 100) if total_gross > 0 else 100, 1
                ),
                "period": {"start": start_date, "end": end_date},
            }

    @staticmethod
    def get_pack_performance_report() -> list:
        """Admin report: revenue vs usage breakdown by credit pack tier.
        Shows which pack tiers generate most revenue and usage."""
        with get_db() as db:
            db.execute(
                """SELECT
                       stc.tier_key,
                       stc.name as tier_name,
                       stc.discount_percent,
                       stc.monthly_price as pack_price,
                       COUNT(DISTINCT bt_topup.id) as total_topups,
                       COALESCE(SUM(CASE WHEN bt_topup.transaction_type='topup' THEN bt_topup.net_amount ELSE 0 END), 0) as total_revenue,
                       COUNT(DISTINCT bt_charge.id) as total_charges,
                       COALESCE(SUM(CASE WHEN bt_charge.transaction_type='charge' THEN bt_charge.net_amount ELSE 0 END), 0) as total_spent,
                       COALESCE(SUM(CASE WHEN bt_charge.transaction_type='charge' THEN bt_charge.discount_amount ELSE 0 END), 0) as total_discount_given
                   FROM subscription_tier_config stc
                   LEFT JOIN balance_transactions bt_topup ON bt_topup.topup_pack_tier = stc.tier_key AND bt_topup.transaction_type='topup'
                   LEFT JOIN balance_transactions bt_charge ON bt_charge.agency_id IN (
                       SELECT agency_id FROM balance_transactions WHERE topup_pack_tier = stc.tier_key AND transaction_type='topup'
                   ) AND bt_charge.transaction_type='charge'
                   WHERE stc.is_active = 1
                   GROUP BY stc.tier_key, stc.name, stc.discount_percent, stc.monthly_price
                   ORDER BY total_revenue DESC"""
            )
            rows = db.fetchall()
            results = []
            for row in rows:
                r = dict(row)
                revenue = float(r.get("total_revenue") or 0)
                spent = float(r.get("total_spent") or 0)
                results.append({
                    "tier_key": r["tier_key"],
                    "tier_name": r["tier_name"],
                    "discount_percent": float(r.get("discount_percent") or 0),
                    "pack_price": float(r.get("pack_price") or 0),
                    "total_topups": int(r.get("total_topups") or 0),
                    "total_revenue": round(revenue, 2),
                    "total_charges": int(r.get("total_charges") or 0),
                    "total_spent": round(spent, 2),
                    "total_discount_given": round(float(r.get("total_discount_given") or 0), 2),
                    "net_retained": round(revenue - spent, 2),
                    "utilisation_percent": round((spent / revenue * 100) if revenue > 0 else 0, 1),
                })
            return results

    @staticmethod
    def get_agency_financial_summary(agency_id: str) -> dict:
        """Get detailed financial summary for a single agency (admin view)."""
        with get_db() as db:
            db.execute(
                """SELECT id, name, balance_amount, total_topup_amount, total_spent_amount, discount_percent
                   FROM agencies WHERE id=%s""",
                (agency_id,),
            )
            row = db.fetchone()
            if not row:
                return {"error": "Agency not found"}
            r = dict(row)

            # Get charge breakdown by check type
            db.execute(
                """SELECT check_type, COUNT(*) as count,
                          SUM(gross_amount) as total_gross,
                          SUM(discount_amount) as total_discount,
                          SUM(net_amount) as total_net
                   FROM balance_transactions
                   WHERE agency_id=%s AND transaction_type='charge'
                   GROUP BY check_type ORDER BY total_net DESC""",
                (agency_id,),
            )
            breakdown = [dict(row) for row in db.fetchall()]

            return {
                "agency_id": agency_id,
                "agency_name": r.get("name"),
                "balance": round(float(r.get("balance_amount") or 0), 2),
                "total_paid_in": round(float(r.get("total_topup_amount") or 0), 2),
                "total_actual_spend": round(float(r.get("total_spent_amount") or 0), 2),
                "discount_percent": float(r.get("discount_percent") or 0),
                "usage_breakdown": breakdown,
            }
