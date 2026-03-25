"""GDPR Compliance routes — right to erasure, data export (SAR), consent, DPIAs, retention."""
import json
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.database import get_db
from app.utils.auth import (
    generate_id,
    get_current_admin,
    get_current_user,
)

router = APIRouter(prefix="/api/gdpr", tags=["GDPR"])


# ── Schemas ─────────────────────────────────────────────────────────────────

class DataExportRequest(BaseModel):
    candidate_id: str = Field(..., max_length=100)
    reason: str = Field("Subject Access Request", max_length=500)


class ErasureRequest(BaseModel):
    candidate_id: str = Field(..., max_length=100)
    reason: str = Field(..., min_length=5, max_length=1000)
    confirmed: bool = Field(...)


class ConsentRecord(BaseModel):
    consent_type: str = Field(..., max_length=100)
    consent_given: bool
    privacy_policy_version: str = Field("1.0", max_length=20)
    terms_version: str = Field("1.0", max_length=20)


class DPIARecord(BaseModel):
    title: str = Field(..., min_length=3, max_length=200)
    description: str = Field(..., min_length=10, max_length=5000)
    data_types: str = Field(..., max_length=2000)
    processing_purpose: str = Field(..., max_length=2000)
    risk_level: str = Field("medium", pattern=r"^(low|medium|high|critical)$")
    mitigations: str = Field("", max_length=5000)
    status: str = Field("draft", pattern=r"^(draft|in_review|approved|rejected)$")


class RetentionPolicyRecord(BaseModel):
    data_category: str = Field(..., min_length=2, max_length=100)
    retention_period_days: int = Field(..., ge=1, le=36500)
    legal_basis: str = Field(..., max_length=500)
    description: str = Field("", max_length=2000)
    auto_delete: bool = Field(False)


# ── Subject Access Request (Data Export) ────────────────────────────────────

