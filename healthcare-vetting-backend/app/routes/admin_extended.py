"""Extended admin routes: override checks, suspend agencies, edit candidates,
manage users, alert settings, audit log viewer, edit entry data, re-trigger verifications."""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.utils.auth import get_current_user, generate_id, hash_password, create_access_token

router = APIRouter(prefix="/api/admin", tags=["Admin Extended"])


def require_admin(current_user: dict):
    if current_user["type"] != "admin":
        raise HTTPException(status_code=403, detail="Admin only")


# ── 1. Override / Force-Pass Candidate Check Results ─────────────

class CheckOverride(BaseModel):
    check_type: str  # identity, dbs, right_to_work, cv_analysis, registration, references, employment
    status: str  # e.g. "completed", "clear", "verified", "flagged"
    notes: Optional[str] = None


@router.post("/candidates/{candidate_id}/override-check")
async def override_candidate_check(
    candidate_id: str, data: CheckOverride, current_user: dict = Depends(get_current_user)
):
    """Override a candidate's individual check result (admin force-pass/fail)."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    table_map = {
        "identity": ("identity_checks", "status", "completed_at"),
        "dbs": ("dbs_checks", "status", "completed_at"),
        "right_to_work": ("right_to_work_checks", "status", "checked_at"),
        "cv_analysis": ("cv_analyses", "status", "analysed_at"),
        "registration": ("registration_checks", "status", "last_checked"),
        "references": ("references_", "status", "completed_at"),
        "employment": ("employment_verifications", "status", "completed_at"),
    }

    if data.check_type not in table_map:
        raise HTTPException(status_code=400, detail=f"Invalid check_type. Valid: {list(table_map.keys())}")

    table, status_col, date_col = table_map[data.check_type]

    with get_db() as db:
        # Verify candidate exists
        db.execute("SELECT id FROM candidates WHERE id=%s", (candidate_id,))
        cand = db.fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Find existing check record(s)
        db.execute(f"SELECT id FROM {table} WHERE candidate_id=%s", (candidate_id,))
        rows = db.fetchall()

        if rows:
            # Update the most recent check
            row_id = dict(rows[-1])["id"]
            db.execute(f"UPDATE {table} SET {status_col}=%s, {date_col}=%s WHERE id=%s",
                       (data.status, now, row_id))
            # For identity checks, also set result field
            if data.check_type == "identity":
                db.execute("UPDATE identity_checks SET result=%s WHERE id=%s", (data.status, row_id))
            if data.check_type == "dbs":
                db.execute("UPDATE dbs_checks SET result=%s WHERE id=%s", (data.status, row_id))
            if data.check_type == "right_to_work":
                db.execute("UPDATE right_to_work_checks SET verified=%s WHERE id=%s",
                           (1 if data.status in ("verified", "clear", "completed") else 0, row_id))
            if data.check_type == "registration":
                db.execute("UPDATE registration_checks SET is_active=%s, result=%s WHERE id=%s",
                           (1 if data.status in ("active", "verified", "clear") else 0, data.status, row_id))
        else:
            # Create a new check record with the overridden status
            new_id = generate_id()
            if data.check_type == "identity":
                db.execute(
                    "INSERT INTO identity_checks (id, candidate_id, status, result, completed_at) VALUES (%s,%s,%s,%s,%s)",
                    (new_id, candidate_id, data.status, data.status, now))
            elif data.check_type == "dbs":
                db.execute(
                    "INSERT INTO dbs_checks (id, candidate_id, status, result, completed_at) VALUES (%s,%s,%s,%s,%s)",
                    (new_id, candidate_id, data.status, data.status, now))
            elif data.check_type == "right_to_work":
                verified = 1 if data.status in ("verified", "clear", "completed") else 0
                db.execute(
                    "INSERT INTO right_to_work_checks (id, candidate_id, status, verified, checked_at) VALUES (%s,%s,%s,%s,%s)",
                    (new_id, candidate_id, data.status, verified, now))
            elif data.check_type == "cv_analysis":
                db.execute(
                    "INSERT INTO cv_analyses (id, candidate_id, status, analysed_at) VALUES (%s,%s,%s,%s)",
                    (new_id, candidate_id, data.status, now))
            elif data.check_type == "registration":
                is_active = 1 if data.status in ("active", "verified", "clear") else 0
                db.execute(
                    "INSERT INTO registration_checks (id, candidate_id, body, status, is_active, result, last_checked) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (new_id, candidate_id, "NMC", data.status, is_active, data.status, now))
            elif data.check_type == "references":
                db.execute(
                    "INSERT INTO references_ (id, candidate_id, referee_name, referee_email, status, completed_at) VALUES (%s,%s,%s,%s,%s,%s)",
                    (new_id, candidate_id, "Admin Override", "admin@override", data.status, now))
            elif data.check_type == "employment":
                db.execute(
                    "INSERT INTO employment_verifications (id, candidate_id, employment_id, verifier_name, verifier_email, status, completed_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (new_id, candidate_id, "admin-override", "Admin Override", "admin@override", data.status, now))

        # Log the override action
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "check_override", candidate_id, f"override_{data.check_type}",
             current_user["sub"], f"Status set to '{data.status}'. Notes: {data.notes or 'N/A'}", now))

        # Re-evaluate compliance
        from app.services.compliance_engine import ComplianceEngine
        ComplianceEngine.evaluate_candidate(candidate_id)

        return {"status": "overridden", "check_type": data.check_type, "new_status": data.status, "candidate_id": candidate_id}


# ── 2. Suspend / Deactivate Agency Accounts ──────────────────────

class AgencyStatusUpdate(BaseModel):
    status: str  # active, suspended, deactivated
    reason: Optional[str] = None


@router.put("/agencies/{agency_id}/status")
async def update_agency_status(
    agency_id: str, data: AgencyStatusUpdate, current_user: dict = Depends(get_current_user)
):
    """Suspend or deactivate an agency account."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    valid_statuses = ["active", "suspended", "deactivated"]
    if data.status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Valid: {valid_statuses}")

    with get_db() as db:
        db.execute("SELECT * FROM agencies WHERE id=%s", (agency_id,))
        agency = db.fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")

        db.execute("UPDATE agencies SET status=%s WHERE id=%s", (data.status, agency_id))

        # Log the action
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "agency", agency_id, f"status_changed_to_{data.status}",
             current_user["sub"], data.reason or "", now))

        db.execute("SELECT * FROM agencies WHERE id=%s", (agency_id,))
        row = db.fetchone()
        return dict(row)


