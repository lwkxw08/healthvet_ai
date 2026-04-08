"""
Industry-Specific Subscription Plans (Option A) + Per-Element Industry Pricing (Option C)
Routes for managing subscription plans tied to industries with per-check pricing.
"""
import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.utils.auth import get_current_user, generate_id

router = APIRouter(prefix="/api/subscription-plans", tags=["Subscription Plans"])


def require_admin(current_user: dict):
    if current_user.get("role") != "admin" and current_user.get("type") != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


# Mapping from template check_key to pricing_settings check_type (for default price lookup)
CHECK_KEY_TO_PRICING_TYPE = {
    "identity_verified": "identity",
    "right_to_work_valid": "right_to_work",
    "dbs_valid": "dbs",
    "dbs_standard": "dbs_standard",
    "dbs_enhanced": "dbs_enhanced",
    "dbs_enhanced_barred": "dbs_enhanced_barred",
    "employment_verified": "employment",
    "references_verified": "references",
    "registration_active": "registration",
    "cv_validated": "cv_analysis",
    "training_compliant": "training_verification",
    "overseas_criminal_check": "overseas_criminal",
    "professional_registration_check": "professional_registration",
    "occupational_health_check": "fit_to_work",
    "training_verification": "training_verification",
    "sanctions_check": "sanctions_check",
    "credit_check": "credit_check",
    "social_media_check": "social_media_check",
    "counterterrorism_check": "counterterrorism_check",
}


def _sync_industry_pricing(db, industry_template_id: str):
    """Ensure industry_check_pricing has a row for every enabled check in the template.
    Missing checks are auto-populated with defaults from pricing_settings."""
    template_checks = db.execute(
        "SELECT check_key, check_label FROM industry_template_checks WHERE template_id=? AND is_enabled=1 ORDER BY sort_order",
        (industry_template_id,)
    ).fetchall()
    if not template_checks:
        return

    existing_types = {row[0] for row in db.execute(
        "SELECT check_type FROM industry_check_pricing WHERE industry_template_id=?",
        (industry_template_id,)
    ).fetchall()}

    # Load default pricing for lookup
    pricing_defaults = {dict(r)["check_type"]: dict(r) for r in db.execute("SELECT * FROM pricing_settings").fetchall()}

    now = datetime.now(timezone.utc).isoformat()
    for tc in template_checks:
        tc_dict = dict(tc)
        check_key = tc_dict["check_key"]
        if check_key in existing_types:
            continue
        # Look up default pricing
        pricing_type = CHECK_KEY_TO_PRICING_TYPE.get(check_key, check_key)
        defaults = pricing_defaults.get(pricing_type, {})
        pricing_id = generate_id()
        db.execute(
            """INSERT INTO industry_check_pricing
               (id, industry_template_id, check_type, label, credit_value,
                third_party_cost, sell_price, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pricing_id, industry_template_id, check_key,
             tc_dict["check_label"],
             1.0,
             defaults.get("cost_price", 0),
             defaults.get("sell_price", 0),
             now),
        )


# ── Schemas ──────────────────────────────────────────────────────────

class IndustryPlanLinkCreate(BaseModel):
    tier_key: str
    industry_template_id: str
    custom_monthly_price: Optional[float] = None
    custom_per_worker_price: Optional[float] = None
    custom_monthly_checks: Optional[int] = None


class IndustryPlanLinkUpdate(BaseModel):
    custom_monthly_price: Optional[float] = None
    custom_per_worker_price: Optional[float] = None
    custom_monthly_checks: Optional[int] = None
    is_active: Optional[bool] = None


class IndustryCheckPricingCreate(BaseModel):
    industry_template_id: str
    check_type: str
    label: Optional[str] = None
    credit_value: Optional[float] = 1.0
    third_party_cost: Optional[float] = 0.0
    sell_price: Optional[float] = 0.0


class IndustryCheckPricingUpdate(BaseModel):
    label: Optional[str] = None
    credit_value: Optional[float] = None
    third_party_cost: Optional[float] = None
    sell_price: Optional[float] = None
    is_active: Optional[bool] = None


class BulkIndustryPricingRequest(BaseModel):
    industry_template_id: str
    pricing: List[dict]  # [{check_type, label, credit_value, third_party_cost, sell_price}]


# ── Option A: Industry-Specific Plan Links ────────────────────────────

@router.get("/industry-plans")
async def list_industry_plan_links(current_user: dict = Depends(get_current_user)):
    """List all industry-plan links with enriched data."""
    require_admin(current_user)

    with get_db() as db:
        rows = db.execute("""
            SELECT ipl.*, it.name as industry_name, it.description as industry_description,
                   stc.name as tier_name, stc.monthly_price as base_monthly_price,
                   stc.per_worker_price as base_per_worker_price, stc.monthly_checks as base_monthly_checks
            FROM industry_plan_links ipl
            LEFT JOIN industry_templates it ON ipl.industry_template_id = it.id
            LEFT JOIN subscription_tier_config stc ON ipl.tier_key = stc.tier_key
            ORDER BY it.name, stc.monthly_price
        """).fetchall()
        return [dict(r) for r in rows]


@router.post("/industry-plans")
async def create_industry_plan_link(data: IndustryPlanLinkCreate, current_user: dict = Depends(get_current_user)):
    """Link a subscription tier to an industry with optional custom pricing."""
    require_admin(current_user)

    link_id = generate_id()
    with get_db() as db:
        # Verify tier and template exist
        tier = db.execute("SELECT * FROM subscription_tier_config WHERE tier_key=?", (data.tier_key,)).fetchone()
        if not tier:
            raise HTTPException(status_code=404, detail=f"Tier '{data.tier_key}' not found")

        template = db.execute("SELECT * FROM industry_templates WHERE id=?", (data.industry_template_id,)).fetchone()
        if not template:
            raise HTTPException(status_code=404, detail="Industry template not found")

        # Check for duplicates
        existing = db.execute(
            "SELECT id FROM industry_plan_links WHERE tier_key=? AND industry_template_id=?",
            (data.tier_key, data.industry_template_id),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="This tier-industry link already exists")

        db.execute(
            """INSERT INTO industry_plan_links
               (id, tier_key, industry_template_id, custom_monthly_price,
                custom_per_worker_price, custom_monthly_checks)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (link_id, data.tier_key, data.industry_template_id,
             data.custom_monthly_price, data.custom_per_worker_price, data.custom_monthly_checks),
        )

        row = db.execute("SELECT * FROM industry_plan_links WHERE id=?", (link_id,)).fetchone()
        return dict(row)