@router.post("/data-export")
async def request_data_export(
    request: Request,
    data: DataExportRequest,
    current_user: dict = Depends(get_current_user),
):
    """Export all personal data for a candidate (GDPR Article 15 — Subject Access Request).
    Candidates can export their own data; admins can export any candidate's data."""
    user_type = current_user.get("type")
    candidate_id = data.candidate_id

    if user_type == "candidate" and current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only export your own data")
    if user_type == "agency":
        raise HTTPException(status_code=403, detail="Agencies cannot export candidate data directly")

    now = datetime.now(timezone.utc).isoformat()
    export = {"candidate_id": candidate_id, "exported_at": now, "sections": {}}

    with get_db() as db:
        # Personal data
        candidate = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        c = dict(candidate)
        c.pop("password_hash", None)
        export["sections"]["personal_data"] = c

        # Consent logs
        consents = db.execute(
            "SELECT * FROM consent_logs WHERE candidate_id=? ORDER BY timestamp DESC",
            (candidate_id,),
        ).fetchall()
        export["sections"]["consent_history"] = [dict(r) for r in consents]

        # Identity checks
        identity = db.execute(
            "SELECT * FROM identity_checks WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["identity_checks"] = [dict(r) for r in identity]

        # Right to work
        rtw = db.execute(
            "SELECT * FROM right_to_work_checks WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["right_to_work_checks"] = [dict(r) for r in rtw]

        # DBS checks
        dbs = db.execute(
            "SELECT * FROM dbs_checks WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["dbs_checks"] = [dict(r) for r in dbs]

        # CV analyses
        cv = db.execute(
            "SELECT * FROM cv_analyses WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["cv_analyses"] = [dict(r) for r in cv]

        # Registration checks
        reg = db.execute(
            "SELECT * FROM registration_checks WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["registration_checks"] = [dict(r) for r in reg]

        # References
        refs = db.execute(
            "SELECT * FROM references_ WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["references"] = [dict(r) for r in refs]

        # Employment history
        emp = db.execute(
            "SELECT * FROM employment_history WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["employment_history"] = [dict(r) for r in emp]

        # Employment verifications
        emp_v = db.execute(
            "SELECT * FROM employment_verifications WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["employment_verifications"] = [dict(r) for r in emp_v]

        # Training certificates
        try:
            training = db.execute(
                "SELECT * FROM training_certificates WHERE candidate_id=?", (candidate_id,),
            ).fetchall()
            export["sections"]["training_certificates"] = [dict(r) for r in training]
        except Exception:
            export["sections"]["training_certificates"] = []

        # Compliance records
        comp = db.execute(
            "SELECT * FROM compliance_records WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["compliance_records"] = [dict(r) for r in comp]

        # Submissions
        subs = db.execute(
            "SELECT * FROM candidate_submissions WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["submissions"] = [dict(r) for r in subs]

        # Imposter declarations
        imp = db.execute(
            "SELECT * FROM imposter_declarations WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["imposter_declarations"] = [dict(r) for r in imp]

        # Monitoring alerts
        alerts = db.execute(
            "SELECT * FROM monitoring_alerts WHERE candidate_id=?", (candidate_id,),
        ).fetchall()
        export["sections"]["monitoring_alerts"] = [dict(r) for r in alerts]

        # Audit log for this export
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (?, 'candidate', ?, 'gdpr_data_export', ?, ?, ?)""",
            (generate_id(), candidate_id, current_user.get("sub", "unknown"),
             json.dumps({"reason": data.reason, "sections_exported": list(export["sections"].keys())}),
             now),
        )

    return export


# ── Right to Erasure (GDPR Article 17) ─────────────────────────────────────

@router.post("/erasure-request")
async def request_erasure(
    request: Request,
    data: ErasureRequest,
    current_user: dict = Depends(get_current_user),
):
    """Request deletion of all personal data for a candidate (GDPR Article 17).
    Candidates can request their own erasure; admins can process any.
    Data required for legal/regulatory compliance is retained but anonymised."""
    user_type = current_user.get("type")
    candidate_id = data.candidate_id

    if user_type == "candidate" and current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only request erasure of your own data")
    if user_type == "agency":
        raise HTTPException(status_code=403, detail="Agencies cannot request candidate erasure")
    if not data.confirmed:
        raise HTTPException(status_code=400, detail="You must confirm the erasure request")

    now = datetime.now(timezone.utc).isoformat()
    erasure_id = generate_id()

    with get_db() as db:
        candidate = db.execute("SELECT * FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Log the erasure request before processing
        db.execute(
            """INSERT INTO gdpr_erasure_requests
               (id, candidate_id, requested_by, reason, status, created_at)
               VALUES (?, ?, ?, ?, 'processing', ?)""",
            (erasure_id, candidate_id, current_user.get("sub", "unknown"), data.reason, now),
        )

        # Anonymise personal data (keep structure for audit/compliance but remove PII)
        anon_email = f"erased-{candidate_id[:8]}@anonymised.healthvet"
        db.execute(
            """UPDATE candidates SET
               email=?, first_name='[ERASED]', last_name='[ERASED]',
               phone=NULL, date_of_birth=NULL,
               address_line1=NULL, address_line2=NULL, city=NULL, postcode=NULL,
               profession=NULL, registration_number=NULL, registration_body=NULL,
               password_hash='[ERASED]', status='erased', updated_at=?
               WHERE id=?""",
            (anon_email, now, candidate_id),
        )

        # Anonymise references (keep for compliance but strip PII)
        db.execute(
            """UPDATE references_ SET
               referee_name='[ERASED]', referee_email='[ERASED]',
               referee_phone=NULL, referee_organisation='[ERASED]',
               responses=NULL, ip_address=NULL
               WHERE candidate_id=?""",
            (candidate_id,),
        )

        # Anonymise employment verifications
        db.execute(
            """UPDATE employment_verifications SET
               verifier_name='[ERASED]', verifier_email='[ERASED]',
               additional_comments=NULL, ip_address=NULL
               WHERE candidate_id=?""",
            (candidate_id,),
        )

        # Clear CV text (keep fraud scores for regulatory compliance)
        db.execute(
            "UPDATE cv_analyses SET cv_text=NULL, ai_summary=NULL WHERE candidate_id=?",
            (candidate_id,),
        )

        # Remove draft data
        db.execute(
            "DELETE FROM candidate_draft_data WHERE candidate_id=?",
            (candidate_id,),
        )

        # Mark erasure as completed
        db.execute(
            "UPDATE gdpr_erasure_requests SET status='completed', completed_at=? WHERE id=?",
            (now, erasure_id),
        )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (?, 'candidate', ?, 'gdpr_erasure_completed', ?, ?, ?)""",
            (generate_id(), candidate_id, current_user.get("sub", "unknown"),
             json.dumps({"reason": data.reason, "erasure_id": erasure_id}), now),
        )

    return {
        "erasure_id": erasure_id,
        "status": "completed",
        "candidate_id": candidate_id,
        "message": "Personal data has been anonymised. Regulatory compliance records retained in anonymised form.",
    }


# ── Consent Management ─────────────────────────────────────────────────────

@router.post("/consent")
async def record_consent(
    request: Request,
    data: ConsentRecord,
    current_user: dict = Depends(get_current_user),
):
    """Record a consent decision from a candidate (GDPR Article 7)."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can record consent")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    user_agent = request.headers.get("User-Agent", "unknown")

    with get_db() as db:
        consent_id = generate_id()
        db.execute(
            """INSERT INTO consent_logs
               (id, candidate_id, consent_type, consent_given, ip_address, user_agent,
                privacy_policy_version, terms_version, timestamp)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (consent_id, candidate_id, data.consent_type, int(data.consent_given),
             ip, user_agent, data.privacy_policy_version, data.terms_version, now),
        )

    return {"consent_id": consent_id, "recorded_at": now}


@router.get("/consent/{candidate_id}")
async def get_consent_history(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get consent history for a candidate."""
    user_type = current_user.get("type")
    if user_type == "candidate" and current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only view your own consent history")

    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM consent_logs WHERE candidate_id=? ORDER BY timestamp DESC",
            (candidate_id,),
        ).fetchall()
        return [dict(r) for r in rows]


@router.delete("/consent/{consent_id}")
async def withdraw_consent(
    consent_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Withdraw a previously given consent (GDPR Article 7(3))."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can withdraw consent")

    now = datetime.now(timezone.utc).isoformat()
    candidate_id = current_user["sub"]

    with get_db() as db:
        existing = db.execute(
            "SELECT * FROM consent_logs WHERE id=? AND candidate_id=?",
            (consent_id, candidate_id),
        ).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Consent record not found")

        # Record the withdrawal as a new entry (don't delete the original — audit trail)
        withdrawal_id = generate_id()
        db.execute(
            """INSERT INTO consent_logs
               (id, candidate_id, consent_type, consent_given, ip_address,
                privacy_policy_version, terms_version, timestamp)
               VALUES (?, ?, ?, 0, 'withdrawal', ?, ?, ?)""",
            (withdrawal_id, candidate_id, dict(existing)["consent_type"],
             dict(existing).get("privacy_policy_version", "1.0"),
             dict(existing).get("terms_version", "1.0"), now),
        )

    return {"withdrawal_id": withdrawal_id, "withdrawn_at": now}


# ── DPIA Management (Admin only) ───────────────────────────────────────────

@router.get("/dpias")
async def list_dpias(current_user: dict = Depends(get_current_admin)):
    """List all Data Protection Impact Assessments."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM gdpr_dpias ORDER BY created_at DESC",
        ).fetchall()
        return [dict(r) for r in rows]


@router.post("/dpias")
async def create_dpia(
    data: DPIARecord,
    current_user: dict = Depends(get_current_admin),
):
    """Create a new Data Protection Impact Assessment (GDPR Article 35)."""
    now = datetime.now(timezone.utc).isoformat()
    dpia_id = generate_id()

    with get_db() as db:
        db.execute(
            """INSERT INTO gdpr_dpias
               (id, title, description, data_types, processing_purpose,
                risk_level, mitigations, status, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (dpia_id, data.title, data.description, data.data_types,
             data.processing_purpose, data.risk_level, data.mitigations,
             data.status, current_user.get("sub", "admin"), now, now),
        )

    return {"dpia_id": dpia_id, "status": data.status, "created_at": now}


@router.put("/dpias/{dpia_id}")
async def update_dpia(
    dpia_id: str,
    data: DPIARecord,
    current_user: dict = Depends(get_current_admin),
):
    """Update an existing DPIA."""
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        existing = db.execute("SELECT id FROM gdpr_dpias WHERE id=?", (dpia_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="DPIA not found")

        db.execute(
            """UPDATE gdpr_dpias SET
               title=?, description=?, data_types=?, processing_purpose=?,
               risk_level=?, mitigations=?, status=?, updated_at=?
               WHERE id=?""",
            (data.title, data.description, data.data_types, data.processing_purpose,
             data.risk_level, data.mitigations, data.status, now, dpia_id),
        )

    return {"dpia_id": dpia_id, "status": data.status, "updated_at": now}


# ── Retention Policies (Admin only) ────────────────────────────────────────

@router.get("/retention-policies")
async def list_retention_policies(current_user: dict = Depends(get_current_admin)):
    """List all data retention policies."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM gdpr_retention_policies ORDER BY data_category",
        ).fetchall()
        return [dict(r) for r in rows]


@router.post("/retention-policies")
async def create_retention_policy(
    data: RetentionPolicyRecord,
    current_user: dict = Depends(get_current_admin),
):
    """Create a data retention policy."""
    now = datetime.now(timezone.utc).isoformat()
    policy_id = generate_id()

    with get_db() as db:
        existing = db.execute(
            "SELECT id FROM gdpr_retention_policies WHERE data_category=?",
            (data.data_category,),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Retention policy for this category already exists")

        db.execute(
            """INSERT INTO gdpr_retention_policies
               (id, data_category, retention_period_days, legal_basis,
                description, auto_delete, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (policy_id, data.data_category, data.retention_period_days,
             data.legal_basis, data.description, int(data.auto_delete), now),
        )

    return {"policy_id": policy_id, "created_at": now}


@router.put("/retention-policies/{policy_id}")
async def update_retention_policy(
    policy_id: str,
    data: RetentionPolicyRecord,
    current_user: dict = Depends(get_current_admin),
):
    """Update a retention policy."""
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        existing = db.execute("SELECT id FROM gdpr_retention_policies WHERE id=?", (policy_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Retention policy not found")

        db.execute(
            """UPDATE gdpr_retention_policies SET
               data_category=?, retention_period_days=?, legal_basis=?,
               description=?, auto_delete=?, updated_at=?
               WHERE id=?""",
            (data.data_category, data.retention_period_days, data.legal_basis,
             data.description, int(data.auto_delete), now, policy_id),
        )

    return {"policy_id": policy_id, "updated_at": now}


@router.delete("/retention-policies/{policy_id}")
async def delete_retention_policy(
    policy_id: str,
    current_user: dict = Depends(get_current_admin),
):
    """Delete a retention policy."""
    with get_db() as db:
        existing = db.execute("SELECT id FROM gdpr_retention_policies WHERE id=?", (policy_id,)).fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Retention policy not found")
        db.execute("DELETE FROM gdpr_retention_policies WHERE id=?", (policy_id,))
    return {"deleted": True}


# ── Erasure Request History (Admin only) ────────────────────────────────────

@router.get("/erasure-requests")
async def list_erasure_requests(current_user: dict = Depends(get_current_admin)):
    """List all erasure requests for audit trail."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM gdpr_erasure_requests ORDER BY created_at DESC",
        ).fetchall()
        return [dict(r) for r in rows]


# ── Privacy Notice ──────────────────────────────────────────────────────────

@router.get("/privacy-notice")
async def get_privacy_notice():
    """Return the current privacy notice content (public endpoint)."""
    return {
        "version": "1.0",
        "last_updated": "2026-03-01",
        "controller": {
            "name": "HealthVet AI Ltd",
            "contact_email": "dpo@healthvet.ai",
            "ico_registration": "Pending",
        },
        "data_collected": [
            {"category": "Identity", "data": "Full name, date of birth, address, email, phone", "basis": "Contractual necessity", "retention": "Duration of employment + 7 years"},
            {"category": "Right to Work", "data": "Nationality, visa status, share codes, NI number", "basis": "Legal obligation (Immigration Act 2016)", "retention": "Duration of employment + 2 years"},
            {"category": "DBS", "data": "DBS certificate number, check results", "basis": "Legal obligation (Safeguarding Vulnerable Groups Act 2006)", "retention": "Duration of employment + 6 months after leaving"},
            {"category": "Professional Registration", "data": "NMC/GMC/HCPC registration number, status", "basis": "Legal obligation (Health and Social Care Act 2008)", "retention": "Duration of employment + 7 years"},
            {"category": "Employment History", "data": "Previous employers, job titles, dates, references", "basis": "Legitimate interest (pre-employment screening)", "retention": "Duration of employment + 7 years"},
            {"category": "CV / Qualifications", "data": "CV text, qualification certificates", "basis": "Contractual necessity", "retention": "Duration of employment + 7 years"},
            {"category": "Financial", "data": "Invoice records, payment history", "basis": "Legal obligation (financial record-keeping)", "retention": "7 years"},
        ],
        "rights": [
            "Right of access (Article 15) — request a copy of all your data",
            "Right to rectification (Article 16) — correct inaccurate data",
            "Right to erasure (Article 17) — request deletion of your data",
            "Right to restrict processing (Article 18)",
            "Right to data portability (Article 20) — receive data in machine-readable format",
            "Right to object (Article 21) — object to processing based on legitimate interest",
            "Right to withdraw consent (Article 7(3)) — withdraw consent at any time",
        ],
        "international_transfers": "Data is stored in UK/EU data centres only. No international transfers.",
        "complaints": "You may lodge a complaint with the ICO: https://ico.org.uk/make-a-complaint/",
    }
