"""SMS notification management routes."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.utils.auth import get_current_user
from app.services.sms_service import SMSService

router = APIRouter(prefix="/api/sms", tags=["SMS Notifications"])


class SendSMSRequest(BaseModel):
    to_number: str
    message: str
    category: str = "general"
    reference_id: Optional[str] = None


@router.get("/config")
async def get_sms_config(current_user: dict = Depends(get_current_user)):
    """Get SMS configuration status."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return SMSService.get_config()


@router.post("/send")
async def send_sms(data: SendSMSRequest, current_user: dict = Depends(get_current_user)):
    """Send an SMS notification (admin only)."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    result = SMSService.send_sms(
        to_number=data.to_number,
        message=data.message,
        user_id=current_user["sub"],
        user_type="admin",
        category=data.category,
        reference_id=data.reference_id,
    )
    return result


@router.get("/history")
async def get_sms_history(
    limit: int = 50,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Get SMS notification history (admin only)."""
    if current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    history = SMSService.get_sms_history(limit=limit, offset=offset)
    return {"sms_notifications": history, "total": len(history)}