@router.put("/industry-plans/{link_id}")
async def update_industry_plan_link(link_id: str, data: IndustryPlanLinkUpdate, current_user: dict = Depends(get_current_user)):
    """Update an industry-plan link."""
    require_admin(current_user)

    with get_db() as db:
        existing = db.execute("SELECT * FROM industry_plan_links WHERE id=?", (link_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Industry-plan link not found")

        updates = []
        params = []
        if data.custom_monthly_price is not None:
            updates.append("custom_monthly_price=?")
            params.append(data.custom_monthly_price)
        if data.custom_per_worker_price is not None:
            updates.append("custom_per_worker_price=?")
            params.append(data.custom_per_worker_price)
        if data.custom_monthly_checks is not None:
            updates.append("custom_monthly_checks=?")
            params.append(data.custom_monthly_checks)
        if data.is_active is not None:
            updates.append("is_active=?")
            params.append(1 if data.is_active else 0)

        if updates:
            params.append(link_id)
            db.execute(f"UPDATE industry_plan_links SET {', '.join(updates)} WHERE id=?", params)

        row = db.execute("SELECT * FROM industry_plan_links WHERE id=?", (link_id,)).fetchone()
        return dict(row)


@router.delete("/industry-plans/{link_id}")
async def delete_industry_plan_link(link_id: str, current_user: dict = Depends(get_current_user)):
    """Delete an industry-plan link."""
    require_admin(current_user)

    with get_db() as db:
        existing = db.execute("SELECT * FROM industry_plan_links WHERE id=?", (link_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Industry-plan link not found")
        db.execute("DELETE FROM industry_plan_links WHERE id=?", (link_id,))
        return {"deleted": True}


# ── Option C: Per-Element Industry Pricing ─────────────────────────────

@router.get("/industry-pricing")
async def list_industry_check_pricing(
    industry_template_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """List per-element pricing for industries.
    Auto-syncs: if template has enabled checks without pricing rows, creates them from pricing_settings defaults."""
    require_admin(current_user)

    with get_db() as db:
        if industry_template_id:
            # Auto-sync: ensure pricing rows exist for all enabled template checks
            _sync_industry_pricing(db, industry_template_id)

            rows = db.execute("""
                SELECT icp.*, it.name as industry_name
                FROM industry_check_pricing icp
                LEFT JOIN industry_templates it ON icp.industry_template_id = it.id
                WHERE icp.industry_template_id=?
                ORDER BY icp.check_type
            """, (industry_template_id,)).fetchall()
        else:
            rows = db.execute("""
                SELECT icp.*, it.name as industry_name
                FROM industry_check_pricing icp
                LEFT JOIN industry_templates it ON icp.industry_template_id = it.id
                ORDER BY it.name, icp.check_type
            """).fetchall()
        return [dict(r) for r in rows]


@router.post("/industry-pricing")
async def create_industry_check_pricing(data: IndustryCheckPricingCreate, current_user: dict = Depends(get_current_user)):
    """Create per-element pricing for an industry."""
    require_admin(current_user)

    pricing_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        template = db.execute("SELECT * FROM industry_templates WHERE id=?", (data.industry_template_id,)).fetchone()
        if not template:
            raise HTTPException(status_code=404, detail="Industry template not found")

        existing = db.execute(
            "SELECT id FROM industry_check_pricing WHERE industry_template_id=? AND check_type=?",
            (data.industry_template_id, data.check_type),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Pricing for this check type already exists for this industry")

        db.execute(
            """INSERT INTO industry_check_pricing
               (id, industry_template_id, check_type, label, credit_value,
                third_party_cost, sell_price, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (pricing_id, data.industry_template_id, data.check_type,
             data.label or data.check_type.replace("_", " ").title(),
             data.credit_value, data.third_party_cost, data.sell_price, now),
        )

        row = db.execute("SELECT * FROM industry_check_pricing WHERE id=?", (pricing_id,)).fetchone()
        return dict(row)


@router.put("/industry-pricing/{pricing_id}")
async def update_industry_check_pricing(pricing_id: str, data: IndustryCheckPricingUpdate, current_user: dict = Depends(get_current_user)):
    """Update per-element pricing."""
    require_admin(current_user)

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        existing = db.execute("SELECT * FROM industry_check_pricing WHERE id=?", (pricing_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Pricing not found")

        updates = ["updated_at=?"]
        params = [now]
        if data.label is not None:
            updates.append("label=?")
            params.append(data.label)
        if data.credit_value is not None:
            updates.append("credit_value=?")
            params.append(data.credit_value)
        if data.third_party_cost is not None:
            updates.append("third_party_cost=?")
            params.append(data.third_party_cost)
        if data.sell_price is not None:
            updates.append("sell_price=?")
            params.append(data.sell_price)
        if data.is_active is not None:
            updates.append("is_active=?")
            params.append(1 if data.is_active else 0)

        params.append(pricing_id)
        db.execute(f"UPDATE industry_check_pricing SET {', '.join(updates)} WHERE id=?", params)

        row = db.execute("SELECT * FROM industry_check_pricing WHERE id=?", (pricing_id,)).fetchone()
        return dict(row)


@router.delete("/industry-pricing/{pricing_id}")
async def delete_industry_check_pricing(pricing_id: str, current_user: dict = Depends(get_current_user)):
    """Delete per-element pricing."""
    require_admin(current_user)

    with get_db() as db:
        existing = db.execute("SELECT * FROM industry_check_pricing WHERE id=?", (pricing_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Pricing not found")
        db.execute("DELETE FROM industry_check_pricing WHERE id=?", (pricing_id,))
        return {"deleted": True}


@router.post("/industry-pricing/bulk")
async def bulk_set_industry_pricing(data: BulkIndustryPricingRequest, current_user: dict = Depends(get_current_user)):
    """Set pricing for all check types for an industry at once (upsert)."""
    require_admin(current_user)

    now = datetime.now(timezone.utc).isoformat()
    results = []

    with get_db() as db:
        template = db.execute("SELECT * FROM industry_templates WHERE id=?", (data.industry_template_id,)).fetchone()
        if not template:
            raise HTTPException(status_code=404, detail="Industry template not found")

        for item in data.pricing:
            check_type = item.get("check_type")
            if not check_type:
                continue

            existing = db.execute(
                "SELECT id FROM industry_check_pricing WHERE industry_template_id=? AND check_type=?",
                (data.industry_template_id, check_type),
            ).fetchone()

            if existing:
                # Update
                db.execute(
                    """UPDATE industry_check_pricing
                       SET label=?, credit_value=?, third_party_cost=?, sell_price=?, updated_at=?
                       WHERE id=?""",
                    (item.get("label", check_type.replace("_", " ").title()),
                     float(item.get("credit_value", 1.0)),
                     float(item.get("third_party_cost", 0)),
                     float(item.get("sell_price", 0)),
                     now, existing["id"]),
                )
                results.append({"check_type": check_type, "action": "updated"})
            else:
                # Insert
                pricing_id = generate_id()
                db.execute(
                    """INSERT INTO industry_check_pricing
                       (id, industry_template_id, check_type, label, credit_value,
                        third_party_cost, sell_price, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (pricing_id, data.industry_template_id, check_type,
                     item.get("label", check_type.replace("_", " ").title()),
                     float(item.get("credit_value", 1.0)),
                     float(item.get("third_party_cost", 0)),
                     float(item.get("sell_price", 0)),
                     now),
                )
                results.append({"check_type": check_type, "action": "created"})

    return {"results": results, "industry_template_id": data.industry_template_id}


# ── Combined View: Plans by Industry ──────────────────────────────────

@router.get("/by-industry")
async def get_plans_by_industry(current_user: dict = Depends(get_current_user)):
    """Get a combined view of all plans organized by industry with their pricing."""
    require_admin(current_user)

    with get_db() as db:
        templates = db.execute("SELECT * FROM industry_templates WHERE is_active=1 ORDER BY name").fetchall()
        tiers = db.execute("SELECT * FROM subscription_tier_config WHERE is_active=1 ORDER BY monthly_price").fetchall()

        result = []
        for tmpl in templates:
            t = dict(tmpl)
            industry_id = t["id"]

            # Get plan links for this industry
            plan_links = db.execute(
                """SELECT ipl.*, stc.name as tier_name, stc.monthly_price as base_monthly_price,
                          stc.per_worker_price as base_per_worker_price, stc.monthly_checks as base_monthly_checks
                   FROM industry_plan_links ipl
                   LEFT JOIN subscription_tier_config stc ON ipl.tier_key = stc.tier_key
                   WHERE ipl.industry_template_id=? AND ipl.is_active=1""",
                (industry_id,),
            ).fetchall()

            # Get per-element pricing for this industry
            check_pricing = db.execute(
                "SELECT * FROM industry_check_pricing WHERE industry_template_id=? AND is_active=1 ORDER BY check_type",
                (industry_id,),
            ).fetchall()

            # Get template checks
            template_checks = db.execute(
                "SELECT * FROM industry_template_checks WHERE template_id=? ORDER BY sort_order",
                (industry_id,),
            ).fetchall()

            result.append({
                "industry": {
                    "id": t["id"],
                    "name": t["name"],
                    "description": t["description"],
                    "compliance_label": t["compliance_label"],
                    "compliance_threshold": t["compliance_threshold"],
                },
                "plan_links": [dict(pl) for pl in plan_links],
                "check_pricing": [dict(cp) for cp in check_pricing],
                "template_checks": [dict(tc) for tc in template_checks],
                "available_tiers": [dict(tier) for tier in tiers],
            })

        return result


@router.get("/pricing-matrix")
async def get_pricing_matrix(current_user: dict = Depends(get_current_user)):
    """Get a pricing matrix: industries x check types with prices."""
    require_admin(current_user)

    with get_db() as db:
        templates = db.execute("SELECT * FROM industry_templates WHERE is_active=1 ORDER BY name").fetchall()
        all_pricing = db.execute("""
            SELECT icp.*, it.name as industry_name
            FROM industry_check_pricing icp
            LEFT JOIN industry_templates it ON icp.industry_template_id = it.id
            WHERE icp.is_active=1
            ORDER BY it.name, icp.check_type
        """).fetchall()

        # Get default rates
        default_rates = db.execute("SELECT * FROM partial_credit_rates").fetchall()

        # Build matrix
        check_types = set()
        matrix = {}
        for row in all_pricing:
            r = dict(row)
            check_types.add(r["check_type"])
            if r["industry_name"] not in matrix:
                matrix[r["industry_name"]] = {}
            matrix[r["industry_name"]][r["check_type"]] = {
                "credit_value": r["credit_value"],
                "third_party_cost": r["third_party_cost"],
                "sell_price": r["sell_price"],
            }

        return {
            "industries": [dict(t) for t in templates],
            "check_types": sorted(check_types),
            "matrix": matrix,
            "default_rates": [dict(r) for r in default_rates],
        }
