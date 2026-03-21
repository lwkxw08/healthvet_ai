"""Extended admin routes: override checks, suspend agencies, edit candidates,
manage users, alert settings, audit log viewer, edit entry data, re-trigger verifications."""
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.database import get_db
from app.utils.auth import get_current_user, generate_id, hash_password

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
        cand = db.execute("SELECT id FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Find existing check record(s)
        rows = db.execute(f"SELECT id FROM {table} WHERE candidate_id=?", (candidate_id,)).fetchall()

        if rows:
            # Update the most recent check
            row_id = dict(rows[-1])["id"]
            db.execute(f"UPDATE {table} SET {status_col}=?, {date_col}=? WHERE id=?",
                       (data.status, now, row_id))
            # For identity checks, also set result field
            if data.check_type == "identity":
                db.execute("UPDATE identity_checks SET result=? WHERE id=?", (data.status, row_id))
            if data.check_type == "dbs":
                db.execute("UPDATE dbs_checks SET result=? WHERE id=?", (data.status, row_id))
            if data.check_type == "right_to_work":
                db.execute("UPDATE right_to_work_checks SET verified=? WHERE id=?",
                           (1 if data.status in ("verified", "clear", "completed") else 0, row_id))
            if data.check_type == "registration":
                db.execute("UPDATE registration_checks SET is_active=?, result=? WHERE id=?",
                           (1 if data.status in ("active", "verified", "clear") else 0, data.status, row_id))
        else:
            # Create a new check record with the overridden status
            new_id = generate_id()
            if data.check_type == "identity":
                db.execute(
                    "INSERT INTO identity_checks (id, candidate_id, status, result, completed_at) VALUES (?,?,?,?,?)",
                    (new_id, candidate_id, data.status, data.status, now))
            elif data.check_type == "dbs":
                db.execute(
                    "INSERT INTO dbs_checks (id, candidate_id, status, result, completed_at) VALUES (?,?,?,?,?)",
                    (new_id, candidate_id, data.status, data.status, now))
            elif data.check_type == "right_to_work":
                verified = 1 if data.status in ("verified", "clear", "completed") else 0
                db.execute(
                    "INSERT INTO right_to_work_checks (id, candidate_id, status, verified, checked_at) VALUES (?,?,?,?,?)",
                    (new_id, candidate_id, data.status, verified, now))
            elif data.check_type == "cv_analysis":
                db.execute(
                    "INSERT INTO cv_analyses (id, candidate_id, status, analysed_at) VALUES (?,?,?,?)",
                    (new_id, candidate_id, data.status, now))
            elif data.check_type == "registration":
                is_active = 1 if data.status in ("active", "verified", "clear") else 0
                db.execute(
                    "INSERT INTO registration_checks (id, candidate_id, body, status, is_active, result, last_checked) VALUES (?,?,?,?,?,?,?)",
                    (new_id, candidate_id, "NMC", data.status, is_active, data.status, now))
            elif data.check_type == "references":
                db.execute(
                    "INSERT INTO references_ (id, candidate_id, referee_name, referee_email, status, completed_at) VALUES (?,?,?,?,?,?)",
                    (new_id, candidate_id, "Admin Override", "admin@override", data.status, now))
            elif data.check_type == "employment":
                db.execute(
                    "INSERT INTO employment_verifications (id, candidate_id, employment_id, verifier_name, verifier_email, status, completed_at) VALUES (?,?,?,?,?,?,?)",
                    (new_id, candidate_id, "admin-override", "Admin Override", "admin@override", data.status, now))

        # Log the override action
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
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
        agency = db.execute("SELECT * FROM agencies WHERE id=?", (agency_id,)).fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")

        db.execute("UPDATE agencies SET status=? WHERE id=?", (data.status, agency_id))

        # Log the action
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "agency", agency_id, f"status_changed_to_{data.status}",
             current_user["sub"], data.reason or "", now))

        row = db.execute("SELECT * FROM agencies WHERE id=?", (agency_id,)).fetchone()
        return dict(row)


