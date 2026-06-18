"""
Stripe Billing Reconciliation Service

Nightly job to reconcile Stripe payments against invoices.status,
backfill invite_id on pre-migration invoices, and detect webhook drops.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class BillingReconciliationService:

    @staticmethod
    def reconcile_stripe_payments() -> dict:
        """Compare webhook_events (stripe) vs invoices to catch silent drops.

        Returns a report of mismatches:
        - paid_but_no_webhook: invoices marked paid without a matching webhook
        - webhook_but_unpaid: webhook processed but invoice still unpaid
        - stale_pending: invoices pending for > 24h
        """
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(hours=24)).isoformat()
        report = {
            "run_at": now.isoformat(),
            "paid_but_no_webhook": [],
            "webhook_but_unpaid": [],
            "stale_pending": [],
        }

        with get_db() as db:
            # 1. Invoices marked paid — check for matching Stripe webhook
            db.execute("""
                SELECT i.id, i.agency_id, i.status, i.paid_at,
                       i.stripe_session_id, i.stripe_payment_intent_id
                FROM invoices i
                WHERE i.status = 'paid' AND i.paid_at > %s
            """, (cutoff,))
            paid_invoices = [dict(r) for r in db.fetchall()]

            for inv in paid_invoices:
                session_id = inv.get("stripe_session_id") or ""
                pi_id = inv.get("stripe_payment_intent_id") or ""
                if not session_id and not pi_id:
                    report["paid_but_no_webhook"].append({
                        "invoice_id": inv["id"],
                        "agency_id": inv.get("agency_id"),
                        "issue": "Paid but no Stripe session/PI reference",
                    })
                    continue

                # Look for matching webhook
                db.execute("""
                    SELECT id FROM webhook_events
                    WHERE source='stripe'
                      AND status='processed'
                      AND (payload LIKE %s OR payload LIKE %s)
                    LIMIT 1
                """, (f"%{session_id}%", f"%{pi_id}%"))
                wh = db.fetchone()
                if not wh:
                    report["paid_but_no_webhook"].append({
                        "invoice_id": inv["id"],
                        "agency_id": inv.get("agency_id"),
                        "issue": "No matching webhook event found",
                    })

            # 2. Processed Stripe webhooks — check for unpaid invoices
            db.execute("""
                SELECT id, event_type, payload, created_at
                FROM webhook_events
                WHERE source='stripe'
                  AND event_type='checkout.session.completed'
                  AND status='processed'
                  AND created_at > %s
            """, (cutoff,))
            webhooks = [dict(r) for r in db.fetchall()]

            for wh in webhooks:
                try:
                    p = json.loads(wh["payload"]) if isinstance(wh["payload"], str) else wh["payload"]
                    inv_id = p.get("data", {}).get("object", {}).get("metadata", {}).get("invoice_id")
                    if inv_id:
                        db.execute("SELECT status FROM invoices WHERE id=%s", (inv_id,))
                        inv = db.fetchone()
                        if inv and dict(inv)["status"] != "paid":
                            report["webhook_but_unpaid"].append({
                                "invoice_id": inv_id,
                                "webhook_id": wh["id"],
                                "current_status": dict(inv)["status"],
                            })
                except (json.JSONDecodeError, KeyError):
                    pass

            # 3. Stale pending invoices (> 24h)
            db.execute("""
                SELECT id, agency_id, amount, created_at
                FROM invoices
                WHERE status = 'pending'
                  AND created_at < %s
            """, (cutoff,))
            stale = [dict(r) for r in db.fetchall()]
            report["stale_pending"] = [{
                "invoice_id": s["id"],
                "agency_id": s.get("agency_id"),
                "amount": s.get("amount"),
                "created_at": str(s.get("created_at")),
            } for s in stale]

        report["total_issues"] = (
            len(report["paid_but_no_webhook"])
            + len(report["webhook_but_unpaid"])
            + len(report["stale_pending"])
        )

        # Log the report
        if report["total_issues"] > 0:
            logger.warning("Billing reconciliation found %d issues", report["total_issues"])
            # Write to audit trail
            try:
                with get_db() as db:
                    db.execute(
                        """INSERT INTO audit_trail (id, action, entity_type, entity_id,
                           actor, details, created_at)
                           VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                        (generate_id(), "billing_reconciliation", "system", "nightly",
                         "system:reconciliation", json.dumps(report, default=str),
                         now.isoformat()),
                    )
            except Exception as e:
                logger.error("Failed to log reconciliation to audit trail: %s", e)
        else:
            logger.info("Billing reconciliation: no issues found")

        return report

    @staticmethod
    def backfill_invoice_invite_ids() -> dict:
        """Backfill invite_id on pre-migration invoices.

        Matches invoices to invites by (agency_id, candidate_id, check_type, created_at).
        """
        fixed = 0
        skipped = 0

        with get_db() as db:
            db.execute("""
                SELECT i.id, i.agency_id, i.candidate_id, i.check_type, i.created_at
                FROM invoices i
                WHERE i.invite_id IS NULL
                  AND i.candidate_id IS NOT NULL
                  AND i.agency_id IS NOT NULL
            """)
            orphan_invoices = [dict(r) for r in db.fetchall()]

            for inv in orphan_invoices:
                db.execute("""
                    SELECT id FROM candidate_invites
                    WHERE agency_id = %s
                      AND candidate_id = %s
                    ORDER BY ABS(EXTRACT(EPOCH FROM (created_at::timestamp - %s::timestamp)))
                    LIMIT 1
                """, (inv["agency_id"], inv["candidate_id"], inv["created_at"]))
                match = db.fetchone()
                if match:
                    db.execute(
                        "UPDATE invoices SET invite_id = %s WHERE id = %s",
                        (dict(match)["id"], inv["id"]),
                    )
                    fixed += 1
                else:
                    skipped += 1

        logger.info("Backfill complete: %d fixed, %d skipped", fixed, skipped)
        return {"fixed": fixed, "skipped": skipped, "total_orphans": fixed + skipped}
