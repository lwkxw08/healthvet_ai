"""REST API + Webhook integrations for agency HR systems.

Provides:
- API key management (create, list, revoke)
- Webhook subscription management (subscribe, list, delete, test)
- Public API endpoints authenticated via API key
- Webhook event dispatching with HMAC signatures
"""
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.database import get_db
from app.utils.auth import (
    generate_id,
    get_current_admin,
    get_current_user,
    hash_password,
)

router = APIRouter(prefix="/api/integrations", tags=["Integrations"])


# ── Schemas ─────────────────────────────────────────────────────────────────

class CreateAPIKeyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    scopes: list[str] = Field(
        default=["candidates:read", "compliance:read"],
        description="Permission scopes for this key",
    )


class CreateWebhookRequest(BaseModel):
    url: str = Field(..., min_length=10, max_length=2000)
    events: list[str] = Field(
        ...,
        description="Event types to subscribe to",
    )


class WebhookTestRequest(BaseModel):
    subscription_id: str


VALID_SCOPES = [
    "candidates:read",
    "candidates:write",
    "compliance:read",
    "checks:read",
    "invoices:read",
    "invoices:write",
    "webhooks:manage",
]

VALID_WEBHOOK_EVENTS = [
    "check.completed",
    "check.failed",
    "candidate.status_changed",
    "candidate.compliance_updated",
    "invoice.created",
    "invoice.paid",
    "invoice.overdue",
    "expiry.warning",
    "monitoring.alert",
]


# ── API Key Authentication Dependency ───────────────────────────────────────

def get_api_key_user(request: Request) -> dict:
    """Authenticate a request using an API key in the X-API-Key header."""
    api_key = request.headers.get("X-API-Key")
    if not api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")

    # Extract prefix for lookup (first 8 chars)
    if len(api_key) < 8:
        raise HTTPException(status_code=401, detail="Invalid API key format")
    prefix = api_key[:8]

    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM api_keys WHERE key_prefix=%s AND is_active=1",
            (prefix,),
        )
        rows = db.fetchall()

        for row in rows:
            key_record = dict(row)
            # Verify full key hash
            key_hash = hashlib.sha256(api_key.encode("utf-8")).hexdigest()
            if key_hash == key_record["key_hash"]:
                # Check expiry
                if key_record.get("expires_at"):
                    expiry = datetime.fromisoformat(key_record["expires_at"])
                    if expiry < datetime.now(timezone.utc):
                        raise HTTPException(status_code=401, detail="API key expired")

                # Update last used
                now = datetime.now(timezone.utc).isoformat()
                db.execute(
                    "UPDATE api_keys SET last_used_at=%s WHERE id=%s",
                    (now, key_record["id"]),
                )

                return {
                    "sub": key_record["agency_id"],
                    "type": "api_key",
                    "key_id": key_record["id"],
                    "scopes": json.loads(key_record.get("scopes", "[]")),
                }

    raise HTTPException(status_code=401, detail="Invalid API key")


def require_scope(scope: str):
    """Dependency factory that checks for a specific scope on the API key."""
    def checker(api_user: dict = Depends(get_api_key_user)):
        if scope not in api_user.get("scopes", []):
            raise HTTPException(
                status_code=403,
                detail=f"API key missing required scope: {scope}",
            )
        return api_user
    return checker


# ── API Key Management ──────────────────────────────────────────────────────

@router.post("/api-keys")
async def create_api_key(
    data: CreateAPIKeyRequest,
    current_user: dict = Depends(get_current_user),
):
    """Create a new API key for the authenticated agency or admin."""
    user_type = current_user.get("type")
    if user_type not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Only agencies and admins can create API keys")

    # Validate scopes
    for scope in data.scopes:
        if scope not in VALID_SCOPES:
            raise HTTPException(status_code=400, detail=f"Invalid scope: {scope}. Valid: {VALID_SCOPES}")

    agency_id = current_user["sub"]
    raw_key = f"hv_{secrets.token_hex(32)}"
    key_prefix = raw_key[:8]
    key_hash = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    key_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        # Limit to 5 active keys per agency
        db.execute(
            "SELECT COUNT(*) AS cnt FROM api_keys WHERE agency_id=%s AND is_active=1",
            (agency_id,),
        )["cnt"]
        count = db.fetchone()
        if count >= 5:
            raise HTTPException(status_code=400, detail="Maximum 5 active API keys per agency")

        db.execute(
            """INSERT INTO api_keys
               (id, agency_id, key_hash, key_prefix, name, scopes, is_active, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, 1, %s)""",
            (key_id, agency_id, key_hash, key_prefix, data.name,
             json.dumps(data.scopes), now),
        )

    return {
        "key_id": key_id,
        "api_key": raw_key,
        "prefix": key_prefix,
        "name": data.name,
        "scopes": data.scopes,
        "message": "Store this key securely — it will not be shown again.",
    }


