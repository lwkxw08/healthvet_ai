"""
Subscription & Billing Service
Manages Stripe payment integration, subscription tiers, and recurring invoices.
Supports both Stripe (card) and manual recurring invoice billing modes.
"""
import json
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.utils.auth import generate_id


# Subscription tier definitions
SUBSCRIPTION_TIERS = {
    "starter": {
        "name": "Starter",
        "max_workers": 50,
        "monthly_price": 299.00,
        "per_worker_price": 0,
        "monthly_checks": 50,
        "features": ["Up to 50 workers", "50 checks/month included", "Basic compliance dashboard", "Email alerts", "Standard support"],
    },
    "growth": {
        "name": "Growth",
        "max_workers": 200,
        "monthly_price": 799.00,
        "per_worker_price": 0,
        "monthly_checks": 200,
        "features": ["Up to 200 workers", "200 checks/month included", "Advanced analytics", "Priority alerts", "CQC audit pack", "Priority support"],
    },
    "enterprise": {
        "name": "Enterprise",
        "max_workers": 99999,
        "monthly_price": 1999.00,
        "per_worker_price": 0,
        "monthly_checks": 999999,
        "features": ["Unlimited workers", "Unlimited checks/month", "Full analytics suite", "Dedicated account manager",
                      "Custom integrations", "SLA guarantee", "White-label options"],
    },
    "per_worker": {
        "name": "Per Worker",
        "max_workers": 99999,
        "monthly_price": 0,
        "per_worker_price": 5.00,
        "monthly_checks": 0,
        "features": ["Pay per active worker", "No monthly check allowance", "Full feature access", "Flexible scaling"],
    },
}