@router.get("/agencies")
async def list_agencies(current_user: dict = Depends(get_current_user)):
    """List all agencies with their status."""
    require_admin(current_user)
    with get_db() as db:
        rows = db.execute("""
            SELECT a.*,
                   (SELECT COUNT(*) FROM agency_candidates ac WHERE ac.agency_id = a.id) as candidate_count
            FROM agencies a ORDER BY a.created_at DESC
        """).fetchall()
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
        cand = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        old_values = dict(cand)
        updates["updated_at"] = now
        set_clause = ", ".join(f"{k}=?" for k in updates.keys())
        values = list(updates.values()) + [candidate_id]
        db.execute(f"UPDATE candidates SET {set_clause} WHERE id=?", values)

        # Log the changes
        changes = {k: {"old": old_values.get(k), "new": v} for k, v in updates.items() if k != "updated_at" and old_values.get(k) != v}
        log_id = generate_id()
        import json
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "candidate", candidate_id, "admin_edit_profile",
             current_user["sub"], json.dumps(changes), now))

        row = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
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
        existing = db.execute("SELECT id FROM agencies WHERE email=?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Agency with this email already exists")

        db.execute(
            "INSERT INTO agencies (id, name, email, password_hash, contact_name, phone, plan, status, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (agency_id, data.name, data.email, hash_password(data.password),
             data.contact_name, data.phone, data.plan, "active", now))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "agency", agency_id, "admin_created_agency", current_user["sub"], f"Created agency: {data.name}", now))

        row = db.execute("SELECT * FROM agencies WHERE id=?", (agency_id,)).fetchone()
        return dict(row)


@router.post("/candidates/create")
async def admin_create_candidate(data: CreateCandidateRequest, current_user: dict = Depends(get_current_user)):
    """Admin create a new candidate account."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()
    cand_id = generate_id()

    with get_db() as db:
        existing = db.execute("SELECT id FROM candidates WHERE email=?", (data.email,)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Candidate with this email already exists")

        db.execute(
            "INSERT INTO candidates (id, email, password_hash, first_name, last_name, phone, profession, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (cand_id, data.email, hash_password(data.password),
             data.first_name, data.last_name, data.phone, data.profession, now, now))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "candidate", cand_id, "admin_created_candidate", current_user["sub"], f"Created candidate: {data.first_name} {data.last_name}", now))

        row = db.execute("SELECT * FROM candidates WHERE id=?", (cand_id,)).fetchone()
        return dict(row)


@router.delete("/agencies/{agency_id}")
async def admin_delete_agency(agency_id: str, current_user: dict = Depends(get_current_user)):
    """Admin delete an agency account."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        agency = db.execute("SELECT * FROM agencies WHERE id=?", (agency_id,)).fetchone()
        if not agency:
            raise HTTPException(status_code=404, detail="Agency not found")

        agency_name = dict(agency)["name"]
        # Remove agency-candidate links
        db.execute("DELETE FROM agency_candidates WHERE agency_id=?", (agency_id,))
        db.execute("DELETE FROM agency_invites WHERE agency_id=?", (agency_id,))
        db.execute("DELETE FROM agency_subscriptions WHERE agency_id=?", (agency_id,))
        db.execute("DELETE FROM agencies WHERE id=?", (agency_id,))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "agency", agency_id, "admin_deleted_agency", current_user["sub"], f"Deleted agency: {agency_name}", now))

        return {"status": "deleted", "agency_id": agency_id, "name": agency_name}