@router.get("/api-keys")
async def list_api_keys(current_user: dict = Depends(get_current_user)):
    """List all API keys for the authenticated agency (key values are masked)."""
    user_type = current_user.get("type")
    if user_type not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Only agencies and admins can view API keys")

    agency_id = current_user["sub"]

    with get_db() as db:
        if user_type == "admin":
            rows = db.execute(
                "SELECT id, agency_id, key_prefix, name, scopes, is_active, last_used_at, created_at FROM api_keys ORDER BY created_at DESC",
            )
            rows = db.fetchall()
        else:
            rows = db.execute(
                "SELECT id, agency_id, key_prefix, name, scopes, is_active, last_used_at, created_at FROM api_keys WHERE agency_id=%s ORDER BY created_at DESC",
                (agency_id,),
            )
            rows = db.fetchall()

        return [dict(r) for r in rows]


@router.delete("/api-keys/{key_id}")
async def revoke_api_key(
    key_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Revoke an API key."""
    user_type = current_user.get("type")
    agency_id = current_user["sub"]

    with get_db() as db:
        if user_type == "admin":
            db.execute("SELECT id FROM api_keys WHERE id=%s", (key_id,))
            existing = db.fetchone()
        else:
            existing = db.execute(
                "SELECT id FROM api_keys WHERE id=%s AND agency_id=%s",
                (key_id, agency_id),
            )
            existing = db.fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="API key not found")

        db.execute("UPDATE api_keys SET is_active=0 WHERE id=%s", (key_id,))

    return {"revoked": True, "key_id": key_id}


# ── Webhook Subscription Management ────────────────────────────────────────

@router.post("/webhooks")
async def create_webhook_subscription(
    data: CreateWebhookRequest,
    current_user: dict = Depends(get_current_user),
):
    """Subscribe to webhook events."""
    user_type = current_user.get("type")
    if user_type not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Only agencies and admins can create webhooks")

    for event in data.events:
        if event not in VALID_WEBHOOK_EVENTS:
            raise HTTPException(status_code=400, detail=f"Invalid event: {event}. Valid: {VALID_WEBHOOK_EVENTS}")

    agency_id = current_user["sub"]
    webhook_secret = f"whsec_{secrets.token_hex(24)}"
    sub_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        # Limit to 10 webhooks per agency
        db.execute(
            "SELECT COUNT(*) AS cnt FROM webhook_subscriptions WHERE agency_id=%s AND is_active=1",
            (agency_id,),
        )["cnt"]
        count = db.fetchone()
        if count >= 10:
            raise HTTPException(status_code=400, detail="Maximum 10 active webhook subscriptions per agency")

        db.execute(
            """INSERT INTO webhook_subscriptions
               (id, agency_id, url, secret, events, is_active, created_at)
               VALUES (%s, %s, %s, %s, %s, 1, %s)""",
            (sub_id, agency_id, data.url, webhook_secret,
             json.dumps(data.events), now),
        )

    return {
        "subscription_id": sub_id,
        "url": data.url,
        "events": data.events,
        "secret": webhook_secret,
        "message": "Store this secret securely — use it to verify webhook signatures.",
    }


@router.get("/webhooks")
async def list_webhook_subscriptions(current_user: dict = Depends(get_current_user)):
    """List webhook subscriptions."""
    user_type = current_user.get("type")
    if user_type not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Only agencies and admins can view webhooks")

    agency_id = current_user["sub"]

    with get_db() as db:
        if user_type == "admin":
            rows = db.execute(
                "SELECT id, agency_id, url, events, is_active, failure_count, last_triggered_at, created_at FROM webhook_subscriptions ORDER BY created_at DESC",
            )
            rows = db.fetchall()
        else:
            rows = db.execute(
                "SELECT id, agency_id, url, events, is_active, failure_count, last_triggered_at, created_at FROM webhook_subscriptions WHERE agency_id=%s ORDER BY created_at DESC",
                (agency_id,),
            )
            rows = db.fetchall()

        return [dict(r) for r in rows]


@router.delete("/webhooks/{subscription_id}")
async def delete_webhook_subscription(
    subscription_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a webhook subscription."""
    user_type = current_user.get("type")
    agency_id = current_user["sub"]

    with get_db() as db:
        if user_type == "admin":
            db.execute("SELECT id FROM webhook_subscriptions WHERE id=%s", (subscription_id,))
            existing = db.fetchone()
        else:
            existing = db.execute(
                "SELECT id FROM webhook_subscriptions WHERE id=%s AND agency_id=%s",
                (subscription_id, agency_id),
            )
            existing = db.fetchone()

        if not existing:
            raise HTTPException(status_code=404, detail="Webhook subscription not found")

        db.execute("UPDATE webhook_subscriptions SET is_active=0 WHERE id=%s", (subscription_id,))

    return {"deleted": True, "subscription_id": subscription_id}


@router.post("/webhooks/test")
async def test_webhook(
    data: WebhookTestRequest,
    current_user: dict = Depends(get_current_user),
):
    """Send a test event to a webhook subscription."""
    from app.services.tasks import deliver_webhook

    test_payload = {
        "event": "test.ping",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": {"message": "This is a test webhook from HealthVet AI"},
    }

    result = deliver_webhook(data.subscription_id, "test.ping", test_payload)
    return result


@router.get("/webhooks/{subscription_id}/deliveries")
async def list_webhook_deliveries(
    subscription_id: str,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """List recent deliveries for a webhook subscription."""
    with get_db() as db:
        rows = db.execute(
            """SELECT id, event_type, response_status, attempt, status, created_at, delivered_at
               FROM webhook_deliveries WHERE subscription_id=%s
               ORDER BY created_at DESC LIMIT %s""",
            (subscription_id, limit),
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


# ── Public API Endpoints (API Key Auth) ─────────────────────────────────────

@router.get("/v1/candidates")
async def api_list_candidates(
    api_user: dict = Depends(require_scope("candidates:read")),
):
    """List candidates for the agency (API key authenticated)."""
    agency_id = api_user["sub"]

    with get_db() as db:
        rows = db.execute(
            """SELECT c.id, c.email, c.first_name, c.last_name, c.profession,
                      c.status, c.compliance_score, c.compliance_status, c.created_at,
                      ac.employment_status
               FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               WHERE ac.agency_id=%s
               ORDER BY c.created_at DESC""",
            (agency_id,),
        )
        rows = db.fetchall()
        return {"candidates": [dict(r) for r in rows], "total": len(rows)}


@router.get("/v1/candidates/{candidate_id}")
async def api_get_candidate(
    candidate_id: str,
    api_user: dict = Depends(require_scope("candidates:read")),
):
    """Get candidate details (API key authenticated)."""
    agency_id = api_user["sub"]

    with get_db() as db:
        # Verify agency owns candidate
        link = db.execute(
            "SELECT 1 FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
            (agency_id, candidate_id),
        )
        link = db.fetchone()
        if not link:
            raise HTTPException(status_code=404, detail="Candidate not found")

        candidate = db.execute(
            """SELECT id, email, first_name, last_name, phone, profession,
                      registration_number, registration_body, status,
                      compliance_score, compliance_status, created_at
               FROM candidates WHERE id=%s""",
            (candidate_id,),
        )
        candidate = db.fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        return dict(candidate)


@router.get("/v1/candidates/{candidate_id}/compliance")
async def api_get_compliance(
    candidate_id: str,
    api_user: dict = Depends(require_scope("compliance:read")),
):
    """Get compliance status for a candidate (API key authenticated)."""
    agency_id = api_user["sub"]

    with get_db() as db:
        link = db.execute(
            "SELECT 1 FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
            (agency_id, candidate_id),
        )
        link = db.fetchone()
        if not link:
            raise HTTPException(status_code=404, detail="Candidate not found")

        compliance = db.execute(
            "SELECT * FROM compliance_records WHERE candidate_id=%s ORDER BY last_evaluated DESC LIMIT 1",
            (candidate_id,),
        )
        compliance = db.fetchone()
        if not compliance:
            return {"candidate_id": candidate_id, "status": "not_evaluated"}

        return dict(compliance)


@router.get("/v1/candidates/{candidate_id}/checks")
async def api_get_checks(
    candidate_id: str,
    api_user: dict = Depends(require_scope("checks:read")),
):
    """Get all check results for a candidate (API key authenticated)."""
    agency_id = api_user["sub"]

    with get_db() as db:
        link = db.execute(
            "SELECT 1 FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
            (agency_id, candidate_id),
        )
        link = db.fetchone()
        if not link:
            raise HTTPException(status_code=404, detail="Candidate not found")

        identity = db.execute(
            "SELECT id, status, result, started_at, completed_at FROM identity_checks WHERE candidate_id=%s",
            (candidate_id,),
        )
        identity = db.fetchall()
        rtw = db.execute(
            "SELECT id, status, verified, verification_method, checked_at FROM right_to_work_checks WHERE candidate_id=%s",
            (candidate_id,),
        )
        rtw = db.fetchall()
        dbs = db.execute(
            "SELECT id, status, check_type, certificate_number, result, submitted_at, completed_at FROM dbs_checks WHERE candidate_id=%s",
            (candidate_id,),
        )
        dbs = db.fetchall()
        reg = db.execute(
            "SELECT id, body, status, is_active, last_checked FROM registration_checks WHERE candidate_id=%s",
            (candidate_id,),
        )
        reg = db.fetchall()

        return {
            "candidate_id": candidate_id,
            "identity_checks": [dict(r) for r in identity],
            "right_to_work_checks": [dict(r) for r in rtw],
            "dbs_checks": [dict(r) for r in dbs],
            "registration_checks": [dict(r) for r in reg],
        }


@router.get("/v1/invoices")
async def api_list_invoices(
    api_user: dict = Depends(require_scope("invoices:read")),
):
    """List invoices for the agency (API key authenticated)."""
    agency_id = api_user["sub"]

    with get_db() as db:
        rows = db.execute(
            """SELECT id, candidate_id, check_type, description, cost_amount,
                      sell_amount, status, created_at, paid_at
               FROM invoices WHERE agency_id=%s
               ORDER BY created_at DESC""",
            (agency_id,),
        )
        rows = db.fetchall()
        return {"invoices": [dict(r) for r in rows], "total": len(rows)}


# ── Webhook Event Dispatcher (called from other routes) ─────────────────────

def dispatch_webhook_event(agency_id: str, event_type: str, data: dict):
    """Dispatch a webhook event to all subscribed endpoints for an agency.

    Call this from any route handler when a notable event occurs.
    Example: dispatch_webhook_event(agency_id, "check.completed", {"candidate_id": "...", ...})
    """
    from app.services.celery_app import dispatch_task

    now = datetime.now(timezone.utc).isoformat()
    payload = {
        "event": event_type,
        "timestamp": now,
        "data": data,
    }

    with get_db() as db:
        subs = db.execute(
            "SELECT id, events FROM webhook_subscriptions WHERE agency_id=%s AND is_active=1",
            (agency_id,),
        )
        subs = db.fetchall()

        dispatched = 0
        for sub in subs:
            sub_dict = dict(sub)
            subscribed_events = json.loads(sub_dict.get("events", "[]"))
            if event_type in subscribed_events or "*" in subscribed_events:
                dispatch_task(
                    "app.services.tasks.deliver_webhook",
                    sub_dict["id"],
                    event_type,
                    payload,
                )
                dispatched += 1

    return dispatched
