"""Webhook handlers for external service callbacks."""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException
from app.database import get_db
from app.utils.auth import generate_id
from app.services.compliance_engine import ComplianceEngine

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webhooks", tags=["Webhooks"])


@router.post("/onfido")
async def onfido_webhook(request: Request):
    """Handle Onfido identity verification callbacks."""
    payload = await request.json()
    event_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            """INSERT INTO webhook_events (id, source, event_type, payload, status, created_at)
               VALUES (?, 'onfido', ?, ?, 'received', ?)""",
            (event_id, payload.get("event", "unknown"), json.dumps(payload), now),
        )

        # Process the webhook
        check_id = payload.get("check_id")
        if check_id:
            result = payload.get("result", {})
            db.execute(
                """UPDATE identity_checks SET
                   status=?, result=?, details=?, completed_at=?
                   WHERE id=?""",
                (
                    "completed",
                    result.get("result", "unknown"),
                    json.dumps(result),
                    now,
                    check_id,
                ),
            )

            # Get candidate_id and re-evaluate compliance
            check = db.execute("SELECT candidate_id FROM identity_checks WHERE id=?", (check_id,)).fetchone()
            if check:
                ComplianceEngine.evaluate_candidate(dict(check)["candidate_id"])

        db.execute(
            "UPDATE webhook_events SET status='processed', processed_at=? WHERE id=?",
            (now, event_id),
        )

    return {"status": "ok", "event_id": event_id}


@router.post("/dbs-provider")
async def dbs_provider_webhook(request: Request):
    """Handle DBS provider (uCheck/CareCheck) callbacks."""
    payload = await request.json()
    event_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            """INSERT INTO webhook_events (id, source, event_type, payload, status, created_at)
               VALUES (?, 'dbs_provider', ?, ?, 'received', ?)""",
            (event_id, payload.get("event", "status_update"), json.dumps(payload), now),
        )

        application_ref = payload.get("application_ref")
        if application_ref:
            result = payload.get("result", {})
            db.execute(
                """UPDATE dbs_checks SET
                   status=?, certificate_number=?, result=?, details=?, completed_at=?
                   WHERE application_ref=?""",
                (
                    "completed",
                    result.get("certificate_number"),
                    result.get("result", "unknown"),
                    json.dumps(result),
                    now,
                    application_ref,
                ),
            )

            check = db.execute(
                "SELECT candidate_id FROM dbs_checks WHERE application_ref=?",
                (application_ref,),
            ).fetchone()
            if check:
                ComplianceEngine.evaluate_candidate(dict(check)["candidate_id"])

        db.execute(
            "UPDATE webhook_events SET status='processed', processed_at=? WHERE id=?",
            (now, event_id),
        )

    return {"status": "ok", "event_id": event_id}


@router.post("/home-office")
async def home_office_webhook(request: Request):
    """Handle Home Office Right to Work status changes."""
    payload = await request.json()
    event_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            """INSERT INTO webhook_events (id, source, event_type, payload, status, created_at)
               VALUES (?, 'home_office', ?, ?, 'received', ?)""",
            (event_id, payload.get("event", "status_change"), json.dumps(payload), now),
        )

        db.execute(
            "UPDATE webhook_events SET status='processed', processed_at=? WHERE id=?",
            (now, event_id),
        )

    return {"status": "ok", "event_id": event_id}


@router.post("/stripe")
async def stripe_webhook(request: Request):
    """Handle Stripe payment webhooks (checkout.session.completed, payment_intent.succeeded, etc.)."""
    raw_body = await request.body()
    event_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    # Optionally verify Stripe signature
    sig_header = request.headers.get("stripe-signature")
    payload = json.loads(raw_body)
    event_type = payload.get("type", "unknown")

    if sig_header:
        from app.services.payment_providers import PaymentProviderService
        provider_config = PaymentProviderService.get_provider("stripe")
        webhook_secret = (provider_config or {}).get("webhook_secret", "")
        if webhook_secret:
            try:
                import stripe
                stripe.Webhook.construct_event(raw_body, sig_header, webhook_secret)
            except Exception as e:
                logger.warning("Stripe signature verification failed: %s", e)
                raise HTTPException(status_code=400, detail="Invalid Stripe signature")

    with get_db() as db:
        db.execute(
            """INSERT INTO webhook_events (id, source, event_type, payload, status, created_at)
               VALUES (?, 'stripe', ?, ?, 'received', ?)""",
            (event_id, event_type, json.dumps(payload), now),
        )

        data_obj = payload.get("data", {}).get("object", {})

        if event_type == "checkout.session.completed":
            session_id = data_obj.get("id", "")
            payment_intent = data_obj.get("payment_intent", "")
            metadata = data_obj.get("metadata", {})
            invoice_id = metadata.get("invoice_id")
            agency_id = metadata.get("agency_id")

            # Update payment transaction
            db.execute(
                "UPDATE payment_transactions SET status='completed', completed_at=? WHERE provider_payment_id=?",
                (now, session_id),
            )

            # Mark invoice as paid
            if invoice_id:
                db.execute(
                    "UPDATE invoices SET status='paid', paid_at=?, payment_method='stripe', stripe_payment_intent_id=?, stripe_session_id=? WHERE id=?",
                    (now, payment_intent, session_id, invoice_id),
                )

            logger.info("Stripe checkout completed: session=%s invoice=%s", session_id, invoice_id)

        elif event_type == "payment_intent.succeeded":
            pi_id = data_obj.get("id", "")
            db.execute(
                "UPDATE payment_transactions SET status='completed', completed_at=? WHERE provider_payment_id=?",
                (now, pi_id),
            )
            logger.info("Stripe payment_intent succeeded: %s", pi_id)

        elif event_type in ("charge.refunded", "charge.refund.updated"):
            charge_id = data_obj.get("id", "")
            logger.info("Stripe refund event: %s for charge %s", event_type, charge_id)

        elif event_type == "payment_intent.payment_failed":
            pi_id = data_obj.get("id", "")
            db.execute(
                "UPDATE payment_transactions SET status='failed' WHERE provider_payment_id=?",
                (pi_id,),
            )
            logger.warning("Stripe payment failed: %s", pi_id)

        db.execute(
            "UPDATE webhook_events SET status='processed', processed_at=? WHERE id=?",
            (now, event_id),
        )

    return {"status": "ok", "event_id": event_id}


@router.get("/events")
async def list_webhook_events(limit: int = 50):
    """List recent webhook events for debugging."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM webhook_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
