"""
3.3 Webhook Reliability & Retry

Exponential backoff retry for webhook deliveries, HMAC signature
verification, delivery status dashboard, failed delivery alerting,
and webhook event replay capability.
"""
import hashlib
import hmac
import json
import logging
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)

# Retry schedule: delays in seconds (exponential backoff)
RETRY_DELAYS = [60, 300, 900, 3600, 14400, 43200]  # 1m, 5m, 15m, 1h, 4h, 12h
MAX_RETRIES = len(RETRY_DELAYS)


class WebhookReliabilityService:
    """Enhanced webhook delivery with retry, signatures, and monitoring."""

    @staticmethod
    def deliver_with_retry(subscription_id: str, event_type: str, payload: dict,
                           delivery_id: str = None) -> dict:
        """Deliver a webhook with automatic retry on failure."""
        if not delivery_id:
            delivery_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            sub = db.execute(
                "SELECT * FROM webhook_subscriptions WHERE id=%s AND is_active=1",
                (subscription_id,),
            )
            sub = db.fetchone()
            if not sub:
                return {"delivery_id": delivery_id, "status": "subscription_inactive"}

            sub_dict = dict(sub)
            payload_bytes = json.dumps(payload, default=str).encode("utf-8")

            # Generate HMAC-SHA256 signature
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
                "X-ViperAI-Timestamp": now,
                "User-Agent": "ViperAI-Webhooks/1.0",
            }

            # Attempt delivery
            response_status = None
            response_body = None
            error_msg = None
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

                # Success
                db.execute(
                    """INSERT INTO webhook_deliveries
                       (id, subscription_id, event_type, payload, response_status,
                        response_body, attempt, status, next_retry_at, created_at, delivered_at)
                       VALUES (%s, %s, %s, %s, %s, %s, 1, 'delivered', NULL, %s, %s)""",
                    (delivery_id, subscription_id, event_type, json.dumps(payload),
                     response_status, response_body, now, now),
                )
                db.execute(
                    "UPDATE webhook_subscriptions SET failure_count=0, last_triggered_at=%s WHERE id=%s",
                    (now, subscription_id),
                )
                return {"delivery_id": delivery_id, "status": "delivered", "response_status": response_status}

            except Exception as e:
                error_msg = str(e)[:500]
                # Schedule first retry
                next_retry = (datetime.now(timezone.utc) + timedelta(seconds=RETRY_DELAYS[0])).isoformat()

                db.execute(
                    """INSERT INTO webhook_deliveries
                       (id, subscription_id, event_type, payload, response_status,
                        response_body, attempt, status, next_retry_at, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, 1, 'pending_retry', %s, %s)""",
                    (delivery_id, subscription_id, event_type, json.dumps(payload),
                     response_status, error_msg, next_retry, now),
                )
                db.execute(
                    "UPDATE webhook_subscriptions SET failure_count=failure_count+1, last_triggered_at=%s WHERE id=%s",
                    (now, subscription_id),
                )

                # Schedule background retry
                _schedule_retry(delivery_id, 0)

                return {"delivery_id": delivery_id, "status": "pending_retry", "error": error_msg,
                        "next_retry_at": next_retry}

    @staticmethod
    def retry_delivery(delivery_id: str, attempt: int) -> dict:
        """Retry a failed webhook delivery."""
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            delivery = db.execute(
                "SELECT * FROM webhook_deliveries WHERE id=%s", (delivery_id,)
            )
            delivery = db.fetchone()
            if not delivery:
                return {"status": "not_found"}

            d = dict(delivery)
            if d["status"] == "delivered":
                return {"status": "already_delivered"}

            sub = db.execute(
                "SELECT * FROM webhook_subscriptions WHERE id=%s",
                (d["subscription_id"],),
            )
            sub = db.fetchone()
            if not sub:
                db.execute(
                    "UPDATE webhook_deliveries SET status='abandoned', next_retry_at=NULL WHERE id=%s",
                    (delivery_id,),
                )
                return {"status": "subscription_not_found"}

            sub_dict = dict(sub)
            payload = json.loads(d["payload"])
            payload_bytes = json.dumps(payload, default=str).encode("utf-8")

            signature = hmac.new(
                sub_dict["secret"].encode("utf-8"),
                payload_bytes,
                hashlib.sha256,
            ).hexdigest()

            headers = {
                "Content-Type": "application/json",
                "X-ViperAI-Signature": f"sha256={signature}",
                "X-ViperAI-Event": d["event_type"],
                "X-ViperAI-Delivery": delivery_id,
                "X-ViperAI-Timestamp": now,
                "X-ViperAI-Retry": str(attempt + 1),
                "User-Agent": "ViperAI-Webhooks/1.0",
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
                    """UPDATE webhook_deliveries SET
                       response_status=%s, response_body=%s, attempt=%s,
                       status='delivered', next_retry_at=NULL, delivered_at=%s
                       WHERE id=%s""",
                    (response_status, response_body, attempt + 2, now, delivery_id),
                )
                db.execute(
                    "UPDATE webhook_subscriptions SET failure_count=0 WHERE id=%s",
                    (d["subscription_id"],),
                )
                return {"delivery_id": delivery_id, "status": "delivered", "attempt": attempt + 2}

            except Exception as e:
                error_msg = str(e)[:500]
                next_attempt = attempt + 1

                if next_attempt >= MAX_RETRIES:
                    # Max retries reached — mark as failed
                    db.execute(
                        """UPDATE webhook_deliveries SET
                           response_body=%s, attempt=%s, status='failed', next_retry_at=NULL
                           WHERE id=%s""",
                        (error_msg, next_attempt + 1, delivery_id),
                    )
                    # Increment failure count; disable subscription after 10 consecutive failures
                    db.execute(
                        "UPDATE webhook_subscriptions SET failure_count=failure_count+1 WHERE id=%s",
                        (d["subscription_id"],),
                    )
                    fc = db.execute(
                        "SELECT failure_count FROM webhook_subscriptions WHERE id=%s",
                        (d["subscription_id"],),
                    )
                    fc = db.fetchone()
                    if fc and dict(fc)["failure_count"] >= 10:
                        db.execute(
                            "UPDATE webhook_subscriptions SET is_active=0 WHERE id=%s",
                            (d["subscription_id"],),
                        )
                        logger.warning("Webhook subscription %s disabled after 10 failures", d["subscription_id"])

                    return {"delivery_id": delivery_id, "status": "failed", "attempt": next_attempt + 1}
                else:
                    # Schedule next retry with exponential backoff
                    next_retry = (datetime.now(timezone.utc) + timedelta(seconds=RETRY_DELAYS[next_attempt])).isoformat()
                    db.execute(
                        """UPDATE webhook_deliveries SET
                           response_body=%s, attempt=%s, status='pending_retry', next_retry_at=%s
                           WHERE id=%s""",
                        (error_msg, next_attempt + 1, next_retry, delivery_id),
                    )
                    _schedule_retry(delivery_id, next_attempt)
                    return {"delivery_id": delivery_id, "status": "pending_retry",
                            "attempt": next_attempt + 1, "next_retry_at": next_retry}

    @staticmethod
    def replay_event(delivery_id: str) -> dict:
        """Replay a webhook delivery (create a new delivery with same payload)."""
        with get_db() as db:
            delivery = db.execute(
                "SELECT * FROM webhook_deliveries WHERE id=%s", (delivery_id,)
            )
            delivery = db.fetchone()
            if not delivery:
                return {"status": "not_found"}

            d = dict(delivery)
            new_delivery_id = generate_id()
            payload = json.loads(d["payload"])

            return WebhookReliabilityService.deliver_with_retry(
                d["subscription_id"], d["event_type"], payload, new_delivery_id
            )

    @staticmethod
    def get_delivery_dashboard(agency_id: str = None, limit: int = 100) -> dict:
        """Get webhook delivery status dashboard."""
        with get_db() as db:
            if agency_id:
                deliveries = db.execute(
                    """SELECT wd.*, ws.url, ws.agency_id
                       FROM webhook_deliveries wd
                       JOIN webhook_subscriptions ws ON wd.subscription_id = ws.id
                       WHERE ws.agency_id=%s
                       ORDER BY wd.created_at DESC LIMIT %s""",
                    (agency_id, limit),
                )
                deliveries = db.fetchall()
            else:
                deliveries = db.execute(
                    """SELECT wd.*, ws.url, ws.agency_id
                       FROM webhook_deliveries wd
                       JOIN webhook_subscriptions ws ON wd.subscription_id = ws.id
                       ORDER BY wd.created_at DESC LIMIT %s""",
                    (limit,),
                )
                deliveries = db.fetchall()

            items = [dict(r) for r in deliveries]

            # Stats
            total = len(items)
            delivered = sum(1 for i in items if i.get("status") == "delivered")
            failed = sum(1 for i in items if i.get("status") == "failed")
            pending = sum(1 for i in items if i.get("status") == "pending_retry")

            return {
                "deliveries": items,
                "stats": {
                    "total": total,
                    "delivered": delivered,
                    "failed": failed,
                    "pending_retry": pending,
                    "success_rate": round(delivered / total * 100 if total > 0 else 0, 1),
                },
            }

    @staticmethod
    def get_failed_deliveries(limit: int = 50) -> list:
        """Get failed deliveries for alerting."""
        with get_db() as db:
            rows = db.execute(
                """SELECT wd.*, ws.url, ws.agency_id
                   FROM webhook_deliveries wd
                   JOIN webhook_subscriptions ws ON wd.subscription_id = ws.id
                   WHERE wd.status='failed'
                   ORDER BY wd.created_at DESC LIMIT %s""",
                (limit,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def verify_signature(payload_bytes: bytes, signature_header: str, secret: str) -> bool:
        """Verify an incoming webhook HMAC-SHA256 signature."""
        if not signature_header or not signature_header.startswith("sha256="):
            return False
        expected = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()
        received = signature_header[7:]
        return hmac.compare_digest(expected, received)

    @staticmethod
    def process_pending_retries():
        """Process all deliveries that are due for retry. Called by scheduler."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            due = db.execute(
                "SELECT id, attempt FROM webhook_deliveries WHERE status='pending_retry' AND next_retry_at <= %s",
                (now,),
            )
            due = db.fetchall()

            results = []
            for row in due:
                d = dict(row)
                result = WebhookReliabilityService.retry_delivery(d["id"], d["attempt"] - 1)
                results.append(result)

            return {"processed": len(results), "results": results}


def _schedule_retry(delivery_id: str, attempt_index: int):
    """Schedule a retry in a background thread after the appropriate delay."""
    if attempt_index >= MAX_RETRIES:
        return

    delay = RETRY_DELAYS[attempt_index]

    def _do_retry():
        time.sleep(delay)
        try:
            WebhookReliabilityService.retry_delivery(delivery_id, attempt_index)
        except Exception as e:
            logger.error("Retry failed for delivery %s: %s", delivery_id, e)

    thread = threading.Thread(target=_do_retry, daemon=True)
    thread.start()
