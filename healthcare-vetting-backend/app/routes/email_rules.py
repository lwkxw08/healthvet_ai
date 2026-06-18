"""
Email Rules Management Routes
Admin endpoints for CRUD on email rules (action-to-template mappings).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.email_rules import EmailRulesService

router = APIRouter(prefix="/api/admin/email-rules", tags=["Email Rules"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class RuleCreate(BaseModel):
    action_trigger: str
    name: str
    description: str = ""
    template_key: str
    recipient_type: str = "primary"
    conditions: dict = {}
    priority: int = 0


class RuleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    template_key: str | None = None
    recipient_type: str | None = None
    conditions: dict | None = None
    priority: int | None = None
    is_active: bool | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("")
async def list_rules():
    """List all email rules."""
    rules = EmailRulesService.get_all_rules()
    return {"rules": rules}


@router.get("/triggers")
async def list_triggers():
    """List all known action triggers with metadata."""
    triggers = EmailRulesService.get_action_triggers()
    return {"triggers": triggers}


@router.post("")
async def create_rule(body: RuleCreate):
    """Create a new email rule."""
    result = EmailRulesService.create_rule(
        action_trigger=body.action_trigger,
        name=body.name,
        description=body.description,
        template_key=body.template_key,
        recipient_type=body.recipient_type,
        conditions=body.conditions,
        priority=body.priority,
    )
    return result


@router.get("/{rule_id}")
async def get_rule(rule_id: str):
    """Get a single rule by ID."""
    rule = EmailRulesService.get_rule(rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


@router.put("/{rule_id}")
async def update_rule(rule_id: str, body: RuleUpdate):
    """Update a rule."""
    result = EmailRulesService.update_rule(
        rule_id,
        name=body.name,
        description=body.description,
        template_key=body.template_key,
        recipient_type=body.recipient_type,
        conditions=body.conditions,
        priority=body.priority,
        is_active=body.is_active,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Rule not found")
    return result


@router.delete("/{rule_id}")
async def delete_rule(rule_id: str):
    """Delete a rule."""
    result = EmailRulesService.delete_rule(rule_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"status": "deleted"}
