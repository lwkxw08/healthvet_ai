"""
Email Template Management Routes
Admin endpoints for CRUD on email templates, preview, send log, and stats.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.email_templates import EmailTemplateService

router = APIRouter(prefix="/api/admin/email-templates", tags=["Email Templates"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class TemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    subject: str | None = None
    body_html: str | None = None
    body_text: str | None = None
    is_active: bool | None = None


class TestSendRequest(BaseModel):
    template_key: str
    recipient_email: str
    recipient_name: str = "Test Recipient"
    variables: dict = {}


# ── Template CRUD ─────────────────────────────────────────────────────────────

@router.get("")
async def list_templates():
    """List all email templates."""
    templates = EmailTemplateService.get_all_templates()
    return {"templates": templates}


@router.get("/stats")
async def get_email_stats():
    """Get email delivery statistics."""
    stats = EmailTemplateService.get_email_stats()
    return stats


@router.get("/send-log")
async def get_send_log(limit: int = 50, template_key: str = None):
    """Get email send log."""
    log = EmailTemplateService.get_send_log(limit=limit, template_key=template_key)
    return {"log": log}


@router.get("/{template_id}")
async def get_template(template_id: str):
    """Get a single template by ID."""
    tpl = EmailTemplateService.get_template(template_id)
    if not tpl:
        raise HTTPException(status_code=404, detail="Template not found")
    return tpl


@router.put("/{template_id}")
async def update_template(template_id: str, body: TemplateUpdate):
    """Update a template's content."""
    result = EmailTemplateService.update_template(
        template_id,
        name=body.name,
        description=body.description,
        subject=body.subject,
        body_html=body.body_html,
        body_text=body.body_text,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


@router.post("/{template_id}/reset")
async def reset_template(template_id: str):
    """Reset a template to its default content."""
    result = EmailTemplateService.reset_template(template_id)
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


@router.get("/{template_id}/preview")
async def preview_template(template_id: str):
    """Preview a template with sample data."""
    result = EmailTemplateService.preview_template(template_id)
    if not result:
        raise HTTPException(status_code=404, detail="Template not found")
    return result


@router.post("/test-send")
async def test_send_email(body: TestSendRequest):
    """Send a test email using a template."""
    result = EmailTemplateService.send_email(
        template_key=body.template_key,
        recipient_email=body.recipient_email,
        recipient_name=body.recipient_name,
        variables=body.variables,
    )
    return result
