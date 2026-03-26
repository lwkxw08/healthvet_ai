"""Agency Sub-Accounts with Role-Based Access — recruiter/compliance/manager permissions."""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.utils.auth import get_current_user, generate_id, hash_password, verify_password, create_access_token

router = APIRouter(prefix="/api/agencies/sub-accounts", tags=["Sub-Accounts"])

# Role definitions with permissions
ROLE_PERMISSIONS = {
    "owner": {
        "label": "Owner",
        "permissions": [
            "view_candidates", "edit_candidates", "invite_candidates", "manage_billing",
            "view_compliance", "manage_sub_accounts", "view_invoices", "download_reports",
            "manage_settings", "view_analytics", "request_revet",
        ],
    },
    "manager": {
        "label": "Manager",
        "permissions": [
            "view_candidates", "edit_candidates", "invite_candidates",
            "view_compliance", "view_invoices", "download_reports",
            "view_analytics", "request_revet",
        ],
    },
    "compliance_officer": {
        "label": "Compliance Officer",
        "permissions": [
            "view_candidates", "view_compliance", "download_reports",
            "view_analytics", "request_revet",
        ],
    },
    "recruiter": {
        "label": "Recruiter",
        "permissions": [
            "view_candidates", "invite_candidates", "view_compliance",
        ],
    },
}


class SubAccountCreate(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    role: str  # owner, manager, compliance_officer, recruiter
    industry_template_id: Optional[str] = None


class SubAccountUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    industry_template_id: Optional[str] = None


class SubAccountLogin(BaseModel):
    email: str
    password: str


@router.get("/roles")
async def get_available_roles(current_user: dict = Depends(get_current_user)):
    """Get all available roles and their permissions."""
    return {
        role: {"label": info["label"], "permissions": info["permissions"]}
        for role, info in ROLE_PERMISSIONS.items()
    }


@router.get("")
async def list_sub_accounts(current_user: dict = Depends(get_current_user)):
    """List all sub-accounts for the current agency."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]

    with get_db() as db:
        rows = db.execute(
            """SELECT id, agency_id, email, first_name, last_name, role, industry_template_id, is_active,
                      last_login_at, created_at
               FROM agency_sub_accounts WHERE agency_id=? ORDER BY created_at""",
            (agency_id,),
        ).fetchall()

        results = []
        for row in rows:
            d = dict(row)
            role_info = ROLE_PERMISSIONS.get(d["role"], {})
            d["role_label"] = role_info.get("label", d["role"])
            d["permissions"] = role_info.get("permissions", [])
            # Resolve template name if assigned
            if d.get("industry_template_id"):
                tmpl = db.execute("SELECT name FROM industry_templates WHERE id=?", (d["industry_template_id"],)).fetchone()
                d["industry_template_name"] = dict(tmpl)["name"] if tmpl else None
            else:
                d["industry_template_name"] = None
            results.append(d)

        return results


@router.post("")
async def create_sub_account(data: SubAccountCreate, current_user: dict = Depends(get_current_user)):
    """Create a new sub-account for the agency."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    if data.role not in ROLE_PERMISSIONS:
        raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {list(ROLE_PERMISSIONS.keys())}")

    agency_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    account_id = generate_id()

    with get_db() as db:
        # Check if email already exists for this agency
        existing = db.execute(
            "SELECT id FROM agency_sub_accounts WHERE agency_id=? AND email=?",
            (agency_id, data.email.lower()),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="A sub-account with this email already exists")

        db.execute(
            """INSERT INTO agency_sub_accounts
               (id, agency_id, email, password_hash, first_name, last_name, role, industry_template_id, is_active, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?)""",
            (account_id, agency_id, data.email.lower(), hash_password(data.password),
             data.first_name, data.last_name, data.role, data.industry_template_id, now),
        )

        # Log the action
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (generate_id(), "sub_account", account_id, "sub_account_created",
             current_user["sub"], f"Created sub-account {data.email} with role {data.role}", now),
        )

        # Resolve template name
        template_name = None
        if data.industry_template_id:
            tmpl = db.execute("SELECT name FROM industry_templates WHERE id=?", (data.industry_template_id,)).fetchone()
            template_name = dict(tmpl)["name"] if tmpl else None

        return {
            "id": account_id,
            "agency_id": agency_id,
            "email": data.email.lower(),
            "first_name": data.first_name,
            "last_name": data.last_name,
            "role": data.role,
            "role_label": ROLE_PERMISSIONS[data.role]["label"],
            "permissions": ROLE_PERMISSIONS[data.role]["permissions"],
            "industry_template_id": data.industry_template_id,
            "industry_template_name": template_name,
            "is_active": True,
            "created_at": now,
        }