@router.get("/agencies")
async def list_agencies(current_user: dict = Depends(get_current_user)):
    """List all agencies with their status."""
    require_admin(current_user)
    with get_db() as db:
        db.execute("""
            SELECT a.*,
                   (SELECT COUNT(*) AS cnt FROM agency_candidates ac WHERE ac.agency_id = a.id) as candidate_count
            FROM agencies a ORDER BY a.created_at DESC
        """)
        rows = db.fetchall()
        return [dict(r) for r in rows]


# ── 3. Edit Candidate Profiles Directly ──────────────────────────

class CandidateProfileEdit(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    date_of_birth: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    postcode: Optional[str] = None
    country: Optional[str] = None
    profession: Optional[str] = None
    registration_number: Optional[str] = None
    registration_body: Optional[str] = None


@router.put("/candidates/{candidate_id}")
async def admin_edit_candidate(
    candidate_id: str, data: CandidateProfileEdit, current_user: dict = Depends(get_current_user)
):
    """Admin edit candidate profile fields directly."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    with get_db() as db:
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        cand = db.fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        old_values = dict(cand)
        updates["updated_at"] = now
        set_clause = ", ".join(f"{k}=%s" for k in updates.keys())
        values = list(updates.values()) + [candidate_id]
        db.execute(f"UPDATE candidates SET {set_clause} WHERE id=%s", values)

        # Log the changes
        changes = {k: {"old": old_values.get(k), "new": v} for k, v in updates.items() if k != "updated_at" and old_values.get(k) != v}
        log_id = generate_id()
        import json
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "candidate", candidate_id, "admin_edit_profile",
             current_user["sub"], json.dumps(changes), now))

        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        row = db.fetchone()
        return dict(row)


# ── 4. Manage User Accounts (Create / Delete) ────────────────────

class CreateAgencyRequest(BaseModel):
    name: str
    email: str
    password: str
    contact_name: Optional[str] = None
    phone: Optional[str] = None
    plan: Optional[str] = "standard"


class CreateCandidateRequest(BaseModel):
    email: str
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None
    profession: Optional[str] = None


@router.post("/agencies/create")
async def admin_create_agency(data: CreateAgencyRequest, current_user: dict = Depends(get_current_user)):
    """Admin create a new agency account."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    agency_id = generate_id()

    with get_db() as db:
        db.execute("SELECT id FROM agencies WHERE email=%s", (data.email,))
        existing = db.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Agency with this email already exists")

        db.execute(
            "INSERT INTO agencies (id, name, email, password_hash, contact_name, phone, plan, status, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (agency_id, data.name, data.email, hash_password(data.password),
             data.contact_name, data.phone, data.plan, "active", now))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "agency", agency_id, "admin_created_agency", current_user["sub"], f"Created agency: {data.name}", now))

        db.execute("SELECT * FROM agencies WHERE id=%s", (agency_id,))
        row = db.fetchone()
        return dict(row)


@router.post("/candidates/create")
async def admin_create_candidate(data: CreateCandidateRequest, current_user: dict = Depends(get_current_user)):
    """Admin create a new candidate account."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    cand_id = generate_id()

    with get_db() as db:
        db.execute("SELECT id FROM candidates WHERE email=%s", (data.email,))
        existing = db.fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Candidate with this email already exists")

        db.execute(
            "INSERT INTO candidates (id, email, password_hash, first_name, last_name, phone, profession, created_at, updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (cand_id, data.email, hash_password(data.password),
             data.first_name, data.last_name, data.phone, data.profession, now, now))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "candidate", cand_id, "admin_created_candidate", current_user["sub"], f"Created candidate: {data.first_name} {data.last_name}", now))

        db.execute("SELECT * FROM candidates WHERE id=%s", (cand_id,))
        row = db.fetchone()
        return dict(row)


@router.delete("/agencies/{agency_id}")
async def admin_delete_agency(agency_id: str, current_user: dict = Depends(get_current_user)):
    """Admin delete an agency account."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute("SELECT * FROM agencies WHERE id=%s", (agency_id,))
        agency = db.fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")

        agency_name = dict(agency)["name"]
        # Remove agency-candidate links
        db.execute("DELETE FROM agency_candidates WHERE agency_id=%s", (agency_id,))
        db.execute("DELETE FROM agency_invites WHERE agency_id=%s", (agency_id,))
        db.execute("DELETE FROM agency_subscriptions WHERE agency_id=%s", (agency_id,))
        db.execute("DELETE FROM agencies WHERE id=%s", (agency_id,))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "agency", agency_id, "admin_deleted_agency", current_user["sub"], f"Deleted agency: {agency_name}", now))

        return {"status": "deleted", "agency_id": agency_id, "name": agency_name}


@router.delete("/candidates/{candidate_id}")
async def admin_delete_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Admin delete a candidate account and all related data."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        cand = db.fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        cand_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}"
        # Remove all related data
        for tbl in ["identity_checks", "right_to_work_checks", "dbs_checks", "cv_analyses",
                     "registration_checks", "references_", "compliance_records", "monitoring_alerts",
                     "employment_history", "employment_verifications", "training_certificates", "fraud_flags"]:
            db.execute(f"DELETE FROM {tbl} WHERE candidate_id=%s", (candidate_id,))
        db.execute("DELETE FROM agency_candidates WHERE candidate_id=%s", (candidate_id,))
        db.execute("DELETE FROM candidates WHERE id=%s", (candidate_id,))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "candidate", candidate_id, "admin_deleted_candidate", current_user["sub"], f"Deleted candidate: {cand_name}", now))

        return {"status": "deleted", "candidate_id": candidate_id, "name": cand_name}