@router.delete("/candidates/{candidate_id}")
async def admin_delete_candidate(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Admin delete a candidate account and all related data."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        cand = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        cand_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}"
        # Remove all related data
        for tbl in ["identity_checks", "right_to_work_checks", "dbs_checks", "cv_analyses",
                     "registration_checks", "references_", "compliance_records", "monitoring_alerts",
                     "employment_history", "employment_verifications", "training_certificates", "fraud_flags"]:
            db.execute(f"DELETE FROM {tbl} WHERE candidate_id=?", (candidate_id,))
        db.execute("DELETE FROM agency_candidates WHERE candidate_id=?", (candidate_id,))
        db.execute("DELETE FROM candidates WHERE id=?", (candidate_id,))

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "candidate", candidate_id, "admin_deleted_candidate", current_user["sub"], f"Deleted candidate: {cand_name}", now))

        return {"status": "deleted", "candidate_id": candidate_id, "name": cand_name}


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
        rows = db.execute("SELECT * FROM alert_settings ORDER BY setting_key").fetchall()
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
            existing = db.execute("SELECT id FROM alert_settings WHERE setting_key=?", (key,)).fetchone()
            if existing:
                db.execute("UPDATE alert_settings SET setting_value=?, updated_at=? WHERE setting_key=?",
                           (value, now, key))
            else:
                db.execute("INSERT INTO alert_settings (id, setting_key, setting_value, updated_at) VALUES (?,?,?,?)",
                           (generate_id(), key, value, now))

        log_id = generate_id()
        import json
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "settings", "alert_settings", "update_alert_settings",
             current_user["sub"], json.dumps(updates), now))

        # Return updated settings
        rows = db.execute("SELECT * FROM alert_settings ORDER BY setting_key").fetchall()
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
            query += " AND entity_type=?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id=?"
            params.append(entity_id)
        if action:
            query += " AND action LIKE ?"
            params.append(f"%{action}%")

        # Get total count
        count_query = query.replace("SELECT *", "SELECT COUNT(*) as cnt")
        total = dict(db.execute(count_query, params).fetchone())["cnt"]

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = db.execute(query, params).fetchall()
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
        columns = {row[1] for row in db.execute(f"PRAGMA table_info({table})").fetchall()}
        invalid_fields = set(data.fields.keys()) - columns
        if invalid_fields:
            raise HTTPException(status_code=400, detail=f"Invalid fields: {invalid_fields}. Valid: {columns}")

        # Don't allow editing the id or candidate_id
        protected = {"id", "candidate_id"}
        if set(data.fields.keys()) & protected:
            raise HTTPException(status_code=400, detail="Cannot edit id or candidate_id fields")

        row = db.execute(f"SELECT * FROM {table} WHERE id=? AND candidate_id=?", (check_id, candidate_id)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Check record not found")

        old_values = dict(row)
        set_clause = ", ".join(f"{k}=?" for k in data.fields.keys())
        values = list(data.fields.values()) + [check_id]
        db.execute(f"UPDATE {table} SET {set_clause} WHERE id=?", values)

        # Log the edit
        import json
        changes = {k: {"old": old_values.get(k), "new": v} for k, v in data.fields.items()}
        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, f"check_{check_type}", check_id, "admin_edit_check_data",
             current_user["sub"], json.dumps(changes), now))

        # Re-evaluate compliance
        from app.services.compliance_engine import ComplianceEngine
        ComplianceEngine.evaluate_candidate(candidate_id)

        updated = db.execute(f"SELECT * FROM {table} WHERE id=?", (check_id,)).fetchone()
        return dict(updated)


# ── 8. Re-trigger Employment & Reference Verification Emails ─────