class BillingService:
    """Manage subscriptions and billing."""

    @staticmethod
    def get_tiers() -> dict:
        return SUBSCRIPTION_TIERS

    @staticmethod
    def get_agency_subscription(agency_id: str) -> dict:
        """Get current subscription for an agency."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            ).fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def create_subscription(agency_id: str, tier: str, billing_method: str = "stripe",
                             stripe_payment_method_id: str = None) -> dict:
        """Create a new subscription for an agency."""
        if tier not in SUBSCRIPTION_TIERS:
            raise ValueError(f"Invalid tier: {tier}")

        tier_info = SUBSCRIPTION_TIERS[tier]
        now = datetime.now(timezone.utc).isoformat()
        sub_id = generate_id()

        with get_db() as db:
            # Deactivate any existing subscription
            db.execute(
                "UPDATE agency_subscriptions SET status='cancelled', cancelled_at=? WHERE agency_id=? AND status='active'",
                (now, agency_id),
            )

            # Calculate next billing date (1 month from now)
            next_billing = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

            # Create subscription
            db.execute(
                """INSERT INTO agency_subscriptions
                   (id, agency_id, tier, billing_method, monthly_amount, per_worker_amount,
                    max_workers, monthly_checks, checks_used, stripe_payment_method_id, stripe_subscription_id,
                    status, current_period_start, current_period_end, next_billing_date,
                    created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, 'active', ?, ?, ?, ?)""",
                (sub_id, agency_id, tier, billing_method,
                 tier_info["monthly_price"], tier_info["per_worker_price"],
                 tier_info["max_workers"], tier_info.get("monthly_checks", 0),
                 stripe_payment_method_id, None,
                 now, next_billing, next_billing, now),
            )

            # If invoice billing, create the first invoice
            if billing_method == "invoice":
                amount = tier_info["monthly_price"]
                if tier == "per_worker":
                    # Count current workers
                    workers = db.execute(
                        "SELECT COUNT(*) as cnt FROM agency_candidates WHERE agency_id=?",
                        (agency_id,),
                    ).fetchone()
                    worker_count = dict(workers)["cnt"] if workers else 0
                    amount = worker_count * tier_info["per_worker_price"]

                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices
                       (id, agency_id, check_type, description, cost_amount, sell_amount,
                        status, created_at)
                       VALUES (?, ?, 'subscription', ?, 0, ?, 'pending', ?)""",
                    (inv_id, agency_id,
                     f"{tier_info['name']} Plan - Monthly Subscription",
                     amount, now),
                )

            # Send confirmation email
            from app.services.email_service import EmailService
            agency = db.execute("SELECT * FROM agencies WHERE id=?", (agency_id,)).fetchone()
            if agency:
                a = dict(agency)
                EmailService.send_subscription_confirmation(
                    a["email"], a["name"], tier_info["name"], tier_info["monthly_price"],
                )

            row = db.execute("SELECT * FROM agency_subscriptions WHERE id=?", (sub_id,)).fetchone()
            return dict(row)

    @staticmethod
    def cancel_subscription(agency_id: str) -> dict:
        """Cancel an agency's subscription."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE agency_subscriptions SET status='cancelled', cancelled_at=? WHERE agency_id=? AND status='active'",
                (now, agency_id),
            )
            return {"status": "cancelled", "cancelled_at": now}

    @staticmethod
    def generate_recurring_invoices():
        """Generate recurring invoices for all active subscriptions due for billing."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        with get_db() as db:
            # Get subscriptions due for billing
            due_subs = db.execute(
                """SELECT s.*, a.name as agency_name, a.email as agency_email
                   FROM agency_subscriptions s
                   JOIN agencies a ON s.agency_id = a.id
                   WHERE s.status='active' AND s.next_billing_date <= ?""",
                (now_str,),
            ).fetchall()

            generated = []
            for sub in due_subs:
                s = dict(sub)
                amount = s["monthly_amount"]

                if s["tier"] == "per_worker":
                    workers = db.execute(
                        "SELECT COUNT(*) as cnt FROM agency_candidates WHERE agency_id=?",
                        (s["agency_id"],),
                    ).fetchone()
                    worker_count = dict(workers)["cnt"] if workers else 0
                    amount = worker_count * s["per_worker_amount"]

                # Create invoice
                inv_id = generate_id()
                tier_info = SUBSCRIPTION_TIERS.get(s["tier"], {})
                db.execute(
                    """INSERT INTO invoices
                       (id, agency_id, check_type, description, cost_amount, sell_amount,
                        status, created_at)
                       VALUES (?, ?, 'subscription', ?, 0, ?, 'pending', ?)""",
                    (inv_id, s["agency_id"],
                     f"{tier_info.get('name', s['tier'])} Plan - Monthly Subscription",
                     amount, now_str),
                )

                # Update next billing date and reset checks_used for new period
                next_billing = (now + timedelta(days=30)).isoformat()
                db.execute(
                    "UPDATE agency_subscriptions SET next_billing_date=?, current_period_start=?, current_period_end=?, checks_used=0 WHERE id=?",
                    (next_billing, now_str, next_billing, s["id"]),
                )

                # Send invoice notification
                from app.services.email_service import EmailService
                EmailService.send_invoice_notification(
                    s["agency_email"], s["agency_name"], inv_id, amount,
                    f"{tier_info.get('name', s['tier'])} Plan - Monthly Subscription",
                )

                generated.append({"agency_id": s["agency_id"], "invoice_id": inv_id, "amount": amount})

            return generated

    @staticmethod
    def get_billing_history(agency_id: str) -> list:
        """Get billing/invoice history for an agency."""
        with get_db() as db:
            rows = db.execute(
                """SELECT * FROM invoices WHERE agency_id=?
                   ORDER BY created_at DESC""",
                (agency_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def simulate_stripe_payment(invoice_id: str) -> dict:
        """Simulate a Stripe payment for an invoice (in production, use real Stripe API)."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE invoices SET status='paid', paid_at=? WHERE id=?",
                (now, invoice_id),
            )
            row = db.execute("SELECT * FROM invoices WHERE id=?", (invoice_id,)).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_remaining_checks(agency_id: str) -> dict:
        """Get remaining check credits for a subscription agency."""
        with get_db() as db:
            sub = db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            ).fetchone()
            if not sub:
                return {"has_subscription": False, "monthly_checks": 0, "checks_used": 0, "checks_remaining": 0, "tier": None}

            s = dict(sub)
            monthly_checks = s.get("monthly_checks") or 0
            checks_used = s.get("checks_used") or 0
            checks_remaining = max(0, monthly_checks - checks_used)

            return {
                "has_subscription": True,
                "subscription_id": s["id"],
                "tier": s["tier"],
                "tier_name": SUBSCRIPTION_TIERS.get(s["tier"], {}).get("name", s["tier"]),
                "monthly_checks": monthly_checks,
                "checks_used": checks_used,
                "checks_remaining": checks_remaining,
                "current_period_start": s.get("current_period_start"),
                "current_period_end": s.get("current_period_end"),
                "billing_method": s.get("billing_method"),
            }

    @staticmethod
    def use_subscription_check(agency_id: str, candidate_id: str, check_description: str, sell_amount: float, cost_amount: float = 0) -> dict:
        """Use a subscription check credit. Auto-marks as paid if within allowance, creates pending invoice if exceeded."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            sub = db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            ).fetchone()

            if not sub:
                # No subscription — create a normal pending invoice
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                       VALUES (?, ?, ?, 'vetting', ?, ?, ?, 'pending', ?)""",
                    (inv_id, agency_id, candidate_id, check_description, cost_amount, sell_amount, now),
                )
                return {"invoice_id": inv_id, "status": "pending", "within_credit": False, "message": "No active subscription. Invoice created as pending."}

            s = dict(sub)
            monthly_checks = s.get("monthly_checks") or 0
            checks_used = s.get("checks_used") or 0

            if checks_used < monthly_checks:
                # Within credit — auto-mark as paid
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, paid_at, created_at)
                       VALUES (?, ?, ?, 'vetting', ?, ?, ?, 'paid', ?, ?)""",
                    (inv_id, agency_id, candidate_id, check_description, cost_amount, sell_amount, now, now),
                )
                # Increment checks_used
                db.execute(
                    "UPDATE agency_subscriptions SET checks_used = checks_used + 1 WHERE id=?",
                    (s["id"],),
                )
                remaining = monthly_checks - checks_used - 1
                return {
                    "invoice_id": inv_id,
                    "status": "paid",
                    "within_credit": True,
                    "checks_remaining": max(0, remaining),
                    "message": f"Check covered by subscription credit. {max(0, remaining)} checks remaining this month.",
                }
            else:
                # Exceeded credit — create pending invoice for manual payment
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                       VALUES (?, ?, ?, 'vetting', ?, ?, ?, 'pending', ?)""",
                    (inv_id, agency_id, candidate_id,
                     f"{check_description} (exceeded monthly credit)",
                     cost_amount, sell_amount, now),
                )
                return {
                    "invoice_id": inv_id,
                    "status": "pending",
                    "within_credit": False,
                    "checks_remaining": 0,
                    "message": "Monthly check credit exceeded. This check will be invoiced separately.",
                }