@router.post("/purge-test-accounts")
async def admin_purge_test_accounts(current_user: dict = Depends(get_current_user)):
    """Bulk-delete all accounts with @test.viperai email domain (e2e test data)."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        # Delete test candidates
        db.execute("SELECT id, first_name, last_name, email FROM candidates WHERE email LIKE %s", ("%@test.viperai",))
        test_candidates = db.fetchall()
        for cand in test_candidates:
            c = dict(cand)
            for tbl in ["identity_checks", "right_to_work_checks", "dbs_checks", "cv_analyses",
                         "registration_checks", "references_", "compliance_records", "monitoring_alerts",
                         "employment_history", "employment_verifications", "training_certificates", "fraud_flags",
                         "candidate_draft_data", "candidate_documents", "submissions"]:
                try:
                    db.execute(f"DELETE FROM {tbl} WHERE candidate_id=%s", (c["id"],))
                except Exception:
                    pass
            db.execute("DELETE FROM agency_candidates WHERE candidate_id=%s", (c["id"],))
            db.execute("DELETE FROM candidates WHERE id=%s", (c["id"],))

        # Delete test agencies
        db.execute("SELECT id, name, email FROM agencies WHERE email LIKE %s", ("%@test.viperai",))
        test_agencies = db.fetchall()
        for ag in test_agencies:
            a = dict(ag)
            for tbl in ["agency_invites", "agency_candidates", "invoices", "agency_sub_accounts"]:
                try:
                    db.execute(f"DELETE FROM {tbl} WHERE agency_id=%s", (a["id"],))
                except Exception:
                    pass
            db.execute("DELETE FROM agencies WHERE id=%s", (a["id"],))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "system", "test-purge", "admin_purged_test_accounts", current_user["sub"],
             f"Purged {len(test_candidates)} candidates and {len(test_agencies)} agencies with @test.viperai emails", now))

        return {
            "status": "purged",
            "candidates_deleted": len(test_candidates),
            "agencies_deleted": len(test_agencies),
        }


# ── 5. Configurable Alert Thresholds & Expiry Warning Windows ────

class AlertSettings(BaseModel):
    visa_warning_days: Optional[int] = None
    dbs_warning_days: Optional[int] = None
    registration_warning_days: Optional[int] = None
    training_warning_days: Optional[int] = None


@router.get("/alert-settings")
async def get_alert_settings(current_user: dict = Depends(get_current_user)):
    """Get current alert threshold settings."""
    require_admin(current_user)
    with get_db() as db:
        db.execute("SELECT * FROM alert_settings ORDER BY setting_key")
        rows = db.fetchall()
        if not rows:
            # Return defaults
            return {
                "visa_warning_days": 30,
                "dbs_warning_days": 60,
                "registration_warning_days": 30,
                "training_warning_days": 30,
            }
        return {dict(r)["setting_key"]: dict(r)["setting_value"] for r in rows}


@router.put("/alert-settings")
async def update_alert_settings(data: AlertSettings, current_user: dict = Depends(get_current_user)):
    """Update alert threshold settings."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    updates = {k: v for k, v in data.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No settings to update")

    with get_db() as db:
        for key, value in updates.items():
            db.execute("SELECT id FROM alert_settings WHERE setting_key=%s", (key,))
            existing = db.fetchone()
            if existing:
                db.execute("UPDATE alert_settings SET setting_value=%s, updated_at=%s WHERE setting_key=%s",
                           (value, now, key))
            else:
                db.execute("INSERT INTO alert_settings (id, setting_key, setting_value, updated_at) VALUES (%s,%s,%s,%s)",
                           (generate_id(), key, value, now))

        log_id = generate_id()
        import json
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "settings", "alert_settings", "update_alert_settings",
             current_user["sub"], json.dumps(updates), now))

        # Return updated settings
        db.execute("SELECT * FROM alert_settings ORDER BY setting_key")
        rows = db.fetchall()
        return {dict(r)["setting_key"]: dict(r)["setting_value"] for r in rows}


# ── 6. Audit Log Viewer ──────────────────────────────────────────

@router.get("/audit-logs")
async def get_audit_logs(
    entity_type: str = None,
    entity_id: str = None,
    action: str = None,
    limit: int = 100,
    offset: int = 0,
    current_user: dict = Depends(get_current_user),
):
    """Get audit logs with optional filters."""
    require_admin(current_user)

    with get_db() as db:
        query = "SELECT * FROM audit_logs WHERE 1=1"
        params: list = []

        if entity_type:
            query += " AND entity_type=%s"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id=%s"
            params.append(entity_id)
        if action:
            query += " AND action LIKE %s"
            params.append(f"%{action}%")

        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as cnt")
        db.execute(count_query, params)
        total = dict(db.fetchone())["cnt"]

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        db.execute(query, params)
        rows = db.fetchall()
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "logs": [dict(r) for r in rows],
        }


# ── 7. Edit Candidate Entry Data (Automation Fallout) ────────────

class CandidateCheckDataEdit(BaseModel):
    """Edit any field on a specific check record."""
    fields: dict  # key-value pairs to update


