"""
Credit Pack Billing Service
12-month credit pack model: agencies buy credit packs upfront, credits valid for 12 months.
No monthly recurring charge. Agencies top up manually or via auto top-up when credits run low/expire.
"""
import json
from datetime import datetime, timezone, timedelta
from typing import Optional
from app.database import get_db
from app.utils.auth import generate_id


class BillingService:
    """Manage subscriptions, credits, and billing."""

    # -- Subscription Tier Management (DB-driven) --

    @staticmethod
    def get_tiers() -> dict:
        """Get all credit pack tiers from the database."""
        with get_db() as db:
            db.execute(
                "SELECT * FROM subscription_tier_config WHERE is_active=1 ORDER BY monthly_price ASC"
            )
            rows = db.fetchall()
            tiers = {}
            for row in rows:
                r = dict(row)
                credits = int(r.get("monthly_checks") or 0)
                price = float(r.get("monthly_price") or 0)
                per_credit = round(price / credits, 2) if credits > 0 else 0
                tiers[r["tier_key"]] = {
                    "id": r["id"],
                    "name": r["name"],
                    "pack_price": price,
                    "credits": credits,
                    "per_credit_cost": per_credit,
                    "validity_months": 12,
                    # Legacy fields kept for backward compat
                    "monthly_price": price,
                    "per_worker_price": r["per_worker_price"],
                    "max_workers": r["max_workers"],
                    "monthly_checks": credits,
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
            db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=%s", (tier_key,)
            )
            row = db.fetchone()
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
                set_clause = ", ".join(f"{k}=%s" for k in updates.keys())
                values = list(updates.values()) + [tier_key]
                db.execute(f"UPDATE subscription_tier_config SET {set_clause} WHERE tier_key=%s", values)

            db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=%s", (tier_key,)
            )
            row = db.fetchone()
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
            db.execute(
                "SELECT id FROM subscription_tier_config WHERE tier_key=%s", (tier_key,)
            )
            existing = db.fetchone()
            if existing:
                raise ValueError(f"Tier '{tier_key}' already exists")

            features = json.dumps(data.get("features", [])) if isinstance(data.get("features"), list) else data.get("features", "[]")
            db.execute(
                """INSERT INTO subscription_tier_config
                   (id, tier_key, name, monthly_price, per_worker_price, max_workers, monthly_checks,
                    overage_rate, allow_rollover, monitoring_included, monitoring_cap, monitoring_addon_rate,
                    features, is_active, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)""",
                (tier_id, tier_key, data.get("name", tier_key.title()),
                 data.get("monthly_price", 0), data.get("per_worker_price", 0),
                 data.get("max_workers", 0), data.get("monthly_checks", 0),
                 data.get("overage_rate", 0),
                 1 if data.get("allow_rollover") else 0,
                 1 if data.get("monitoring_included") else 0,
                 data.get("monitoring_cap", 0), data.get("monitoring_addon_rate", 0),
                 features, now),
            )
            db.execute("SELECT * FROM subscription_tier_config WHERE id=%s", (tier_id,))
            row = db.fetchone()
            r = dict(row)
            r["features"] = json.loads(r["features"]) if isinstance(r["features"], str) else r["features"]
            return r

    @staticmethod
    def delete_tier(tier_key: str) -> dict:
        """Soft-delete a subscription tier (set is_active=0)."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=%s", (tier_key,)
            )
            row = db.fetchone()
            if not row:
                raise ValueError(f"Tier '{tier_key}' not found")
            db.execute(
                "SELECT COUNT(*) AS cnt FROM agency_subscriptions WHERE tier=%s AND status='active'",
                (tier_key,),
            )["cnt"]
            active_count = db.fetchone()
            if active_count > 0:
                raise ValueError(f"Cannot delete tier '{tier_key}' - {active_count} active subscription(s) use it.")
            db.execute(
                "UPDATE subscription_tier_config SET is_active=0, updated_at=%s WHERE tier_key=%s",
                (now, tier_key),
            )
            return {"deleted": True, "tier_key": tier_key}

    # -- Partial Credit Rates --

    @staticmethod
    def get_partial_credit_rates() -> list:
        """Get all partial credit rate configurations."""
        with get_db() as db:
            db.execute("SELECT * FROM partial_credit_rates ORDER BY credit_value DESC")
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def update_partial_credit_rate(check_type: str, data: dict) -> dict:
        """Update a partial credit rate."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "SELECT * FROM partial_credit_rates WHERE check_type=%s", (check_type,)
            )
            row = db.fetchone()
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
                set_clause = ", ".join(f"{k}=%s" for k in updates.keys())
                values = list(updates.values()) + [check_type]
                db.execute(f"UPDATE partial_credit_rates SET {set_clause} WHERE check_type=%s", values)

            db.execute("SELECT * FROM partial_credit_rates WHERE check_type=%s", (check_type,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def create_partial_credit_rate(data: dict) -> dict:
        """Create a new partial credit rate."""
        rate_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "SELECT id FROM partial_credit_rates WHERE check_type=%s", (data["check_type"],)
            )
            existing = db.fetchone()
            if existing:
                raise ValueError(f"Partial credit rate '{data['check_type']}' already exists")

            db.execute(
                "INSERT INTO partial_credit_rates (id, check_type, label, credit_value, third_party_cost, updated_at) VALUES (%s, %s, %s, %s, %s, %s)",
                (rate_id, data["check_type"], data.get("label", data["check_type"]),
                 float(data.get("credit_value", 1.0)), float(data.get("third_party_cost", 0)), now),
            )
            db.execute("SELECT * FROM partial_credit_rates WHERE id=%s", (rate_id,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def delete_partial_credit_rate(check_type: str) -> dict:
        """Delete a partial credit rate."""
        with get_db() as db:
            db.execute(
                "SELECT * FROM partial_credit_rates WHERE check_type=%s", (check_type,)
            )
            row = db.fetchone()
            if not row:
                raise ValueError(f"Partial credit rate '{check_type}' not found")
            db.execute("DELETE FROM partial_credit_rates WHERE check_type=%s", (check_type,))
            return {"deleted": True, "check_type": check_type}

    @staticmethod
    def get_agency_subscription(agency_id: str) -> dict:
        """Get current subscription for an agency."""
        with get_db() as db:
            db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=%s AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            )
            row = db.fetchone()
            if row:
                return dict(row)
            return None

    @staticmethod
    def create_subscription(agency_id: str, tier: str, billing_method: str = "stripe",
                             stripe_payment_method_id: str = None) -> dict:
        """Purchase a credit pack for an agency. Credits valid for 12 months from purchase."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        expires_at = (now + timedelta(days=365)).isoformat()
        sub_id = generate_id()

        with get_db() as db:
            # Get tier config from DB
            db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=%s AND is_active=1", (tier,)
            )
            tier_row = db.fetchone()
            if not tier_row:
                raise ValueError(f"Invalid or inactive credit pack: {tier}")
            tier_info = dict(tier_row)

            pack_price = float(tier_info["monthly_price"])
            pack_credits = float(tier_info["monthly_checks"])
            pack_name = tier_info["name"]

            # Check if agency has an active credit pack with remaining credits
            db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=%s AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            )
            existing = db.fetchone()

            if existing:
                ex = dict(existing)
                old_remaining = max(0, float(ex.get("credits_total") or 0) - float(ex.get("credits_used") or 0))
                # Deactivate old pack - carry over remaining credits
                db.execute(
                    "UPDATE agency_subscriptions SET status='replaced', cancelled_at=%s WHERE id=%s",
                    (now_str, ex["id"]),
                )
                # Add remaining credits to new pack
                pack_credits += old_remaining

            db.execute(
                """INSERT INTO agency_subscriptions
                   (id, agency_id, tier, billing_method, monthly_amount, per_worker_amount,
                    max_workers, monthly_checks, checks_used, credits_total, credits_used,
                    rollover_credits, allow_rollover, overage_rate,
                    stripe_payment_method_id, stripe_subscription_id,
                    status, current_period_start, current_period_end, next_billing_date,
                    expires_at, pack_name, created_at)
                   VALUES (%s, %s, %s, %s, %s, 0, 99999, %s, 0, %s, 0, 0, 0, 0,
                    %s, NULL, 'active', %s, %s, %s, %s, %s, %s)""",
                (sub_id, agency_id, tier, billing_method,
                 pack_price, int(pack_credits), pack_credits,
                 stripe_payment_method_id,
                 now_str, expires_at, expires_at,
                 expires_at, pack_name, now_str),
            )

            # Create invoice for the credit pack purchase
            inv_id = generate_id()
            db.execute(
                """INSERT INTO invoices (id, agency_id, check_type, description, cost_amount, sell_amount, status, created_at)
                   VALUES (%s, %s, 'credit_pack', %s, 0, %s, %s, %s)""",
                (inv_id, agency_id,
                 f"{pack_name} - {int(tier_info['monthly_checks'])} Credits (12 months)",
                 pack_price,
                 'paid' if billing_method == 'stripe' else 'pending',
                 now_str),
            )

            from app.services.email_service import EmailService
            db.execute("SELECT * FROM agencies WHERE id=%s", (agency_id,))
            agency = db.fetchone()
            if agency:
                a = dict(agency)
                EmailService.send_subscription_confirmation(
                    a["email"], a["name"], pack_name, pack_price,
                )

            db.execute("SELECT * FROM agency_subscriptions WHERE id=%s", (sub_id,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def cancel_subscription(agency_id: str) -> dict:
        """Cancel an agency's subscription."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE agency_subscriptions SET status='cancelled', cancelled_at=%s WHERE agency_id=%s AND status='active'",
                (now, agency_id),
            )
            return {"status": "cancelled", "cancelled_at": now}

    @staticmethod
    def generate_recurring_invoices():
        """Process expired credit packs and handle auto top-ups.
        Called periodically to check for expired packs and trigger auto top-ups."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()

        with get_db() as db:
            # Find expired or nearly-expired credit packs
            db.execute(
                """SELECT s.*, a.name as agency_name, a.email as agency_email
                   FROM agency_subscriptions s
                   JOIN agencies a ON s.agency_id = a.id
                   WHERE s.status='active' AND s.expires_at IS NOT NULL AND s.expires_at <= %s""",
                (now_str,),
            )
            expired_subs = db.fetchall()

            generated = []
            for sub in expired_subs:
                s = dict(sub)
                auto_topup = bool(s.get("auto_topup", 0))
                auto_topup_tier = s.get("auto_topup_tier") or s.get("tier")

                if auto_topup:
                    # Auto top-up: purchase same or configured tier
                    try:
                        result = BillingService.create_subscription(
                            s["agency_id"], auto_topup_tier, s.get("billing_method", "stripe"),
                        )
                        generated.append({
                            "agency_id": s["agency_id"],
                            "action": "auto_topup",
                            "new_pack": auto_topup_tier,
                            "credits": result.get("credits_total", 0),
                        })
                    except Exception as e:
                        generated.append({
                            "agency_id": s["agency_id"],
                            "action": "auto_topup_failed",
                            "error": str(e),
                        })
                else:
                    # Expire the pack
                    credits_remaining = max(0, float(s.get("credits_total") or 0) - float(s.get("credits_used") or 0))
                    db.execute(
                        "UPDATE agency_subscriptions SET status='expired', cancelled_at=%s WHERE id=%s",
                        (now_str, s["id"]),
                    )

                    # Record expiry transaction
                    if credits_remaining > 0:
                        txn_id = generate_id()
                        db.execute(
                            """INSERT INTO credit_transactions
                               (id, agency_id, check_type, credits_consumed, credit_balance_after,
                                is_rollover, description, created_at)
                               VALUES (%s, %s, 'expiry', %s, 0, 0, %s, %s)""",
                            (txn_id, s["agency_id"], credits_remaining,
                             f"{round(credits_remaining, 1)} credits expired (12-month validity ended)", now_str),
                        )

                    from app.services.email_service import EmailService
                    EmailService.send_invoice_notification(
                        s["agency_email"], s["agency_name"], None, 0,
                        f"Your credit pack has expired. {round(credits_remaining, 1)} unused credits were forfeited. Purchase a new pack to continue.",
                    )

                    generated.append({
                        "agency_id": s["agency_id"],
                        "action": "expired",
                        "expired_credits": round(credits_remaining, 2),
                    })

            return generated

    @staticmethod
    def get_billing_history(agency_id: str) -> list:
        """Get billing/invoice history for an agency."""
        with get_db() as db:
            db.execute(
                """SELECT * FROM invoices WHERE agency_id=%s
                   ORDER BY created_at DESC""",
                (agency_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def simulate_stripe_payment(invoice_id: str) -> dict:
        """Simulate a Stripe payment for an invoice (in production, use real Stripe API)."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE invoices SET status='paid', paid_at=%s WHERE id=%s",
                (now, invoice_id),
            )
            db.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
            row = db.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_remaining_checks(agency_id: str) -> dict:
        """Get remaining check credits for an agency's active credit pack."""
        with get_db() as db:
            db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=%s AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            )
            sub = db.fetchone()
            if not sub:
                return {
                    "has_subscription": False,
                    "has_credit_pack": False,
                    "credits_total": 0, "credits_used": 0, "credits_remaining": 0,
                    "rollover_credits": 0, "allow_rollover": False,
                    "monthly_checks": 0, "checks_used": 0, "checks_remaining": 0,
                    "tier": None, "overage_rate": 0,
                    "expires_at": None, "days_remaining": 0,
                    "auto_topup": False, "auto_topup_tier": None,
                }

            s = dict(sub)
            credits_total = float(s.get("credits_total") or s.get("monthly_checks") or 0)
            credits_used = float(s.get("credits_used") or 0)
            credits_remaining = max(0, credits_total - credits_used)

            db.execute(
                "SELECT * FROM subscription_tier_config WHERE tier_key=%s", (s["tier"],)
            )
            tier_row = db.fetchone()
            tier_name = dict(tier_row)["name"] if tier_row else s.get("pack_name") or s["tier"]

            # Calculate days remaining
            expires_at = s.get("expires_at")
            days_remaining = 0
            is_expired = False
            if expires_at:
                try:
                    exp_dt = datetime.fromisoformat(expires_at)
                    delta = exp_dt - datetime.now(timezone.utc)
                    days_remaining = max(0, delta.days)
                    is_expired = delta.total_seconds() <= 0
                except (ValueError, TypeError):
                    pass

            return {
                "has_subscription": True,
                "has_credit_pack": True,
                "subscription_id": s["id"],
                "tier": s["tier"],
                "tier_name": tier_name,
                "pack_name": s.get("pack_name") or tier_name,
                "credits_total": round(credits_total, 2),
                "credits_used": round(credits_used, 2),
                "credits_remaining": round(credits_remaining, 2),
                "rollover_credits": 0,
                "allow_rollover": False,
                "overage_rate": 0,
                "monthly_checks": int(credits_total),
                "checks_used": round(credits_used, 2),
                "checks_remaining": round(credits_remaining, 2),
                "expires_at": expires_at,
                "days_remaining": days_remaining,
                "is_expired": is_expired,
                "purchased_at": s.get("current_period_start") or s.get("created_at"),
                "auto_topup": bool(s.get("auto_topup", 0)),
                "auto_topup_tier": s.get("auto_topup_tier"),
                "billing_method": s.get("billing_method"),
            }

    @staticmethod
    def use_subscription_check(agency_id: str, candidate_id: str, check_description: str,
                                sell_amount: float, cost_amount: float = 0,
                                check_type: str = "full_vetting",
                                invite_id: Optional[str] = None) -> dict:
        """Use credit pack credits for a check. Checks expiry, then deducts credits.
        If no credits or pack expired, creates a PAYG invoice instead."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=%s AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            )
            sub = db.fetchone()

            # Look up credit value for this check type
            db.execute(
                "SELECT * FROM partial_credit_rates WHERE check_type=%s", (check_type,)
            )
            pcr = db.fetchone()
            credit_value = float(dict(pcr)["credit_value"]) if pcr else 1.0

            if not sub:
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at, invite_id)
                       VALUES (%s, %s, %s, 'vetting', %s, %s, %s, 'pending', %s, %s)""",
                    (inv_id, agency_id, candidate_id, check_description, cost_amount, sell_amount, now, invite_id),
                )
                return {"invoice_id": inv_id, "status": "pending", "within_credit": False,
                        "credits_consumed": 0, "message": "No active credit pack. Invoice created as pending. Purchase a credit pack to get started."}

            s = dict(sub)

            # Check if pack has expired
            expires_at = s.get("expires_at")
            if expires_at:
                try:
                    exp_dt = datetime.fromisoformat(expires_at)
                    if exp_dt <= datetime.now(timezone.utc):
                        # Pack expired — create PAYG invoice
                        inv_id = generate_id()
                        db.execute(
                            """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at, invite_id)
                               VALUES (%s, %s, %s, 'vetting', %s, %s, %s, 'pending', %s, %s)""",
                            (inv_id, agency_id, candidate_id,
                             f"{check_description} (credit pack expired)",
                             cost_amount, sell_amount, now, invite_id),
                        )
                        return {"invoice_id": inv_id, "status": "credits_expired", "within_credit": False,
                                "credits_consumed": 0, "message": "Credit pack has expired. Please purchase a new pack."}
                except (ValueError, TypeError):
                    pass

            credits_total = float(s.get("credits_total") or 0)
            credits_used = float(s.get("credits_used") or 0)
            credits_remaining = credits_total - credits_used

            new_credits_used = credits_used + credit_value
            credit_balance_after = max(0, credits_total - new_credits_used)

            if new_credits_used <= credits_total:
                # Within credit — auto-mark as paid
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, paid_at, created_at, invite_id)
                       VALUES (%s, %s, %s, 'vetting', %s, %s, %s, 'paid', %s, %s, %s)""",
                    (inv_id, agency_id, candidate_id, check_description, cost_amount, 0, now, now, invite_id),
                )
                db.execute(
                    "UPDATE agency_subscriptions SET credits_used = credits_used + %s WHERE id=%s",
                    (credit_value, s["id"]),
                )
                # Record credit transaction
                txn_id = generate_id()
                db.execute(
                    """INSERT INTO credit_transactions
                       (id, agency_id, candidate_id, check_type, credits_consumed, credit_balance_after,
                        unit_cost, charge_amount, is_overage, description, created_at, invite_id)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 0, 0, %s, %s, %s)""",
                    (txn_id, agency_id, candidate_id, check_type, credit_value,
                     credit_balance_after, cost_amount, check_description, now, invite_id),
                )
                return {
                    "invoice_id": inv_id,
                    "status": "paid",
                    "within_credit": True,
                    "credits_consumed": credit_value,
                    "credits_remaining": round(credit_balance_after, 2),
                    "message": f"Paid by credit pack ({credit_value} credits used). {round(credit_balance_after, 2)} credits remaining.",
                }
            else:
                # No credits left — create PAYG invoice
                inv_id = generate_id()
                db.execute(
                    """INSERT INTO invoices (id, agency_id, candidate_id, check_type, description, cost_amount, sell_amount, status, created_at, invite_id)
                       VALUES (%s, %s, %s, 'vetting', %s, %s, %s, 'pending', %s, %s)""",
                    (inv_id, agency_id, candidate_id,
                     f"{check_description} (credits exhausted)",
                     cost_amount, sell_amount, now, invite_id),
                )
                return {
                    "invoice_id": inv_id,
                    "status": "credits_exceeded",
                    "within_credit": False,
                    "credits_consumed": 0,
                    "credits_remaining": 0,
                    "message": "Credit pack exhausted. Please purchase a new pack to continue using credits.",
                }

    @staticmethod
    def get_credit_transactions(agency_id: str, limit: int = 50) -> list:
        """Get credit transaction history for an agency."""
        with get_db() as db:
            db.execute(
                """SELECT ct.*, c.first_name, c.last_name
                   FROM credit_transactions ct
                   LEFT JOIN candidates c ON ct.candidate_id = c.id
                   WHERE ct.agency_id=%s
                   ORDER BY ct.created_at DESC LIMIT %s""",
                (agency_id, limit),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    # -- Credit Pack Top-Up & Auto Top-Up --

    @staticmethod
    def topup_credits(agency_id: str, tier: str, billing_method: str = "stripe") -> dict:
        """Manual top-up: purchase a new credit pack. Carries over any remaining credits."""
        return BillingService.create_subscription(agency_id, tier, billing_method)

    @staticmethod
    def update_auto_topup(agency_id: str, enabled: bool, tier: str = None) -> dict:
        """Enable or disable auto top-up for an agency's credit pack."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "SELECT * FROM agency_subscriptions WHERE agency_id=%s AND status='active' ORDER BY created_at DESC LIMIT 1",
                (agency_id,),
            )
            sub = db.fetchone()
            if not sub:
                raise ValueError("No active credit pack found. Purchase a credit pack first.")

            s = dict(sub)
            auto_topup_tier = tier or s.get("tier")

            # Validate the auto-topup tier exists
            if enabled and auto_topup_tier:
                db.execute(
                    "SELECT * FROM subscription_tier_config WHERE tier_key=%s AND is_active=1",
                    (auto_topup_tier,),
                )
                tier_row = db.fetchone()
                if not tier_row:
                    raise ValueError(f"Invalid credit pack tier: {auto_topup_tier}")

            db.execute(
                "UPDATE agency_subscriptions SET auto_topup=%s, auto_topup_tier=%s WHERE id=%s",
                (1 if enabled else 0, auto_topup_tier if enabled else None, s["id"]),
            )

            return {
                "agency_id": agency_id,
                "auto_topup": enabled,
                "auto_topup_tier": auto_topup_tier if enabled else None,
                "message": f"Auto top-up {'enabled' if enabled else 'disabled'}" + (f" with {auto_topup_tier} pack" if enabled else ""),
            }

    # -- Agency Billing Mode --

    @staticmethod
    def get_agency_billing_mode(agency_id: str) -> dict:
        """Get the billing mode for an agency."""
        with get_db() as db:
            db.execute(
                "SELECT id, name, billing_mode, stripe_customer_id FROM agencies WHERE id=%s",
                (agency_id,),
            )
            row = db.fetchone()
            if not row:
                return {"billing_mode": "manual_invoicing", "stripe_customer_id": None}
            r = dict(row)
            return {
                "agency_id": r["id"],
                "agency_name": r["name"],
                "billing_mode": r.get("billing_mode") or "manual_invoicing",
                "stripe_customer_id": r.get("stripe_customer_id"),
            }

    @staticmethod
    def set_agency_billing_mode(agency_id: str, billing_mode: str, stripe_customer_id: str = None) -> dict:
        """Set the billing mode for an agency (admin only)."""
        valid_modes = {"manual_invoicing", "online_payment", "subscription", "credit_pack"}
        if billing_mode not in valid_modes:
            raise ValueError(f"Invalid billing_mode. Valid: {', '.join(valid_modes)}")

        with get_db() as db:
            db.execute("SELECT id, name FROM agencies WHERE id=%s", (agency_id,))
            row = db.fetchone()
            if not row:
                raise ValueError("Agency not found")

            updates = {"billing_mode": billing_mode}
            if stripe_customer_id is not None:
                updates["stripe_customer_id"] = stripe_customer_id

            set_clause = ", ".join(f"{k}=%s" for k in updates.keys())
            values = list(updates.values()) + [agency_id]
            db.execute(f"UPDATE agencies SET {set_clause} WHERE id=%s", values)

            return BillingService.get_agency_billing_mode(agency_id)

    # -- Payment Checkout (routes through configured provider) --

    @staticmethod
    def create_checkout_session(agency_id: str, invoice_id: str, success_url: str, cancel_url: str) -> dict:
        """Create a checkout session using the admin-configured payment provider.
        Falls back to simulation if no provider is configured."""
        import secrets as _secrets
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
            inv = db.fetchone()
            if not inv:
                raise ValueError("Invoice not found")
            invoice = dict(inv)

            if invoice["status"] == "paid":
                raise ValueError("Invoice is already paid")

            amount = invoice.get("adjusted_amount") or invoice["sell_amount"]

            # Try to use the configured payment provider
            try:
                from app.services.payment_providers import PaymentProviderService
                result = PaymentProviderService.create_checkout(
                    agency_id=agency_id,
                    invoice_id=invoice_id,
                    amount=float(amount),
                    payment_type="payg_invoice",
                    description=invoice.get("description") or "Invoice Payment",
                    success_url=success_url,
                    cancel_url=cancel_url,
                )
                # Update invoice with provider session info
                db.execute(
                    "UPDATE invoices SET stripe_session_id=%s, payment_method=%s WHERE id=%s",
                    (result.get("payment_id", ""), result.get("provider", "stripe"), invoice_id),
                )
                return {
                    "session_id": result.get("payment_id"),
                    "invoice_id": invoice_id,
                    "amount": amount,
                    "checkout_url": result.get("checkout_url"),
                    "provider": result.get("provider"),
                    "status": "created",
                }
            except (ValueError, ImportError):
                # No provider configured — fall back to simulation
                pass

            # Simulated fallback
            session_id = f"cs_simulated_{_secrets.token_hex(16)}"
            db.execute(
                "UPDATE invoices SET stripe_session_id=%s, payment_method='stripe' WHERE id=%s",
                (session_id, invoice_id),
            )
            checkout_url = f"{success_url}%ssession_id={session_id}&invoice_id={invoice_id}"

            return {
                "session_id": session_id,
                "invoice_id": invoice_id,
                "amount": amount,
                "checkout_url": checkout_url,
                "provider": "simulated",
                "status": "created",
            }

    @staticmethod
    def confirm_stripe_payment(session_id: str) -> dict:
        """Confirm a Stripe payment (webhook handler in production).
        Simulated: marks invoice as paid when called with valid session_id."""
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute(
                "SELECT * FROM invoices WHERE stripe_session_id=%s", (session_id,)
            )
            inv = db.fetchone()
            if not inv:
                raise ValueError("No invoice found for this session")
            invoice = dict(inv)

            if invoice["status"] == "paid":
                return {"invoice_id": invoice["id"], "status": "already_paid"}

            db.execute(
                "UPDATE invoices SET status='paid', paid_at=%s, payment_method='stripe', stripe_payment_intent_id=%s WHERE id=%s",
                (now, f"pi_simulated_{session_id[-16:]}", invoice["id"]),
            )

            return {
                "invoice_id": invoice["id"],
                "status": "paid",
                "paid_at": now,
                "amount": invoice.get("adjusted_amount") or invoice["sell_amount"],
            }

    @staticmethod
    def pay_invoice_online(invoice_id: str) -> dict:
        """Agency pays an invoice online using the configured payment provider.
        Falls back to simulation if no provider is configured."""
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
            inv = db.fetchone()
            if not inv:
                raise ValueError("Invoice not found")
            invoice = dict(inv)

            if invoice["status"] == "paid":
                return {"invoice_id": invoice_id, "status": "already_paid", "message": "Invoice is already paid"}

            amount = invoice.get("adjusted_amount") or invoice["sell_amount"]

            # Try configured provider first
            try:
                from app.services.payment_providers import PaymentProviderService
                result = PaymentProviderService.create_checkout(
                    agency_id=invoice["agency_id"],
                    invoice_id=invoice_id,
                    amount=float(amount),
                    payment_type="payg_invoice",
                    description=invoice.get("description") or "Invoice Payment",
                    success_url="https://viperai.io/payment/success",
                    cancel_url="https://viperai.io/payment/cancel",
                )
                return {
                    "invoice_id": invoice_id,
                    "status": "checkout_created",
                    "checkout_url": result.get("checkout_url"),
                    "provider": result.get("provider"),
                    "amount": amount,
                    "message": f"Checkout session created via {result.get('provider', 'provider')}",
                }
            except (ValueError, ImportError):
                pass

            # Simulated fallback
            import secrets as _secrets
            payment_intent = f"pi_simulated_{_secrets.token_hex(8)}"

            db.execute(
                "UPDATE invoices SET status='paid', paid_at=%s, payment_method='stripe', stripe_payment_intent_id=%s WHERE id=%s",
                (now, payment_intent, invoice_id),
            )

            return {
                "invoice_id": invoice_id,
                "status": "paid",
                "paid_at": now,
                "payment_intent": payment_intent,
                "provider": "simulated",
                "amount": amount,
                "message": "Payment processed (simulated — no provider configured)",
            }

    # -- Payment Reminders --

    @staticmethod
    def send_payment_reminders() -> list:
        """Send payment reminders for unpaid invoices older than 7 days.
        Returns list of reminders sent."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        reminder_threshold = (now - timedelta(days=7)).isoformat()
        second_reminder = (now - timedelta(days=14)).isoformat()
        final_reminder = (now - timedelta(days=21)).isoformat()

        reminders_sent = []

        with get_db() as db:
            # Find unpaid invoices older than 7 days
            db.execute(
                """SELECT i.*, a.name as agency_name, a.email as agency_email, a.billing_mode
                   FROM invoices i
                   JOIN agencies a ON i.agency_id = a.id
                   WHERE i.status = 'pending' AND i.created_at <= %s
                   ORDER BY i.created_at ASC""",
                (reminder_threshold,),
            )
            unpaid = db.fetchall()

            for row in unpaid:
                inv = dict(row)
                reminder_count = inv.get("reminder_count") or 0
                last_reminder = inv.get("reminder_sent_at")

                # Determine if we should send a reminder
                should_remind = False
                if reminder_count == 0:
                    should_remind = True
                elif reminder_count == 1 and inv["created_at"] <= second_reminder:
                    should_remind = True
                elif reminder_count == 2 and inv["created_at"] <= final_reminder:
                    should_remind = True

                # Don't send more than 3 reminders
                if reminder_count >= 3:
                    should_remind = False

                # Don't re-send within 3 days
                if last_reminder:
                    try:
                        last_dt = datetime.fromisoformat(last_reminder)
                        if (now - last_dt).days < 3:
                            should_remind = False
                    except (ValueError, TypeError):
                        pass

                if should_remind:
                    amount = inv.get("adjusted_amount") or inv["sell_amount"]
                    urgency = "Reminder" if reminder_count == 0 else (
                        "Second Reminder" if reminder_count == 1 else "Final Notice"
                    )

                    from app.services.email_service import EmailService
                    EmailService.send_payment_reminder(
                        inv["agency_email"], inv["agency_name"],
                        inv["id"], amount, inv.get("description", "Invoice"),
                        urgency,
                    )

                    db.execute(
                        "UPDATE invoices SET reminder_count = reminder_count + 1, reminder_sent_at=%s WHERE id=%s",
                        (now_str, inv["id"]),
                    )

                    reminders_sent.append({
                        "invoice_id": inv["id"],
                        "agency_name": inv["agency_name"],
                        "amount": amount,
                        "reminder_number": reminder_count + 1,
                        "urgency": urgency,
                    })

        return reminders_sent
