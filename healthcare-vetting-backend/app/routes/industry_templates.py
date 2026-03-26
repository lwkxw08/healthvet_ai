"""
Industry Templates — Admin CRUD for configurable compliance templates per industry.
"""
import json
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
from app.database import get_db
from app.utils.auth import get_current_admin, get_current_user, generate_id

router = APIRouter(prefix="/api/admin/industry-templates", tags=["Industry Templates"])

# Agency-accessible endpoint (read-only list for sub-account template assignment)
agency_router = APIRouter(prefix="/api/industry-templates", tags=["Industry Templates (Agency)"])


class TemplateCheckInput(BaseModel):
    check_key: str = Field(..., max_length=50)
    check_label: str = Field(..., max_length=100)
    is_required: bool = True
    is_enabled: bool = True
    weight: float = Field(10.0, ge=0, le=100)
    config: dict = Field(default_factory=dict)
    sort_order: int = 0


class TemplateCreateInput(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    compliance_label: str = Field("Compliant", max_length=50)
    compliance_threshold: float = Field(95.0, ge=0, le=100)
    checks: list[TemplateCheckInput] = Field(default_factory=list)


class TemplateUpdateInput(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    compliance_label: Optional[str] = None
    compliance_threshold: Optional[float] = None
    is_active: Optional[bool] = None
    checks: Optional[list[TemplateCheckInput]] = None


class AgencyTemplateAssign(BaseModel):
    agency_id: str
    template_id: str


@router.get("")
async def list_templates(admin=Depends(get_current_admin)):
    """List all industry templates with their check configurations."""
    with get_db() as db:
        templates = db.execute(
            "SELECT * FROM industry_templates ORDER BY is_default DESC, name ASC"
        ).fetchall()
        result = []
        for t in templates:
            td = dict(t)
            checks = db.execute(
                "SELECT * FROM industry_template_checks WHERE template_id=? ORDER BY sort_order ASC",
                (td["id"],),
            ).fetchall()
            td["checks"] = [dict(c) for c in checks]
            for c in td["checks"]:
                try:
                    c["config"] = json.loads(c["config"]) if c["config"] else {}
                except (json.JSONDecodeError, TypeError):
                    c["config"] = {}
            # Count agencies using this template
            agency_count = db.execute(
                "SELECT COUNT(*) as cnt FROM agencies WHERE industry_template_id=?",
                (td["id"],),
            ).fetchone()
            td["agency_count"] = dict(agency_count)["cnt"] if agency_count else 0
            result.append(td)
        return result


@router.get("/{template_id}")
async def get_template(template_id: str, admin=Depends(get_current_admin)):
    """Get a single industry template with checks."""
    with get_db() as db:
        t = db.execute("SELECT * FROM industry_templates WHERE id=?", (template_id,)).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        td = dict(t)
        checks = db.execute(
            "SELECT * FROM industry_template_checks WHERE template_id=? ORDER BY sort_order ASC",
            (template_id,),
        ).fetchall()
        td["checks"] = [dict(c) for c in checks]
        for c in td["checks"]:
            try:
                c["config"] = json.loads(c["config"]) if c["config"] else {}
            except (json.JSONDecodeError, TypeError):
                c["config"] = {}
        return td


@router.post("")
async def create_template(data: TemplateCreateInput, admin=Depends(get_current_admin)):
    """Create a new industry template."""
    now = datetime.now(timezone.utc).isoformat()
    template_id = generate_id()
    with get_db() as db:
        # Check for duplicate name
        existing = db.execute("SELECT id FROM industry_templates WHERE name=?", (data.name,)).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Template with this name already exists")

        db.execute(
            """INSERT INTO industry_templates (id, name, description, compliance_label, compliance_threshold, is_default, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)""",
            (template_id, data.name, data.description, data.compliance_label, data.compliance_threshold, now, now),
        )

        # Insert checks
        for check in data.checks:
            db.execute(
                """INSERT INTO industry_template_checks (id, template_id, check_key, check_label, is_required, is_enabled, weight, config, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (generate_id(), template_id, check.check_key, check.check_label,
                 1 if check.is_required else 0, 1 if check.is_enabled else 0,
                 check.weight, json.dumps(check.config), check.sort_order),
            )

    return {"id": template_id, "message": "Template created successfully"}


@router.put("/{template_id}")
async def update_template(template_id: str, data: TemplateUpdateInput, admin=Depends(get_current_admin)):
    """Update an industry template and its checks."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        t = db.execute("SELECT * FROM industry_templates WHERE id=?", (template_id,)).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")

        # Update template fields
        updates = []
        params = []
        if data.name is not None:
            updates.append("name=?")
            params.append(data.name)
        if data.description is not None:
            updates.append("description=?")
            params.append(data.description)
        if data.compliance_label is not None:
            updates.append("compliance_label=?")
            params.append(data.compliance_label)
        if data.compliance_threshold is not None:
            updates.append("compliance_threshold=?")
            params.append(data.compliance_threshold)
        if data.is_active is not None:
            updates.append("is_active=?")
            params.append(1 if data.is_active else 0)

        if updates:
            updates.append("updated_at=?")
            params.append(now)
            params.append(template_id)
            db.execute(f"UPDATE industry_templates SET {', '.join(updates)} WHERE id=?", params)

        # Replace checks if provided
        if data.checks is not None:
            db.execute("DELETE FROM industry_template_checks WHERE template_id=?", (template_id,))
            for check in data.checks:
                db.execute(
                    """INSERT INTO industry_template_checks (id, template_id, check_key, check_label, is_required, is_enabled, weight, config, sort_order)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (generate_id(), template_id, check.check_key, check.check_label,
                     1 if check.is_required else 0, 1 if check.is_enabled else 0,
                     check.weight, json.dumps(check.config), check.sort_order),
                )

    return {"message": "Template updated successfully"}


@router.delete("/{template_id}")
async def delete_template(template_id: str, admin=Depends(get_current_admin)):
    """Delete an industry template (only if no agencies are using it)."""
    with get_db() as db:
        t = db.execute("SELECT * FROM industry_templates WHERE id=?", (template_id,)).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        if dict(t).get("is_default"):
            raise HTTPException(status_code=400, detail="Cannot delete the default template")

        # Check if any agencies are using this template
        agency_count = db.execute(
            "SELECT COUNT(*) as cnt FROM agencies WHERE industry_template_id=?", (template_id,)
        ).fetchone()
        if dict(agency_count)["cnt"] > 0:
            raise HTTPException(status_code=400, detail=f"Cannot delete: {dict(agency_count)['cnt']} agencies are using this template")

        db.execute("DELETE FROM industry_template_checks WHERE template_id=?", (template_id,))
        db.execute("DELETE FROM industry_templates WHERE id=?", (template_id,))

    return {"message": "Template deleted successfully"}


@router.post("/clone/{template_id}")
async def clone_template(template_id: str, admin=Depends(get_current_admin)):
    """Clone an existing template to create a new one."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        t = db.execute("SELECT * FROM industry_templates WHERE id=?", (template_id,)).fetchone()
        if not t:
            raise HTTPException(status_code=404, detail="Template not found")
        td = dict(t)

        new_id = generate_id()
        new_name = f"{td['name']} (Copy)"
        # Ensure unique name
        counter = 1
        while db.execute("SELECT id FROM industry_templates WHERE name=?", (new_name,)).fetchone():
            counter += 1
            new_name = f"{td['name']} (Copy {counter})"

        db.execute(
            """INSERT INTO industry_templates (id, name, description, compliance_label, compliance_threshold, is_default, is_active, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 0, 1, ?, ?)""",
            (new_id, new_name, td["description"], td["compliance_label"], td["compliance_threshold"], now, now),
        )

        # Clone checks
        checks = db.execute(
            "SELECT * FROM industry_template_checks WHERE template_id=?", (template_id,)
        ).fetchall()
        for c in checks:
            cd = dict(c)
            db.execute(
                """INSERT INTO industry_template_checks (id, template_id, check_key, check_label, is_required, is_enabled, weight, config, sort_order)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (generate_id(), new_id, cd["check_key"], cd["check_label"],
                 cd["is_required"], cd["is_enabled"], cd["weight"], cd["config"], cd["sort_order"]),
            )

    return {"id": new_id, "name": new_name, "message": "Template cloned successfully"}


@router.post("/assign")
async def assign_template_to_agency(data: AgencyTemplateAssign, admin=Depends(get_current_admin)):
    """Assign an industry template to an agency."""
    with get_db() as db:
        agency = db.execute("SELECT id FROM agencies WHERE id=?", (data.agency_id,)).fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")
        template = db.execute("SELECT id FROM industry_templates WHERE id=?", (data.template_id,)).fetchone()
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        db.execute("UPDATE agencies SET industry_template_id=? WHERE id=?", (data.template_id, data.agency_id))

    return {"message": "Template assigned to agency successfully"}


@router.get("/agency/{agency_id}")
async def get_agency_template(agency_id: str, admin=Depends(get_current_admin)):
    """Get the industry template assigned to an agency."""
    with get_db() as db:
        agency = db.execute("SELECT id, industry_template_id FROM agencies WHERE id=?", (agency_id,)).fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")
        ad = dict(agency)
        template_id = ad.get("industry_template_id")
        if not template_id:
            # Return default template
            default = db.execute("SELECT * FROM industry_templates WHERE is_default=1 LIMIT 1").fetchone()
            if default:
                td = dict(default)
                checks = db.execute(
                    "SELECT * FROM industry_template_checks WHERE template_id=? ORDER BY sort_order ASC",
                    (td["id"],),
                ).fetchall()
                td["checks"] = [dict(c) for c in checks]
                return td
            return None

        t = db.execute("SELECT * FROM industry_templates WHERE id=?", (template_id,)).fetchone()
        if not t:
            return None
        td = dict(t)
        checks = db.execute(
            "SELECT * FROM industry_template_checks WHERE template_id=? ORDER BY sort_order ASC",
            (template_id,),
        ).fetchall()
        td["checks"] = [dict(c) for c in checks]
        for c in td["checks"]:
            try:
                c["config"] = json.loads(c["config"]) if c["config"] else {}
            except (json.JSONDecodeError, TypeError):
                c["config"] = {}
        return td


# ── Agency-accessible read-only endpoint ─────────────────────────
@agency_router.get("/list")
async def list_templates_for_agency(current_user: dict = Depends(get_current_user)):
    """List all active industry templates (read-only, for agency sub-account assignment)."""
    if current_user["type"] not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    with get_db() as db:
        templates = db.execute(
            "SELECT id, name, description, compliance_label, compliance_threshold FROM industry_templates WHERE is_active=1 ORDER BY is_default DESC, name ASC"
        ).fetchall()
        return [dict(t) for t in templates]