@router.post("/candidates/{candidate_id}/retrigger-reference/{ref_id}")
async def retrigger_reference_verification(
    candidate_id: str, ref_id: str, current_user: dict = Depends(get_current_user)
):
    """Re-trigger a reference verification email."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        ref = db.execute("SELECT * FROM references_ WHERE id=? AND candidate_id=?",
                         (ref_id, candidate_id)).fetchone()
        if not ref:
            raise HTTPException(status_code=404, detail="Reference not found")

        ref_dict = dict(ref)

        # Reset status to pending and increment reminder count
        db.execute(
            "UPDATE references_ SET status='pending', reminder_count=reminder_count+1, sent_at=? WHERE id=?",
            (now, ref_id))

        # Simulate sending the email
        from app.services.email_service import EmailService
        cand = db.execute("SELECT first_name, last_name FROM candidates WHERE id=?",
                          (candidate_id,)).fetchone()
        cand_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Unknown"

        EmailService.send_notification(
            recipient_email=ref_dict["referee_email"],
            recipient_name=ref_dict["referee_name"],
            subject=f"Reference Request Reminder - {cand_name}",
            body=f"This is a reminder to complete the reference verification for {cand_name}. Token: {ref_dict['token']}",
            notification_type="reference_reminder",
            related_id=ref_id,
        )

        # Now auto-complete the reference (simulated)
        from app.services.reference_automation import ReferenceAutomationService
        responses = {
            "job_title_confirmed": True,
            "dates_confirmed": True,
            "performance_rating": 4,
            "would_rehire": True,
            "concerns": "None",
            "additional_comments": "Re-triggered by admin",
        }
        ReferenceAutomationService.submit_reference(ref_dict["token"], responses, "127.0.0.1")

        # Re-evaluate compliance
        from app.services.compliance_engine import ComplianceEngine
        ComplianceEngine.evaluate_candidate(candidate_id)

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "reference", ref_id, "admin_retrigger_reference",
             current_user["sub"], f"Re-triggered reference for {ref_dict['referee_email']}", now))

        updated = db.execute("SELECT * FROM references_ WHERE id=?", (ref_id,)).fetchone()
        return dict(updated)


@router.post("/candidates/{candidate_id}/retrigger-employment/{ver_id}")
async def retrigger_employment_verification(
    candidate_id: str, ver_id: str, current_user: dict = Depends(get_current_user)
):
    """Re-trigger an employment verification email."""
    require_admin(current_user)
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        ver = db.execute("SELECT * FROM employment_verifications WHERE id=? AND candidate_id=?",
                         (ver_id, candidate_id)).fetchone()
        if not ver:
            raise HTTPException(status_code=404, detail="Employment verification not found")

        ver_dict = dict(ver)

        # Reset status and increment reminder
        db.execute(
            "UPDATE employment_verifications SET status='pending', reminder_count=reminder_count+1, sent_at=? WHERE id=?",
            (now, ver_id))

        # Send reminder email
        from app.services.email_service import EmailService
        cand = db.execute("SELECT first_name, last_name FROM candidates WHERE id=?",
                          (candidate_id,)).fetchone()
        cand_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Unknown"

        EmailService.send_notification(
            recipient_email=ver_dict["verifier_email"],
            recipient_name=ver_dict["verifier_name"],
            subject=f"Employment Verification Reminder - {cand_name}",
            body=f"This is a reminder to complete the employment verification for {cand_name} at {ver_dict.get('employer_name', 'your organization')}.",
            notification_type="employment_verification_reminder",
            related_id=ver_id,
        )

        # Auto-complete the verification (simulated)
        db.execute(
            """UPDATE employment_verifications SET status='completed', job_title_confirmed=1,
               dates_confirmed=1, reason_for_leaving_confirmed='Re-triggered by admin',
               additional_comments='Admin re-triggered verification', completed_at=? WHERE id=?""",
            (now, ver_id))

        # Re-evaluate compliance
        from app.services.compliance_engine import ComplianceEngine
        ComplianceEngine.evaluate_candidate(candidate_id)

        log_id = generate_id()
        db.execute(
            "INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at) VALUES (?,?,?,?,?,?,?)",
            (log_id, "employment_verification", ver_id, "admin_retrigger_employment",
             current_user["sub"], f"Re-triggered employment verification for {ver_dict['verifier_email']}", now))

        updated = db.execute("SELECT * FROM employment_verifications WHERE id=?", (ver_id,)).fetchone()
        return dict(updated)


# ── 9. Get Full Candidate Detail (all checks for admin view) ─────

@router.get("/candidates/{candidate_id}/full-detail")
async def get_candidate_full_detail(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get all check data for a candidate (admin detail view)."""
    require_admin(current_user)

    with get_db() as db:
        cand = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not cand:
            raise HTTPException(status_code=404, detail="Candidate not found")

        identity = [dict(r) for r in db.execute("SELECT * FROM identity_checks WHERE candidate_id=?", (candidate_id,)).fetchall()]
        dbs = [dict(r) for r in db.execute("SELECT * FROM dbs_checks WHERE candidate_id=?", (candidate_id,)).fetchall()]
        rtw = [dict(r) for r in db.execute("SELECT * FROM right_to_work_checks WHERE candidate_id=?", (candidate_id,)).fetchall()]
        cv = [dict(r) for r in db.execute("SELECT * FROM cv_analyses WHERE candidate_id=?", (candidate_id,)).fetchall()]
        reg = [dict(r) for r in db.execute("SELECT * FROM registration_checks WHERE candidate_id=?", (candidate_id,)).fetchall()]
        refs = [dict(r) for r in db.execute("SELECT * FROM references_ WHERE candidate_id=?", (candidate_id,)).fetchall()]
        emp_history = [dict(r) for r in db.execute("SELECT * FROM employment_history WHERE candidate_id=?", (candidate_id,)).fetchall()]
        emp_ver = [dict(r) for r in db.execute("SELECT * FROM employment_verifications WHERE candidate_id=?", (candidate_id,)).fetchall()]
        training = [dict(r) for r in db.execute("SELECT * FROM training_certificates WHERE candidate_id=?", (candidate_id,)).fetchall()]
        compliance = db.execute("SELECT * FROM compliance_records WHERE candidate_id=?", (candidate_id,)).fetchone()
        alerts = [dict(r) for r in db.execute("SELECT * FROM monitoring_alerts WHERE candidate_id=? AND is_resolved=0", (candidate_id,)).fetchall()]
        fraud = [dict(r) for r in db.execute("SELECT * FROM fraud_flags WHERE candidate_id=? AND is_resolved=0", (candidate_id,)).fetchall()]

        # Agency associations
        agencies_linked = db.execute(
            """SELECT a.id, a.name, a.email, ac.employment_status, ac.assigned_at
               FROM agencies a JOIN agency_candidates ac ON a.id = ac.agency_id
               WHERE ac.candidate_id=?""", (candidate_id,)).fetchall()

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
            "compliance": dict(compliance) if compliance else None,
            "active_alerts": alerts,
            "fraud_flags": fraud,
            "agencies": [dict(r) for r in agencies_linked],
        }


# ── 10. Bulk CQC Audit Pack (multi-candidate) ────────────────────

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