@router.put("/candidates/{candidate_id}/check-data/{check_type}/{check_id}")
async def admin_edit_check_data(
    candidate_id: str, check_type: str, check_id: str,
    data: CandidateCheckDataEdit, current_user: dict = Depends(get_current_user)
):
    """Admin edit any field on a candidate's check record (for automation fallout)."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    table_map = {
        "identity": "identity_checks",
        "dbs": "dbs_checks",
        "right_to_work": "right_to_work_checks",
        "cv_analysis": "cv_analyses",
        "registration": "registration_checks",
        "references": "references_",
        "employment_history": "employment_history",
        "employment_verification": "employment_verifications",
        "training": "training_certificates",
    }

    if check_type not in table_map:
        raise HTTPException(status_code=400, detail=f"Invalid check_type. Valid: {list(table_map.keys())}")

    table = table_map[check_type]

    # Prevent SQL injection by validating field names against actual columns
    with get_db() as db:
        db.execute(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s AND table_schema = 'public'",
            (table,)
        )
        columns = {row["column_name"] for row in db.fetchall()}
        invalid_fields = set(data.fields.keys()) - columns
        if invalid_fields:
            raise HTTPException(status_code=400, detail=f"Invalid fields: {invalid_fields}. Valid: {columns}")

        # Don't allow editing the id or candidate_id
        protected = {"id", "candidate_id"}
        if set(data.fields.keys()) & protected:
            raise HTTPException(status_code=400, detail="Cannot edit id or candidate_id fields")

        db.execute(f"SELECT * FROM {table} WHERE id=%s AND candidate_id=%s", (check_id, candidate_id))
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Check record not found")

        old_values = dict(row)
        set_clause = ", ".join(f"{k}=%s" for k in data.fields.keys())
        values = list(data.fields.values()) + [check_id]
        db.execute(f"UPDATE {table} SET {set_clause} WHERE id=%s", values)

        # Log the edit
        import json
        changes = {k: {"old": old_values.get(k), "new": v} for k, v in data.fields.items()}
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, f"check_{check_type}", check_id, "admin_edit_check_data",
             current_user["sub"], json.dumps(changes), now))

        # Re-evaluate compliance
        from app.services.compliance_engine import ComplianceEngine
        ComplianceEngine.evaluate_candidate(candidate_id)

        db.execute(f"SELECT * FROM {table} WHERE id=%s", (check_id,))
        updated = db.fetchone()
        return dict(updated)


# ── 8. Re-trigger Employment & Reference Verification Emails ─────

@router.post("/candidates/{candidate_id}/retrigger-reference/{ref_id}")
async def retrigger_reference_verification(
    candidate_id: str, ref_id: str, current_user: dict = Depends(get_current_user)
):
    """Re-trigger a reference verification email."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    # Phase 1: DB reads and status update (close connection before email send)
    with get_db() as db:
        db.execute("SELECT * FROM references_ WHERE id=%s AND candidate_id=%s",
                         (ref_id, candidate_id))
        ref = db.fetchone()
        if not ref:
            raise HTTPException(status_code=404, detail="Reference not found")

        ref_dict = dict(ref)
        reminder_count = (ref_dict.get("reminder_count") or 0) + 1

        # Reset status to pending and increment reminder count
        db.execute(
            "UPDATE references_ SET status='pending', reminder_count=%s, sent_at=%s WHERE id=%s",
            (reminder_count, now, ref_id))

        # Look up candidate name
        db.execute("SELECT first_name, last_name FROM candidates WHERE id=%s",
                          (candidate_id,))
        cand = db.fetchone()
        cand_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Unknown"

        # Look up agency name
        db.execute(
            "SELECT agency_id FROM agency_candidates WHERE candidate_id=%s LIMIT 1",
            (candidate_id,))
        agency_link = db.fetchone()
        agency_name = "Viper AI"
        if agency_link:
            db.execute("SELECT name FROM agencies WHERE id=%s",
                                (dict(agency_link)["agency_id"],))
            agency = db.fetchone()
            if agency:
                agency_name = dict(agency)["name"]

    # Phase 2: Send email (outside DB context to avoid SQLite lock)
    from app.services.email_templates import EmailTemplateService, get_trust_signal_variables

    from app.config import BASE_URL
    reference_link = f"{BASE_URL}/verify?token={ref_dict['token']}&type=reference"
    verification_code = ref_dict.get("verification_code", "")

    email_result = EmailTemplateService.send_email(
        template_key="reference_request",
        recipient_email=ref_dict["referee_email"],
        recipient_name=ref_dict["referee_name"],
        variables={
            "candidate_name": cand_name,
            "referee_name": ref_dict["referee_name"],
            "agency_name": agency_name,
            "verification_code": verification_code,
            "reference_link": reference_link,
            **get_trust_signal_variables(),
        },
    )

    # Phase 3: Audit log (separate DB context)
    import json as _json
    log_id = generate_id()
    details = _json.dumps({
        "referee_email": ref_dict["referee_email"],
        "referee_name": ref_dict["referee_name"],
        "candidate_name": cand_name,
        "reminder_number": reminder_count,
        "email_status": email_result.get("status", "unknown") if email_result else "error",
        "email_provider": email_result.get("provider", "none") if email_result else "none",
    })
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "reference", ref_id, "admin_retrigger_reference",
             current_user["sub"], details, now))

        db.execute("SELECT * FROM references_ WHERE id=%s", (ref_id,))
        updated = db.fetchone()
        return dict(updated)


