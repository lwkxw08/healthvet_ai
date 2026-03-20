"""Webhook handlers for external service callbacks."""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, Request
from app.database import get_db
from app.utils.auth import generate_id
from app.services.compliance_engine import ComplianceEngine

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


@router.get("/events")
async def list_webhook_events(limit: int = 50):
    """List recent webhook events for debugging."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM webhook_events ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
