"""
3.3 Webhook Reliability & Retry API Routes

Delivery dashboard, retry management, event replay,
failed delivery alerting, and pending retry processing.
"""
from fastapi import APIRouter, Depends, HTTPException

from app.utils.auth import get_current_user, get_current_admin

router = APIRouter(prefix="/api/webhook-management", tags=["Webhook Management"])


@router.get("/dashboard")
async def get_delivery_dashboard(agency_id: str = None, limit: int = 100,
                                  user=Depends(get_current_user)):
    """Get webhook delivery status dashboard."""
    from app.services.webhook_reliability import WebhookReliabilityService
    real_id = user["sub"] if agency_id == "me" else agency_id
    return WebhookReliabilityService.get_delivery_dashboard(real_id, limit)


@router.get("/failed")
async def get_failed_deliveries(limit: int = 50, user=Depends(get_current_admin)):
    """Get failed webhook deliveries for alerting (admin only)."""
    from app.services.webhook_reliability import WebhookReliabilityService
    return WebhookReliabilityService.get_failed_deliveries(limit)


@router.post("/retry/{delivery_id}")
async def retry_delivery(delivery_id: str, user=Depends(get_current_admin)):
    """Manually retry a failed webhook delivery (admin only)."""
    from app.services.webhook_reliability import WebhookReliabilityService
    result = WebhookReliabilityService.retry_delivery(delivery_id, 0)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Delivery not found")
    return result


@router.post("/replay/{delivery_id}")
async def replay_event(delivery_id: str, user=Depends(get_current_admin)):
    """Replay a webhook event (create a new delivery with same payload, admin only)."""
    from app.services.webhook_reliability import WebhookReliabilityService
    result = WebhookReliabilityService.replay_event(delivery_id)
    if result.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Delivery not found")
    return result


@router.post("/process-retries")
async def process_pending_retries(user=Depends(get_current_admin)):
    """Process all pending webhook retries that are due (admin only)."""
    from app.services.webhook_reliability import WebhookReliabilityService
    return WebhookReliabilityService.process_pending_retries()