@router.post("/candidates/{candidate_id}/retrigger-employment/{ver_id}")
async def retrigger_employment_verification(
    candidate_id: str, ver_id: str, current_user: dict = Depends(get_current_user)
):
    """Re-trigger an employment verification email."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    # Phase 1: DB reads and status update (close connection before email send)
    with get_db() as db:
        db.execute("SELECT * FROM employment_verifications WHERE id=%s AND candidate_id=%s",
                         (ver_id, candidate_id))
        ver = db.fetchone()
        if not ver:
            raise HTTPException(status_code=404, detail="Employment verification not found")

        ver_dict = dict(ver)
        reminder_count = (ver_dict.get("reminder_count") or 0) + 1

        # Reset status and increment reminder
        db.execute(
            "UPDATE employment_verifications SET status='pending', reminder_count=%s, sent_at=%s WHERE id=%s",
            (reminder_count, now, ver_id))

        # Look up candidate name
        db.execute("SELECT first_name, last_name FROM candidates WHERE id=%s",
                          (candidate_id,))
        cand = db.fetchone()
        cand_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Unknown"

        # Look up agency name
        db.execute(
            "SELECT agency_id FROM agency_candidates WHERE candidate_id=%s LIMIT 1",
            (candidate_id,))
        agency_link = db.fetchone()
        agency_name = "Viper AI"
        if agency_link:
            db.execute("SELECT name FROM agencies WHERE id=%s",
                                (dict(agency_link)["agency_id"],))
            agency = db.fetchone()
            if agency:
                agency_name = dict(agency)["name"]

        # Look up employment details
        employment_id = ver_dict.get("employment_id", "")
        emp_data = {}
        if employment_id:
            db.execute(
                "SELECT employer_name, job_title, start_date, end_date FROM employment_history WHERE id=%s",
                (employment_id,))
            emp = db.fetchone()
            if emp:
                emp_data = dict(emp)

    # Phase 2: Send email (outside DB context to avoid SQLite lock)
    from app.services.email_templates import EmailTemplateService, get_trust_signal_variables

    from app.config import BASE_URL
    verification_link = f"{BASE_URL}/verify?token={ver_dict['token']}&type=employment"
    verification_code = ver_dict.get("verification_code", "")

    email_result = EmailTemplateService.send_email(
        template_key="employment_verification_request",
        recipient_email=ver_dict["verifier_email"],
        recipient_name=ver_dict["verifier_name"],
        variables={
            "candidate_name": cand_name,
            "verifier_name": ver_dict["verifier_name"],
            "agency_name": agency_name,
            "employer_name": emp_data.get("employer_name", ver_dict.get("employer_name", "")),
            "job_title": emp_data.get("job_title", ""),
            "start_date": emp_data.get("start_date", ""),
            "end_date": emp_data.get("end_date", "Present"),
            "verification_code": verification_code,
            "verification_link": verification_link,
            **get_trust_signal_variables(),
        },
    )

    # Phase 3: Audit log (separate DB context)
    import json as _json
    log_id = generate_id()
    details = _json.dumps({
        "verifier_email": ver_dict["verifier_email"],
        "verifier_name": ver_dict["verifier_name"],
        "candidate_name": cand_name,
        "employer_name": emp_data.get("employer_name", ver_dict.get("employer_name", "")),
        "reminder_number": reminder_count,
        "email_status": email_result.get("status", "unknown") if email_result else "error",
        "email_provider": email_result.get("provider", "none") if email_result else "none",
    })
    with get_db() as db:
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "employment_verification", ver_id, "admin_retrigger_employment",
             current_user["sub"], details, now))

        db.execute("SELECT * FROM employment_verifications WHERE id=%s", (ver_id,))
        updated = db.fetchone()
        return dict(updated)


# ── 9. Get Full Candidate Detail (all checks for admin view) ─────

# ── 8b. Generic re-trigger for stallable checks (CV, Identity, RTW, DBS, Reg, Training, Compliance) ──

_RETRIGGERABLE_CHECKS = {"cv", "identity", "rtw", "dbs", "registration", "training", "references", "compliance"}


@router.post("/candidates/{candidate_id}/retrigger-check/{check_type}")
async def retrigger_candidate_check(
    candidate_id: str,
    check_type: str,
    current_user: dict = Depends(get_current_user),
):
    """Admin re-trigger for any candidate check that may have stalled or failed.

    Loads the candidate's latest draft data for the given section (if any),
    invokes the relevant TriggerEngine._run_* method, then re-evaluates compliance.
    Returns the check result string and an audit entry.
    """
    require_admin(current_user)

    check_type = check_type.lower()
    if check_type not in _RETRIGGERABLE_CHECKS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported check_type '{check_type}'. Supported: {sorted(_RETRIGGERABLE_CHECKS)}",
        )

    now = datetime.now(timezone.utc).isoformat()

    # Load candidate to confirm existence + load relevant draft section data
    section_map = {
        "cv": "cv",
        "identity": "identity",
        "rtw": "rtw",
        "dbs": "dbs",
        "registration": "registration",
        "training": "training",
        "references": "references",
    }
    section_key = section_map.get(check_type)
    section_data: dict = {}
    with get_db() as db:
        db.execute("SELECT id FROM candidates WHERE id=%s", (candidate_id,))
        if not db.fetchone():
            raise HTTPException(status_code=404, detail="Candidate not found")

        if section_key:
            db.execute(
                "SELECT data FROM candidate_draft_data WHERE candidate_id=%s AND section=%s ORDER BY updated_at DESC LIMIT 1",
                (candidate_id, section_key),
            )
            draft = db.fetchone()
            if draft:
                try:
                    import json as _json
                    raw = dict(draft).get("data") or "{}"
                    section_data = _json.loads(raw) if isinstance(raw, str) else (raw or {})
                except Exception:
                    section_data = {}

    # Dispatch to the relevant TriggerEngine method (outside DB context — each method manages its own)
    from app.services.trigger_engine import TriggerEngine
    from app.services.compliance_engine import ComplianceEngine

    result: str
    try:
        if check_type == "cv":
            result = TriggerEngine._run_cv(candidate_id, section_data)
        elif check_type == "identity":
            result = TriggerEngine._run_identity(candidate_id, section_data)
        elif check_type == "rtw":
            result = TriggerEngine._run_rtw(candidate_id, section_data)
        elif check_type == "dbs":
            result = TriggerEngine._run_dbs(candidate_id, section_data)
        elif check_type == "registration":
            result = TriggerEngine._run_registration(candidate_id, section_data)
        elif check_type == "training":
            result = TriggerEngine._run_training(candidate_id, section_data)
        elif check_type == "references":
            # Also re-send any outstanding employment verification emails
            ref_result = TriggerEngine._run_references(candidate_id, section_data)
            emp_result = TriggerEngine._run_employment_verifications(candidate_id)
            result = f"references: {ref_result}; employment: {emp_result}"
        elif check_type == "compliance":
            # Just re-evaluate compliance without re-running any individual check
            result = "compliance re-evaluation requested"
        else:
            result = "unsupported"
    except Exception as e:
        result = f"error: {e}"

    # Re-evaluate compliance regardless (safe — idempotent)
    try:
        ComplianceEngine.evaluate_candidate(candidate_id)
    except Exception as e:
        result = f"{result}; compliance_error: {e}"

    # Audit log
    import json as _json
    log_id = generate_id()
    details = _json.dumps({"check_type": check_type, "result": result, "had_draft": bool(section_data)})
    try:
        with get_db() as db:
            db.execute(
                "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (log_id, "candidate_check", candidate_id, f"admin_retrigger_{check_type}",
                 current_user["sub"], details, now),
            )
    except Exception:
        pass

    return {"candidate_id": candidate_id, "check_type": check_type, "result": result, "triggered_at": now}


@router.get("/candidates/{candidate_id}/full-detail")
async def get_candidate_full_detail(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get all check data for a candidate (admin detail view)."""
    require_admin(current_user)

    with get_db() as db:
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        cand = db.fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        db.execute("SELECT * FROM identity_checks WHERE candidate_id=%s", (candidate_id,))
        identity = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM dbs_checks WHERE candidate_id=%s", (candidate_id,))
        dbs = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM right_to_work_checks WHERE candidate_id=%s", (candidate_id,))
        rtw = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM cv_analyses WHERE candidate_id=%s", (candidate_id,))
        cv = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM registration_checks WHERE candidate_id=%s", (candidate_id,))
        reg = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM references_ WHERE candidate_id=%s", (candidate_id,))
        refs = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM employment_history WHERE candidate_id=%s", (candidate_id,))
        emp_history = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM employment_verifications WHERE candidate_id=%s", (candidate_id,))
        emp_ver = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM training_certificates WHERE candidate_id=%s", (candidate_id,))
        training = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM compliance_records WHERE candidate_id=%s", (candidate_id,))
        compliance = db.fetchone()
        db.execute("SELECT * FROM monitoring_alerts WHERE candidate_id=%s AND is_resolved=0", (candidate_id,))
        alerts = [dict(r) for r in db.fetchall()]
        db.execute("SELECT * FROM fraud_flags WHERE candidate_id=%s AND is_resolved=0", (candidate_id,))
        fraud = [dict(r) for r in db.fetchall()]

        # TrustID checks
        db.execute("SELECT * FROM trustid_checks WHERE candidate_id=%s ORDER BY created_at DESC", (candidate_id,))
        trustid = [dict(r) for r in db.fetchall()]

        # Agency associations
        db.execute(
            """SELECT a.id, a.name, a.email, ac.employment_status, ac.assigned_at
               FROM agencies a JOIN agency_candidates ac ON a.id = ac.agency_id
               WHERE ac.candidate_id=%s""", (candidate_id,))
        agencies_linked = db.fetchall()

        # AI Analysis Results
        ai_cv_analyses = []
        ai_ref_analyses = []
        ai_anomalies = []
        try:
            db.execute("SELECT * FROM ai_cv_gap_analyses WHERE candidate_id=%s ORDER BY created_at DESC", (candidate_id,))
            ai_cv_rows = db.fetchall()
            for r in ai_cv_rows:
                d = dict(r)
                try:
                    import json as _json
                    d["result"] = _json.loads(d.pop("result_json", "{}"))
                except Exception:
                    d["result"] = {}
                ai_cv_analyses.append(d)
        except Exception:
            pass
        try:
            db.execute("SELECT * FROM ai_reference_analyses WHERE candidate_id=%s ORDER BY created_at DESC", (candidate_id,))
            ai_ref_rows = db.fetchall()
            for r in ai_ref_rows:
                d = dict(r)
                try:
                    import json as _json
                    d["result"] = _json.loads(d.pop("result_json", "{}"))
                except Exception:
                    d["result"] = {}
                ai_ref_analyses.append(d)
        except Exception:
            pass
        try:
            db.execute(
                """SELECT * FROM ai_anomaly_scans ORDER BY created_at DESC LIMIT 1"""
            )
            anomaly_scan = db.fetchone()
            if anomaly_scan:
                d = dict(anomaly_scan)
                try:
                    import json as _json
                    scan_data = _json.loads(d.get("result_json", "{}"))
                    candidate_anomalies = [
                        a for a in scan_data.get("anomalies", [])
                        if a.get("candidate_id") == candidate_id
                    ]
                    if candidate_anomalies:
                        ai_anomalies = candidate_anomalies
                except Exception:
                    pass
        except Exception:
            pass

        return {
            "candidate": dict(cand),
            "identity_checks": identity,
            "dbs_checks": dbs,
            "right_to_work_checks": rtw,
            "cv_analyses": cv,
            "registration_checks": reg,
            "references": refs,
            "employment_history": emp_history,
            "employment_verifications": emp_ver,
            "training_certificates": training,
            "trustid_checks": trustid,
            "compliance": dict(compliance) if compliance else None,
            "active_alerts": alerts,
            "fraud_flags": fraud,
            "agencies": [dict(r) for r in agencies_linked],
            "ai_cv_gap_analyses": ai_cv_analyses,
            "ai_reference_analyses": ai_ref_analyses,
            "ai_anomalies": ai_anomalies,
        }