@router.put("/{account_id}")
async def update_sub_account(account_id: str, data: SubAccountUpdate, current_user: dict = Depends(get_current_user)):
    """Update a sub-account."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM agency_sub_accounts WHERE id=? AND agency_id=?",
            (account_id, agency_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sub-account not found")

        updates = {}
        if data.first_name is not None:
            updates["first_name"] = data.first_name
        if data.last_name is not None:
            updates["last_name"] = data.last_name
        if data.role is not None:
            if data.role not in ROLE_PERMISSIONS:
                raise HTTPException(status_code=400, detail=f"Invalid role. Valid: {list(ROLE_PERMISSIONS.keys())}")
            updates["role"] = data.role
        if data.is_active is not None:
            updates["is_active"] = 1 if data.is_active else 0
        if data.industry_template_id is not None:
            updates["industry_template_id"] = data.industry_template_id if data.industry_template_id else None

        if updates:
            set_clause = ", ".join(f"{k}=?" for k in updates.keys())
            values = list(updates.values()) + [account_id]
            db.execute(f"UPDATE agency_sub_accounts SET {set_clause} WHERE id=?", values)

        row = db.execute(
            "SELECT id, agency_id, email, first_name, last_name, role, industry_template_id, is_active, last_login_at, created_at FROM agency_sub_accounts WHERE id=?",
            (account_id,),
        ).fetchone()
        d = dict(row)
        role_info = ROLE_PERMISSIONS.get(d["role"], {})
        d["role_label"] = role_info.get("label", d["role"])
        d["permissions"] = role_info.get("permissions", [])
        if d.get("industry_template_id"):
            tmpl = db.execute("SELECT name FROM industry_templates WHERE id=?", (d["industry_template_id"],)).fetchone()
            d["industry_template_name"] = dict(tmpl)["name"] if tmpl else None
        else:
            d["industry_template_name"] = None
        return d


@router.delete("/{account_id}")
async def delete_sub_account(account_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a sub-account."""
    if current_user["type"] != "agency":
        raise HTTPException(status_code=403, detail="Agencies only")

    agency_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM agency_sub_accounts WHERE id=? AND agency_id=?",
            (account_id, agency_id),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Sub-account not found")

        email = dict(row)["email"]
        db.execute("DELETE FROM agency_sub_accounts WHERE id=?", (account_id,))

        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (generate_id(), "sub_account", account_id, "sub_account_deleted",
             current_user["sub"], f"Deleted sub-account {email}", now),
        )

        return {"status": "deleted", "account_id": account_id}


@router.post("/login")
async def sub_account_login(data: SubAccountLogin):
    """Login as a sub-account user."""
    with get_db() as db:
        row = db.execute(
            "SELECT * FROM agency_sub_accounts WHERE email=? AND is_active=1",
            (data.email.lower(),),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        account = dict(row)
        if not verify_password(data.password, account["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Update last login
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            "UPDATE agency_sub_accounts SET last_login_at=? WHERE id=?",
            (now, account["id"]),
        )

        # Create token with agency_id as sub (for API compatibility) but include sub_account info
        token = create_access_token(account["agency_id"], "agency")

        return {
            "access_token": token,
            "user_type": "agency",
            "user_id": account["agency_id"],
            "sub_account_id": account["id"],
            "role": account["role"],
            "role_label": ROLE_PERMISSIONS.get(account["role"], {}).get("label", account["role"]),
            "permissions": ROLE_PERMISSIONS.get(account["role"], {}).get("permissions", []),
            "name": f"{account['first_name']} {account['last_name']}",
            "industry_template_id": account.get("industry_template_id"),
        }
