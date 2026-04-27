"""
Background task definitions for Celery workers.

Each function can be called directly (synchronous fallback) or dispatched
via Celery when Redis is available. The dispatch_task() helper in
celery_app.py handles this transparently.
"""
import json
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def run_compliance_evaluation(candidate_id: str) -> dict:
    """Re-evaluate compliance for a single candidate."""
    from app.services.compliance_engine import ComplianceEngine

    logger.info("Running compliance evaluation for candidate %s", candidate_id)
    result = ComplianceEngine.evaluate_candidate(candidate_id)
    return {"candidate_id": candidate_id, "result": result}


def run_all_monitoring_checks() -> dict:
    """Run all monitoring checks (DBS renewals, visa expiries, registration, training)."""
    from app.services.monitoring import MonitoringService
    from app.services.email_service import EmailService

    logger.info("Running all monitoring checks...")
    results = MonitoringService.run_all_checks()
    total_alerts = sum(len(v) for v in results.values())
    if total_alerts > 0:
        EmailService.send_monitoring_summary(results)
    logger.info("Monitoring complete: %d alerts", total_alerts)
    return {"total_alerts": total_alerts}


def run_expiry_warning_checks() -> dict:
    """Check for upcoming expiries and queue warning notifications."""
    from app.services.scheduler import run_expiry_warnings

    logger.info("Running expiry warning checks...")
    run_expiry_warnings()
    return {"status": "completed"}


def run_fraud_detection_scan() -> dict:
    """Run cross-candidate fraud detection."""
    from app.services.fraud_detection import FraudDetectionService

    logger.info("Running fraud detection scan...")
    results = FraudDetectionService.run_full_scan()
    return {"total_flags": results.get("total_flags", 0)}


def send_payment_reminders_task() -> dict:
    """Send payment reminders for overdue invoices."""
    from app.services.billing import BillingService

    logger.info("Sending payment reminders...")
    reminders = BillingService.send_payment_reminders()
    return {"reminders_sent": len(reminders) if reminders else 0}


def deliver_webhook(subscription_id: str, event_type: str, payload: dict) -> dict:
    """Deliver a webhook to a subscriber with retry logic."""
    import hashlib
    import hmac
    import urllib.request
    import urllib.error

    from app.database import get_db
    from app.utils.auth import generate_id

    now = datetime.now(timezone.utc).isoformat()
    delivery_id = generate_id()

    with get_db() as db:
        db.execute(
            "SELECT * FROM webhook_subscriptions WHERE id=%s AND is_active=1",
            (subscription_id,),
        )
        sub = db.fetchone()
        if not sub:
            return {"delivery_id": delivery_id, "status": "subscription_inactive"}

        sub_dict = dict(sub)
        payload_bytes = json.dumps(payload).encode("utf-8")

        # Generate HMAC signature
        signature = hmac.new(
            sub_dict["secret"].encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Content-Type": "application/json",
            "X-ViperAI-Signature": f"sha256={signature}",
            "X-ViperAI-Event": event_type,
            "X-ViperAI-Delivery": delivery_id,
        }

        try:
            req = urllib.request.Request(
                sub_dict["url"],
                data=payload_bytes,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                response_status = resp.status
                response_body = resp.read().decode("utf-8")[:1000]

            db.execute(
                """INSERT INTO webhook_deliveries
                   (id, subscription_id, event_type, payload, response_status,
                    response_body, attempt, status, created_at, delivered_at)
                   VALUES (%s, %s, %s, %s, %s, %s, 1, 'delivered', %s, %s)""",
                (delivery_id, subscription_id, event_type, json.dumps(payload),
                 response_status, response_body, now, now),
            )

            # Reset failure count on success
            db.execute(
                "UPDATE webhook_subscriptions SET failure_count=0, last_triggered_at=%s WHERE id=%s",
                (now, subscription_id),
            )

            return {"delivery_id": delivery_id, "status": "delivered", "response_status": response_status}

        except Exception as e:
            error_msg = str(e)[:500]
            db.execute(
                """INSERT INTO webhook_deliveries
                   (id, subscription_id, event_type, payload, response_body,
                    attempt, status, created_at)
                   VALUES (%s, %s, %s, %s, %s, 1, 'failed', %s)""",
                (delivery_id, subscription_id, event_type, json.dumps(payload),
                 error_msg, now),
            )

            # Increment failure count; disable after 10 consecutive failures
            db.execute(
                "UPDATE webhook_subscriptions SET failure_count=failure_count+1 WHERE id=%s",
                (subscription_id,),
            )
            db.execute(
                "SELECT failure_count FROM webhook_subscriptions WHERE id=%s",
                (subscription_id,),
            )
            failure_count = db.fetchone()
            if failure_count and dict(failure_count)["failure_count"] >= 10:
                db.execute(
                    "UPDATE webhook_subscriptions SET is_active=0 WHERE id=%s",
                    (subscription_id,),
                )
                logger.warning("Webhook subscription %s disabled after 10 failures", subscription_id)

            return {"delivery_id": delivery_id, "status": "failed", "error": error_msg}


def apply_retention_policies() -> dict:
    """Apply data retention policies — anonymise/delete data past retention period."""
    from app.database import get_db
    from app.utils.auth import generate_id

    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    deleted_count = 0

    with get_db() as db:
        db.execute(
            "SELECT * FROM gdpr_retention_policies WHERE auto_delete=1",
        )
        policies = db.fetchall()

        for policy in policies:
            p = dict(policy)
            days = p["retention_period_days"]
            category = p["data_category"]

            # Map categories to tables and date columns
            category_map = {
                "draft_data": ("candidate_draft_data", "updated_at"),
                "webhook_events": ("webhook_events", "created_at"),
                "email_notifications": ("email_notifications", "created_at"),
                "background_tasks": ("background_tasks", "created_at"),
            }

            if category in category_map:
                table, date_col = category_map[category]
                result = db.execute(
                    f"DELETE FROM {table} WHERE {date_col}::timestamp < NOW() - INTERVAL '{days} days'",
                )
                deleted_count += result.rowcount

        # Log retention run
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'system', 'retention', 'retention_policy_applied', 'system', %s, %s)""",
            (generate_id(), json.dumps({"deleted_records": deleted_count}), now_iso),
        )

    logger.info("Retention policies applied: %d records deleted", deleted_count)
    return {"deleted_count": deleted_count}