# ── 10. Candidates with Monitoring Status ────────────────────────

@router.get("/candidates-monitoring")
async def get_candidates_monitoring_status(current_user: dict = Depends(get_current_user)):
    """Get all candidates with their annual monitoring subscription status."""
    require_admin(current_user)

    with get_db() as db:
        db.execute(
            """SELECT c.id, c.first_name, c.last_name, c.email, c.compliance_score,
                      c.compliance_status, c.created_at,
                      ac.annual_monitoring, ac.vetting_cost_accepted, ac.monitoring_cost_accepted,
                      ac.employment_status, ac.agency_id,
                      a.name as agency_name
               FROM candidates c
               JOIN agency_candidates ac ON c.id = ac.candidate_id
               LEFT JOIN agencies a ON ac.agency_id = a.id
               ORDER BY ac.annual_monitoring DESC, c.last_name ASC"""
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


# ── 11. Agency Discount Management ───────────────────────────────

class AgencyDiscountUpdate(BaseModel):
    discount_percent: float  # 0-100


@router.put("/agencies/{agency_id}/discount")
async def update_agency_discount(
    agency_id: str, data: AgencyDiscountUpdate, current_user: dict = Depends(get_current_user)
):
    """Set a discount percentage for a specific agency."""
    require_admin(current_user)
    if data.discount_percent < 0 or data.discount_percent > 100:
        raise HTTPException(status_code=400, detail="Discount must be between 0 and 100")

    with get_db() as db:
        db.execute("SELECT id, name FROM agencies WHERE id=%s", (agency_id,))
        agency = db.fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")
        db.execute("UPDATE agencies SET discount_percent=%s WHERE id=%s", (data.discount_percent, agency_id))
        # Log audit
        db.execute(
            "INSERT INTO audit_logs (id, action, entity_type, entity_id, performed_by, details, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (generate_id(), "set_discount", "agency", agency_id, current_user["sub"],
             f"Set discount to {data.discount_percent}%", datetime.now(timezone.utc).isoformat()),
        )
    return {"status": "ok", "agency_id": agency_id, "discount_percent": data.discount_percent}


@router.get("/agencies/{agency_id}/discount")
async def get_agency_discount(agency_id: str, current_user: dict = Depends(get_current_user)):
    """Get the discount percentage for a specific agency."""
    require_admin(current_user)
    with get_db() as db:
        db.execute("SELECT discount_percent FROM agencies WHERE id=%s", (agency_id,))
        row = db.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Agency not found")
        return {"agency_id": agency_id, "discount_percent": dict(row).get("discount_percent", 0) or 0}


