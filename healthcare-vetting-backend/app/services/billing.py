"""
Subscription & Billing Service
Manages subscription tiers (DB-driven), fractional credit system, rollover logic,
and recurring invoices. Supports Stripe (card) and manual recurring invoice billing.
"""
import json
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.utils.auth import generate_id


class BillingService:
    """Manage subscriptions, credits, and billing."""

    # -- Subscription Tier Management (DB-driven) --

    @staticmethod
    def get_tiers() -> dict:
        """Get all subscription tiers from the database."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM subscription_tier_config WHERE is_active=1 ORDER BY monthly_price ASC"
            ).fetchall()
            tiers = {}
            for row in rows:
                r = dict(row)
                tiers[r["tier_key"]] = {
                    "id": r["id"],
                    "name": r["name"],
                    "monthly_price": r["monthly_price"],
                    "per_worker_price": r["per_worker_price"],
                    "max_workers": r["max_workers"],
                    "monthly_checks": r["monthly_checks"],
                    "overage_rate": r.get("overage_rate", 0),
                    "allow_rollover": bool(r.get("allow_rollover", 0)),
                    "monitoring_included": bool(r.get("monitoring_included", 0)),
                    "monitoring_cap": r.get("monitoring_cap", 0),
                    "monitoring_addon_rate": r.get("monitoring_addon_rate", 0),
                    "features": json.loads(r["features"]) if isinstance(r["features"], str) else r["features"],
                    "is_active": bool(r.get("is_active", 1)),
                    "updated_at": r.get("updated_at"),
                }
            return tiers

    @staticmethod
    def update_tier(tier_key: str, data: dict) -> dict:
        """Update a subscription tier configuration."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=?", (tier_key,)
            ).fetchone()
            if not row:
                raise ValueError(f"Tier '{tier_key}' not found")

            updates = {}
            field_map = {
                "name": "name", "monthly_price": "monthly_price",
                "per_worker_price": "per_worker_price", "max_workers": "max_workers",
                "monthly_checks": "monthly_checks", "overage_rate": "overage_rate",
                "allow_rollover": "allow_rollover", "monitoring_included": "monitoring_included",
                "monitoring_cap": "monitoring_cap", "monitoring_addon_rate": "monitoring_addon_rate",
                "is_active": "is_active",
            }
            for key, col in field_map.items():
                if key in data and data[key] is not None:
                    val = data[key]
                    if key in ("allow_rollover", "monitoring_included", "is_active"):
                        val = 1 if val else 0
                    updates[col] = val

            if "features" in data and data["features"] is not None:
                updates["features"] = json.dumps(data["features"]) if isinstance(data["features"], list) else data["features"]

            if updates:
                updates["updated_at"] = now
                set_clause = ", ".join(f"{k}=?" for k in updates.keys())
                values = list(updates.values()) + [tier_key]
                db.execute(f"UPDATE subscription_tier_config SET {set_clause} WHERE tier_key=?", values)

            row = db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=?", (tier_key,)
            ).fetchone()
            r = dict(row)
            r["features"] = json.loads(r["features"]) if isinstance(r["features"], str) else r["features"]
            r["allow_rollover"] = bool(r.get("allow_rollover", 0))
            r["monitoring_included"] = bool(r.get("monitoring_included", 0))
            r["is_active"] = bool(r.get("is_active", 1))
            return r

    @staticmethod
    def create_tier(data: dict) -> dict:
        """Create a new subscription tier."""
        now = datetime.now(timezone.utc).isoformat()
        tier_id = generate_id()
        tier_key = data.get("tier_key", "").lower().replace(" ", "_")
        if not tier_key:
            raise ValueError("tier_key is required")

        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM subscription_tier_config WHERE tier_key=?", (tier_key,)
            ).fetchone()
            if existing:
                raise ValueError(f"Tier '{tier_key}' already exists")

            features = json.dumps(data.get("features", [])) if isinstance(data.get("features"), list) else data.get("features", "[]")
            db.execute(
                """INSERT INTO subscription_tier_config
                   (id, tier_key, name, monthly_price, per_worker_price, max_workers, monthly_checks,
                    overage_rate, allow_rollover, monitoring_included, monitoring_cap, monitoring_addon_rate,
                    features, is_active, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
                (tier_id, tier_key, data.get("name", tier_key.title()),
                 data.get("monthly_price", 0), data.get("per_worker_price", 0),
                 data.get("max_workers", 0), data.get("monthly_checks", 0),
                 data.get("overage_rate", 0),
                 1 if data.get("allow_rollover") else 0,
                 1 if data.get("monitoring_included") else 0,
                 data.get("monitoring_cap", 0), data.get("monitoring_addon_rate", 0),
                 features, now),
            )
            row = db.execute("SELECT * FROM subscription_tier_config WHERE id=?", (tier_id,)).fetchone()
            r = dict(row)
            r["features"] = json.loads(r["features"]) if isinstance(r["features"], str) else r["features"]
            return r

    @staticmethod
    def delete_tier(tier_key: str) -> dict:
        """Soft-delete a subscription tier (set is_active=0)."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=?", (tier_key,)
            ).fetchone()
            if not row:
                raise ValueError(f"Tier '{tier_key}' not found")
            active_count = db.execute(
                "SELECT COUNT(*) FROM agency_subscriptions WHERE tier=? AND status='active'",
                (tier_key,),
            ).fetchone()[0]
            if active_count > 0:
                raise ValueError(f"Cannot delete tier '{tier_key}' - {active_count} active subscription(s) use it.")
            db.execute(
                "UPDATE subscription_tier_config SET is_active=0, updated_at=? WHERE tier_key=?",
                (now, tier_key),
            )
            return {"deleted": True, "tier_key": tier_key}

    # -- Partial Credit Rates --

    @staticmethod
    def get_partial_credit_rates() -> list:
        """Get all partial credit rate configurations."""
        with get_db() as db:
            rows = db.execute("SELECT * FROM partial_credit_rates ORDER BY credit_value DESC").fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_partial_credit_rate(check_type: str, data: dict) -> dict:
        """Update a partial credit rate."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM partial_credit_rates WHERE check_type=?", (check_type,)
            ).fetchone()
            if not row:
                raise ValueError(f"Partial credit rate '{check_type}' not found")

            updates = {}
            if "label" in data and data["label"] is not None:
                updates["label"] = data["label"]
            if "credit_value" in data and data["credit_value"] is not None:
                updates["credit_value"] = float(data["credit_value"])
            if "third_party_cost" in data and data["third_party_cost"] is not None:
                updates["third_party_cost"] = float(data["third_party_cost"])

            if updates:
                updates["updated_at"] = now
                set_clause = ", ".join(f"{k}=?" for k in updates.keys())
                values = list(updates.values()) + [check_type]
                db.execute(f"UPDATE partial_credit_rates SET {set_clause} WHERE check_type=?", values)

            row = db.execute("SELECT * FROM partial_credit_rates WHERE check_type=?", (check_type,)).fetchone()
            return dict(row)

    @staticmethod
    def create_partial_credit_rate(data: dict) -> dict:
        """Create a new partial credit rate."""
        rate_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            existing = db.execute(
                "SELECT id FROM partial_credit_rates WHERE check_type=?", (data["check_type"],)
            ).fetchone()
            if existing:
                raise ValueError(f"Partial credit rate '{data['check_type']}' already exists")

            db.execute(
                "INSERT INTO partial_credit_rates (id, check_type, label, credit_value, third_party_cost, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                (rate_id, data["check_type"], data.get("label", data["check_type"]),
                 float(data.get("credit_value", 1.0)), float(data.get("third_party_cost", 0)), now),
            )
            row = db.execute("SELECT * FROM partial_credit_rates WHERE id=?", (rate_id,)).fetchone()
            return dict(row)

    @staticmethod
    def delete_partial_credit_rate(check_type: str) -> dict:
        """Delete a partial credit rate."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM partial_credit_rates WHERE check_type=?", (check_type,)
            ).fetchone()
            if not row:
                raise ValueError(f"Partial credit rate '{check_type}' not found")
            db.execute("DELETE FROM partial_credit_rates WHERE check_type=?", (check_type,))
            return {"deleted": True, "check_type": check_type}

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
        """Create a new subscription for an agency using DB-driven tier config."""
        now = datetime.now(timezone.utc).isoformat()
        sub_id = generate_id()

        with get_db() as db:
            # Get tier config from DB
            tier_row = db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=? AND is_active=1", (tier,)
            ).fetchone()
            if not tier_row:
                raise ValueError(f"Invalid or inactive tier: {tier}")
            tier_info = dict(tier_row)

            # Deactivate any existing subscription
            db.execute(
                "UPDATE agency_subscriptions SET status='cancelled', cancelled_at=? WHERE agency_id=? AND status='active'",
                (now, agency_id),
            )

            next_billing = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

            db.execute(
                """INSERT INTO agency_subscriptions
                   (id, agency_id, tier, billing_method, monthly_amount, per_worker_amount,
                    max_workers, monthly_checks, checks_used, credits_total, credits_used,
                    rollover_credits, allow_rollover, overage_rate,
                    stripe_payment_method_id, stripe_subscription_id,
                    status, current_period_start, current_period_end, next_billing_date, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, 0, 0, ?, ?, ?, ?, 'active', ?, ?, ?, ?)""",
                (sub_id, agency_id, tier, billing_method,
                 tier_info["monthly_price"], tier_info["per_worker_price"],
                 tier_info["max_workers"], tier_info["monthly_checks"],
                 float(tier_info["monthly_checks"]),
                 1 if tier_info.get("allow_rollover") else 0,
                 float(tier_info.get("overage_rate", 0)),
                 stripe_payment_method_id, None,
                 now, next_billing, next_billing, now),
            )

            # If invoice billing, create the first invoice
            if billing_method == "invoice":
                amount = tier_info["monthly_price"]
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, created_at)
                       VALUES (?, ?, 'subscription', ?, 0, ?, 'pending', ?)""",
                    (inv_id, agency_id,
                     f"{tier_info['name']} Plan - Monthly Subscription",
                     amount, now),
                )

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
        """Generate recurring invoices for all active subscriptions due for billing.
        Handles credit rollover or expiry based on tier settings."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        with get_db() as db:
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

                inv_id = generate_id()
                tier_row = db.execute(
                    "SELECT * FROM subscription_tier_config WHERE tier_key=?", (s["tier"],)
                ).fetchone()
                tier_name = dict(tier_row)["name"] if tier_row else s["tier"]

                db.execute(
                    """INSERT INTO invoices
                       (id, agency_id, check_type, description, cost_amount, sell_amount, status, created_at)
                       VALUES (?, ?, 'subscription', ?, 0, ?, 'pending', ?)""",
                    (inv_id, s["agency_id"],
                     f"{tier_name} Plan - Monthly Subscription",
                     amount, now_str),
                )

                # Handle credit rollover
                credits_total = float(s.get("credits_total") or s.get("monthly_checks") or 0)
                credits_used = float(s.get("credits_used") or 0)
                unused_credits = max(0, credits_total - credits_used)
                allow_rollover = bool(s.get("allow_rollover", 0))

                new_rollover = 0.0
                if allow_rollover and unused_credits > 0:
                    # Cap rollover at 50% of monthly allowance
                    max_rollover = credits_total * 0.5
                    new_rollover = min(unused_credits, max_rollover)

                    txn_id = generate_id()
                    db.execute(
                        """INSERT INTO credit_transactions
                           (id, agency_id, check_type, credits_consumed, credit_balance_after,
                            is_rollover, description, created_at)
                           VALUES (?, ?, 'rollover', 0, ?, 1, ?, ?)""",
                        (txn_id, s["agency_id"], new_rollover,
                         f"Rolled over {round(new_rollover, 2)} unused credits to next cycle", now_str),
                    )

                # Reset credits for new period
                new_credits_total = float(s.get("monthly_checks") or 0)
                next_billing = (now + timedelta(days=30)).isoformat()
                db.execute(
                    """UPDATE agency_subscriptions
                       SET next_billing_date=?, current_period_start=?, current_period_end=?,
                           credits_total=?, credits_used=0, rollover_credits=?
                       WHERE id=?""",
                    (next_billing, now_str, next_billing,
                     new_credits_total, new_rollover, s["id"]),
                )

                from app.services.email_service import EmailService
                EmailService.send_invoice_notification(
                    s["agency_email"], s["agency_name"], inv_id, amount,
                    f"{tier_name} Plan - Monthly Subscription",
                )

                generated.append({
                    "agency_id": s["agency_id"],
                    "invoice_id": inv_id,
                    "amount": amount,
                    "rolled_over_credits": round(new_rollover, 2),
                    "expired_credits": round(unused_credits - new_rollover, 2) if not allow_rollover or unused_credits > new_rollover else 0,
                })

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
        """Get remaining check credits for a subscription agency (supports fractional credits)."""
        with get_db() as db:
            sub = db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            ).fetchone()
            if not sub:
                return {
                    "has_subscription": False,
                    "credits_total": 0, "credits_used": 0, "credits_remaining": 0,
                    "rollover_credits": 0, "allow_rollover": False,
                    "monthly_checks": 0, "checks_used": 0, "checks_remaining": 0,
                    "tier": None, "overage_rate": 0,
                }

            s = dict(sub)
            credits_total = float(s.get("credits_total") or s.get("monthly_checks") or 0)
            credits_used = float(s.get("credits_used") or 0)
            rollover = float(s.get("rollover_credits") or 0)
            total_available = credits_total + rollover
            credits_remaining = max(0, total_available - credits_used)

            tier_row = db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=?", (s["tier"],)
            ).fetchone()
            tier_name = dict(tier_row)["name"] if tier_row else s["tier"]
            overage_rate = float(s.get("overage_rate") or (dict(tier_row).get("overage_rate", 0) if tier_row else 0))

            return {
                "has_subscription": True,
                "subscription_id": s["id"],
                "tier": s["tier"],
                "tier_name": tier_name,
                "credits_total": round(credits_total, 2),
                "credits_used": round(credits_used, 2),
                "credits_remaining": round(credits_remaining, 2),
                "rollover_credits": round(rollover, 2),
                "allow_rollover": bool(s.get("allow_rollover", 0)),
                "overage_rate": round(overage_rate, 2),
                "monthly_checks": int(s.get("monthly_checks") or 0),
                "checks_used": round(credits_used, 2),
                "checks_remaining": round(credits_remaining, 2),
                "current_period_start": s.get("current_period_start"),
                "current_period_end": s.get("current_period_end"),
                "billing_method": s.get("billing_method"),
            }

    @staticmethod
    def use_subscription_check(agency_id: str, candidate_id: str, check_description: str,
                                sell_amount: float, cost_amount: float = 0,
                                check_type: str = "full_vetting") -> dict:
        """Use subscription credits for a check. Supports fractional credits based on check_type.
        Auto-marks as paid if within credit, creates overage invoice if exceeded."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            sub = db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=? AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            ).fetchone()

            # Look up credit value for this check type
            pcr = db.execute(
                "SELECT * FROM partial_credit_rates WHERE check_type=?", (check_type,)
            ).fetchone()
            credit_value = float(dict(pcr)["credit_value"]) if pcr else 1.0

            if not sub:
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                       VALUES (?, ?, ?, 'vetting', ?, ?, ?, 'pending', ?)""",
                    (inv_id, agency_id, candidate_id, check_description, cost_amount, sell_amount, now),
                )
                return {"invoice_id": inv_id, "status": "pending", "within_credit": False,
                        "credits_consumed": 0, "message": "No active subscription. Invoice created as pending."}

            s = dict(sub)
            credits_total = float(s.get("credits_total") or s.get("monthly_checks") or 0)
            credits_used = float(s.get("credits_used") or 0)
            rollover = float(s.get("rollover_credits") or 0)
            total_available = credits_total + rollover
            overage_rate = float(s.get("overage_rate") or 0)

            new_credits_used = credits_used + credit_value
            credit_balance_after = max(0, total_available - new_credits_used)

            if new_credits_used <= total_available:
                # Within credit — auto-mark as paid
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, paid_at, created_at)
                       VALUES (?, ?, ?, 'vetting', ?, ?, ?, 'paid', ?, ?)""",
                    (inv_id, agency_id, candidate_id, check_description, cost_amount, 0, now, now),
                )
                db.execute(
                    "UPDATE agency_subscriptions SET credits_used = credits_used + ? WHERE id=?",
                    (credit_value, s["id"]),
                )
                # Record credit transaction
                txn_id = generate_id()
                db.execute(
                    """INSERT INTO credit_transactions
                       (id, agency_id, candidate_id, check_type, credits_consumed, credit_balance_after,
                        unit_cost, charge_amount, is_overage, description, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, ?, ?)""",
                    (txn_id, agency_id, candidate_id, check_type, credit_value,
                     credit_balance_after, cost_amount, check_description, now),
                )
                return {
                    "invoice_id": inv_id,
                    "status": "paid",
                    "within_credit": True,
                    "credits_consumed": credit_value,
                    "credits_remaining": round(credit_balance_after, 2),
                    "message": f"Check covered by subscription credit ({credit_value} credits used). {round(credit_balance_after, 2)} credits remaining.",
                }
            else:
                # Exceeded credit — create overage invoice
                overage_charge = round(credit_value * overage_rate, 2) if overage_rate > 0 else sell_amount
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at)
                       VALUES (?, ?, ?, 'vetting', ?, ?, ?, 'pending', ?)""",
                    (inv_id, agency_id, candidate_id,
                     f"{check_description} (overage - {credit_value} credits)",
                     cost_amount, overage_charge, now),
                )
                db.execute(
                    "UPDATE agency_subscriptions SET credits_used = credits_used + ? WHERE id=?",
                    (credit_value, s["id"]),
                )
                txn_id = generate_id()
                db.execute(
                    """INSERT INTO credit_transactions
                       (id, agency_id, candidate_id, check_type, credits_consumed, credit_balance_after,
                        unit_cost, charge_amount, is_overage, description, created_at)
                       VALUES (?, ?, ?, ?, ?, 0, ?, ?, 1, ?, ?)""",
                    (txn_id, agency_id, candidate_id, check_type, credit_value,
                     cost_amount, overage_charge,
                     f"{check_description} (overage)", now),
                )
                return {
                    "invoice_id": inv_id,
                    "status": "pending",
                    "within_credit": False,
                    "credits_consumed": credit_value,
                    "credits_remaining": 0,
                    "overage_charge": overage_charge,
                    "message": f"Monthly credit exceeded. Overage invoice created for \u00a3{overage_charge:.2f}.",
                }

    @staticmethod
    def get_credit_transactions(agency_id: str, limit: int = 50) -> list:
        """Get credit transaction history for an agency."""
        with get_db() as db:
            rows = db.execute(
                """SELECT ct.*, c.first_name, c.last_name
                   FROM credit_transactions ct
                   LEFT JOIN candidates c ON ct.candidate_id = c.id
                   WHERE ct.agency_id=?
                   ORDER BY ct.created_at DESC LIMIT ?""",
                (agency_id, limit),
            ).fetchall()
            return [dict(r) for r in rows]
