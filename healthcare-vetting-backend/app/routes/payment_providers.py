"""
Payment Provider Configuration Routes
Admin endpoints for connecting Stripe/GoCardless, managing routing, and viewing transactions.
"""
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.utils.auth import get_current_user
from app.services.payment_providers import PaymentProviderService

router = APIRouter(prefix="/api/admin/payment-providers", tags=["Payment Providers"])


def require_admin(current_user: dict):
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


# ── Schemas ───────────────────────────────────────────────────────────

class ConnectProviderRequest(BaseModel):
    provider: str  # "stripe" or "gocardless"
    api_key: str
    api_secret: Optional[str] = ""
    webhook_secret: Optional[str] = ""
    environment: Optional[str] = "live"  # "live" or "sandbox"


class UpdateRoutingRequest(BaseModel):
    payment_type: str
    provider: Optional[str] = None
    fallback_provider: Optional[str] = None


class CreateCheckoutRequest(BaseModel):
    agency_id: str
    invoice_id: str
    amount: float
    payment_type: str  # e.g. "credit_pack_purchase", "payg_invoice"
    description: str
    success_url: str
    cancel_url: str
    currency: Optional[str] = "GBP"


class ConfirmPaymentRequest(BaseModel):
    provider: str
    provider_payment_id: str


class RefundRequest(BaseModel):
    transaction_id: str
    amount: Optional[float] = None


# ── Provider Configuration ────────────────────────────────────────────

@router.get("")
async def list_providers(current_user: dict = Depends(get_current_user)):
    """Get all payment providers with their config (keys masked)."""
    require_admin(current_user)
    return PaymentProviderService.get_providers()


@router.post("/connect")
async def connect_provider(data: ConnectProviderRequest, current_user: dict = Depends(get_current_user)):
    """Connect a payment provider by entering API credentials. Tests connectivity automatically."""
    require_admin(current_user)
    try:
        result = PaymentProviderService.connect_provider(
            provider=data.provider,
            api_key=data.api_key,
            api_secret=data.api_secret or "",
            webhook_secret=data.webhook_secret or "",
            environment=data.environment or "live",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/disconnect/{provider}")
async def disconnect_provider(provider: str, current_user: dict = Depends(get_current_user)):
    """Disconnect a payment provider (removes credentials and routing)."""
    require_admin(current_user)
    return PaymentProviderService.disconnect_provider(provider)


@router.post("/test/{provider}")
async def test_provider(provider: str, current_user: dict = Depends(get_current_user)):
    """Test connectivity to an already-connected provider."""
    require_admin(current_user)
    return PaymentProviderService.test_provider(provider)


# ── Payment Routing ───────────────────────────────────────────────────

@router.get("/routing")
async def get_routing(current_user: dict = Depends(get_current_user)):
    """Get all payment routing rules (which provider handles what)."""
    require_admin(current_user)
    return PaymentProviderService.get_routing()


@router.put("/routing")
async def update_routing(data: UpdateRoutingRequest, current_user: dict = Depends(get_current_user)):
    """Update which provider handles a specific payment type."""
    require_admin(current_user)
    try:
        return PaymentProviderService.update_routing(
            payment_type=data.payment_type,
            provider=data.provider,
            fallback_provider=data.fallback_provider,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Payment Processing ────────────────────────────────────────────────

@router.post("/checkout")
async def create_checkout(data: CreateCheckoutRequest, current_user: dict = Depends(get_current_user)):
    """Create a payment checkout session using the configured provider."""
    require_admin(current_user)
    try:
        return PaymentProviderService.create_checkout(
            agency_id=data.agency_id,
            invoice_id=data.invoice_id,
            amount=data.amount,
            payment_type=data.payment_type,
            description=data.description,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
            currency=data.currency or "GBP",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/confirm")
async def confirm_payment(data: ConfirmPaymentRequest, current_user: dict = Depends(get_current_user)):
    """Confirm a payment has been completed."""
    require_admin(current_user)
    return PaymentProviderService.confirm_payment(
        provider=data.provider,
        provider_payment_id=data.provider_payment_id,
    )


@router.post("/refund")
async def process_refund(data: RefundRequest, current_user: dict = Depends(get_current_user)):
    """Process a refund for a completed payment."""
    require_admin(current_user)
    try:
        return PaymentProviderService.process_refund(
            transaction_id=data.transaction_id,
            amount=data.amount,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ── Transaction History ───────────────────────────────────────────────

@router.get("/transactions")
async def list_transactions(
    agency_id: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    """Get payment transaction history."""
    require_admin(current_user)
    return PaymentProviderService.get_transactions(agency_id=agency_id, limit=limit)