# ── 12. Partial Invoice Adjustment ──────────────────────────────

class InvoiceAdjustment(BaseModel):
    adjusted_amount: float
    adjustment_notes: Optional[str] = None


@router.put("/invoices/{invoice_id}/adjust")
async def adjust_invoice(
    invoice_id: str, data: InvoiceAdjustment, current_user: dict = Depends(get_current_user)
):
    """Adjust an invoice amount (for partial completion — charge only for completed checks)."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
        inv = db.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        inv_dict = dict(inv)
        if data.adjusted_amount < 0:
            raise HTTPException(status_code=400, detail="Adjusted amount cannot be negative")
        if data.adjusted_amount > inv_dict["sell_amount"]:
            raise HTTPException(status_code=400, detail="Adjusted amount cannot exceed original amount")

        db.execute(
            "UPDATE invoices SET adjusted_amount=%s, adjustment_notes=%s WHERE id=%s",
            (data.adjusted_amount, data.adjustment_notes, invoice_id),
        )
        # Log audit
        db.execute(
            "INSERT INTO audit_logs (id, action, entity_type, entity_id, actor, details, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (generate_id(), "adjust_invoice", "invoice", invoice_id, current_user["sub"],
             f"Adjusted from £{inv_dict['sell_amount']:.2f} to £{data.adjusted_amount:.2f}: {data.adjustment_notes or 'N/A'}", now),
        )
    return {"status": "ok", "invoice_id": invoice_id, "original_amount": inv_dict["sell_amount"],
            "adjusted_amount": data.adjusted_amount, "notes": data.adjustment_notes}


@router.get("/invoices")
async def list_all_invoices(current_user: dict = Depends(get_current_user)):
    """List all invoices with agency details for admin invoicing view."""
    require_admin(current_user)
    with get_db() as db:
        db.execute(
            """SELECT i.*, a.name as agency_name, a.discount_percent
               FROM invoices i
               LEFT JOIN agencies a ON i.agency_id = a.id
               ORDER BY i.created_at DESC"""
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


@router.put("/invoices/{invoice_id}/status")
async def update_invoice_status(
    invoice_id: str, current_user: dict = Depends(get_current_user)
):
    """Mark an invoice as paid."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("SELECT id FROM invoices WHERE id=%s", (invoice_id,))
        inv = db.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        db.execute("UPDATE invoices SET status='paid', paid_at=%s WHERE id=%s", (now, invoice_id))
    return {"status": "ok", "invoice_id": invoice_id}


# ── 13. Agency Billing Mode Toggle ─────────────────────────────────

class BillingModeUpdate(BaseModel):
    billing_mode: str  # manual_invoicing, online_payment, subscription
    stripe_customer_id: Optional[str] = None


@router.put("/agencies/{agency_id}/billing-mode")
async def update_agency_billing_mode(
    agency_id: str, data: BillingModeUpdate, current_user: dict = Depends(get_current_user)
):
    """Admin toggles an agency's billing mode between manual_invoicing, online_payment, and subscription."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    from app.services.billing import BillingService
    try:
        result = BillingService.set_agency_billing_mode(
            agency_id, data.billing_mode, data.stripe_customer_id
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Log the action
    with get_db() as db:
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (log_id, "agency", agency_id, "billing_mode_changed",
             current_user["sub"], f"Billing mode set to '{data.billing_mode}'", now))

    return result


@router.get("/agencies/{agency_id}/billing-mode")
async def get_agency_billing_mode(
    agency_id: str, current_user: dict = Depends(get_current_user)
):
    """Get an agency's billing mode."""
    require_admin(current_user)
    from app.services.billing import BillingService
    return BillingService.get_agency_billing_mode(agency_id)


@router.post("/billing/send-reminders")
async def trigger_payment_reminders(current_user: dict = Depends(get_current_user)):
    """Admin manually triggers payment reminders for all overdue invoices."""
    require_admin(current_user)
    from app.services.billing import BillingService
    reminders = BillingService.send_payment_reminders()
    return {"reminders_sent": len(reminders), "details": reminders}


# ── 14. Bulk CQC Audit Pack (multi-candidate) ────────────────────

@router.post("/audit/bulk")
async def generate_bulk_audit_pack(
    candidate_ids: List[str],
    current_user: dict = Depends(get_current_user),
):
    """Generate a combined CQC audit pack PDF for multiple candidates."""
    require_admin(current_user)
    from app.services.audit_pack import AuditPackService
    import io
    from fastapi.responses import StreamingResponse

    try:
        pdf_bytes = AuditPackService.generate_bulk_audit(candidate_ids)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=bulk_audit_pack.pdf"},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate bulk audit pack: {str(e)}")


# ── Refund approval (PAYG / online_payment paid invoices) ─────────────

@router.get("/refund-requests")
async def list_refund_requests(current_user: dict = Depends(get_current_user)):
    """List invoices awaiting admin approval for refund (from revoked invites)."""
    require_admin(current_user)
    with get_db() as db:
        db.execute(
            """SELECT i.*, a.name AS agency_name, inv.candidate_email
               FROM invoices i
               LEFT JOIN agencies a ON a.id = i.agency_id
               LEFT JOIN agency_invites inv ON inv.id = i.invite_id
               WHERE i.refund_status='pending_admin_approval'
               ORDER BY i.refund_requested_at DESC"""
        )
        return [dict(r) for r in db.fetchall()]


class RefundDecision(BaseModel):
    action: str  # "approve" | "decline"
    notes: Optional[str] = None


@router.post("/invoices/{invoice_id}/refund-decision")
async def decide_refund(
    invoice_id: str,
    data: RefundDecision,
    current_user: dict = Depends(get_current_user),
):
    """Approve or decline a pending PAYG refund request.

    On approval we attempt a real Stripe refund via the configured provider using
    the invoice's stored `stripe_payment_intent_id` (or `stripe_session_id` as a
    fallback). The refund outcome is persisted to the invoice and a
    payment_transactions row is written for audit.
    """
    require_admin(current_user)
    if data.action not in ("approve", "decline"):
        raise HTTPException(status_code=400, detail="action must be approve or decline")
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute("SELECT * FROM invoices WHERE id=%s", (invoice_id,))
        inv = db.fetchone()
        if not inv:
            raise HTTPException(status_code=404, detail="Invoice not found")
        inv_d = dict(inv)
        if inv_d.get("refund_status") != "pending_admin_approval":
            raise HTTPException(status_code=400, detail="Invoice is not awaiting refund approval")

    if data.action == "decline":
        with get_db() as db:
            db.execute(
                """UPDATE invoices
                   SET refund_status='declined', refund_resolved_at=%s, refund_resolved_by=%s
                   WHERE id=%s""",
                (now, current_user.get("sub"), invoice_id),
            )
        return {"status": "declined", "invoice_id": invoice_id}

    # ── Approve: call Stripe Refund ──
    from app.services.payment_providers import PaymentProviderService

    payment_ref = inv_d.get("stripe_payment_intent_id") or inv_d.get("stripe_session_id")
    amount = float(inv_d.get("sell_amount") or inv_d.get("amount") or 0)
    currency = (inv_d.get("currency") or "GBP").upper()

    refund_result: dict = {"success": False, "error": "no_payment_reference"}
    if payment_ref:
        provider_config = PaymentProviderService.get_provider("stripe")
        if provider_config and provider_config.get("api_key_encrypted"):
            refund_result = PaymentProviderService._stripe_refund(
                provider_config["api_key_encrypted"],
                payment_ref,
                amount,
                currency,
            )
        else:
            refund_result = {"success": False, "error": "stripe_provider_not_configured"}

    with get_db() as db:
        if refund_result.get("success"):
            db.execute(
                """UPDATE invoices
                   SET status='cancelled', refund_status='refunded',
                       cancelled_at=%s, refund_resolved_at=%s, refund_resolved_by=%s
                   WHERE id=%s""",
                (now, now, current_user.get("sub"), invoice_id),
            )
            # Audit row in payment_transactions so the refund is traceable.
            try:
                import json as _json
                db.execute(
                    """INSERT INTO payment_transactions
                       (id, agency_id, invoice_id, provider, payment_type, amount, currency,
                        status, provider_payment_id, metadata_json, created_at, completed_at)
                       VALUES (%s, %s, %s, 'stripe', 'refund', %s, %s, 'completed', %s, %s, %s, %s)""",
                    (generate_id(), inv_d.get("agency_id"), invoice_id,
                     amount, currency,
                     refund_result.get("refund_id", ""),
                     _json.dumps({"invoice_id": invoice_id, "approved_by": current_user.get("sub")}),
                     now, now),
                )
            except Exception:
                pass
            return {
                "status": "refunded",
                "invoice_id": invoice_id,
                "stripe_refund_id": refund_result.get("refund_id"),
            }
        else:
            # Mark the attempt but leave the invoice in pending_admin_approval so
            # the admin can retry after fixing config / payment reference.
            db.execute(
                """UPDATE invoices
                   SET refund_status='pending_admin_approval',
                       refund_resolved_at=%s
                   WHERE id=%s""",
                (now, invoice_id),
            )
            raise HTTPException(
                status_code=502,
                detail=f"Stripe refund failed: {refund_result.get('error', 'unknown error')}",
            )


# ── Admin Impersonation / "View As" ─────────────────────────────
# Allows admins to see the platform as a specific candidate or agency user.
# Every impersonation session is fully audit-logged.


class ImpersonateRequest(BaseModel):
    target_user_id: str
    target_user_type: str  # "candidate" or "agency"
    reason: str


@router.post("/impersonate")
async def admin_impersonate(
    body: ImpersonateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Generate a short-lived token to view the platform as another user.

    The token carries an 'imp' (impersonator) claim so all actions are
    attributable to the admin who initiated the session.
    """
    require_admin(current_user)
    admin_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()

    if body.target_user_type not in ("candidate", "agency"):
        raise HTTPException(status_code=400, detail="target_user_type must be 'candidate' or 'agency'")

    with get_db() as db:
        # Verify target user exists
        if body.target_user_type == "candidate":
            db.execute("SELECT id, email, first_name, last_name FROM candidates WHERE id=%s", (body.target_user_id,))
        else:
            db.execute("SELECT id, email, name FROM agencies WHERE id=%s", (body.target_user_id,))

        target = db.fetchone()
        if not target:
            raise HTTPException(status_code=404, detail=f"{body.target_user_type} not found")
        target = dict(target)

        # Create impersonation token (15 min, carries admin's ID in 'imp' claim)
        token = create_access_token(
            body.target_user_id,
            body.target_user_type,
            impersonator_id=admin_id,
        )

        # Audit log the impersonation
        log_id = generate_id()
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                log_id,
                body.target_user_type,
                body.target_user_id,
                "admin_impersonation_started",
                admin_id,
                f"Admin {admin_id} started impersonation of {body.target_user_type} "
                f"{body.target_user_id} ({target.get('email', 'unknown')}). Reason: {body.reason}",
                now,
            ),
        )

        return {
            "access_token": token,
            "user_id": body.target_user_id,
            "user_type": body.target_user_type,
            "impersonator": admin_id,
            "expires_in_minutes": 15,
        }


@router.post("/impersonate/end")
async def admin_end_impersonation(
    current_user: dict = Depends(get_current_user),
):
    """Log the end of an impersonation session.

    Called by the frontend when the admin exits view-as mode. The 'imp' claim
    in the token identifies who was impersonating.
    """
    impersonator_id = current_user.get("imp")
    if not impersonator_id:
        raise HTTPException(status_code=400, detail="Not in an impersonation session")

    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        log_id = generate_id()
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (
                log_id,
                current_user.get("type", "unknown"),
                current_user["sub"],
                "admin_impersonation_ended",
                impersonator_id,
                f"Admin {impersonator_id} ended impersonation of {current_user['sub']}",
                now,
            ),
        )

    return {"status": "impersonation_ended"}


@router.get("/impersonation-log")
async def admin_get_impersonation_log(
    current_user: dict = Depends(get_current_user),
):
    """Retrieve all impersonation audit entries for compliance review."""
    require_admin(current_user)

    with get_db() as db:
        db.execute(
            """SELECT id, entity_type, entity_id, action, actor, details, created_at
               FROM audit_logs
               WHERE action IN ('admin_impersonation_started', 'admin_impersonation_ended')
               ORDER BY created_at DESC
               LIMIT 200"""
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]
