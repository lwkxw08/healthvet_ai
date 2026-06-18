"""GDPR Compliance routes — right to erasure, data export (SAR), consent, DPIAs, retention."""
import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.database import get_db
from app.middleware.rate_limiter import limiter
from app.utils.auth import (
    generate_id,
    get_current_admin,
    get_current_user,
)

logger = logging.getLogger(__name__)

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
@limiter.limit("3/minute")
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
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        candidate = db.fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        c = dict(candidate)
        c.pop("password_hash", None)
        export["sections"]["personal_data"] = c

        # Consent logs
        db.execute(
            "SELECT * FROM consent_logs WHERE candidate_id=%s ORDER BY timestamp DESC",
            (candidate_id,),
        )
        consents = db.fetchall()
        export["sections"]["consent_history"] = [dict(r) for r in consents]

        # Identity checks
        db.execute(
            "SELECT * FROM identity_checks WHERE candidate_id=%s", (candidate_id,),
        )
        identity = db.fetchall()
        export["sections"]["identity_checks"] = [dict(r) for r in identity]

        # Right to work
        db.execute(
            "SELECT * FROM right_to_work_checks WHERE candidate_id=%s", (candidate_id,),
        )
        rtw = db.fetchall()
        export["sections"]["right_to_work_checks"] = [dict(r) for r in rtw]

        # DBS checks
        db.execute(
            "SELECT * FROM dbs_checks WHERE candidate_id=%s", (candidate_id,),
        )
        dbs = db.fetchall()
        export["sections"]["dbs_checks"] = [dict(r) for r in dbs]

        # CV analyses
        db.execute(
            "SELECT * FROM cv_analyses WHERE candidate_id=%s", (candidate_id,),
        )
        cv = db.fetchall()
        export["sections"]["cv_analyses"] = [dict(r) for r in cv]

        # Registration checks
        db.execute(
            "SELECT * FROM registration_checks WHERE candidate_id=%s", (candidate_id,),
        )
        reg = db.fetchall()
        export["sections"]["registration_checks"] = [dict(r) for r in reg]

        # References
        db.execute(
            "SELECT * FROM references_ WHERE candidate_id=%s", (candidate_id,),
        )
        refs = db.fetchall()
        export["sections"]["references"] = [dict(r) for r in refs]

        # Employment history
        db.execute(
            "SELECT * FROM employment_history WHERE candidate_id=%s", (candidate_id,),
        )
        emp = db.fetchall()
        export["sections"]["employment_history"] = [dict(r) for r in emp]

        # Employment verifications
        db.execute(
            "SELECT * FROM employment_verifications WHERE candidate_id=%s", (candidate_id,),
        )
        emp_v = db.fetchall()
        export["sections"]["employment_verifications"] = [dict(r) for r in emp_v]

        # Training certificates
        try:
            db.execute(
                "SELECT * FROM training_certificates WHERE candidate_id=%s", (candidate_id,),
            )
            training = db.fetchall()
            export["sections"]["training_certificates"] = [dict(r) for r in training]
        except Exception:
            export["sections"]["training_certificates"] = []

        # Compliance records
        db.execute(
            "SELECT * FROM compliance_records WHERE candidate_id=%s", (candidate_id,),
        )
        comp = db.fetchall()
        export["sections"]["compliance_records"] = [dict(r) for r in comp]

        # Submissions
        db.execute(
            "SELECT * FROM candidate_submissions WHERE candidate_id=%s", (candidate_id,),
        )
        subs = db.fetchall()
        export["sections"]["submissions"] = [dict(r) for r in subs]

        # Imposter declarations
        db.execute(
            "SELECT * FROM imposter_declarations WHERE candidate_id=%s", (candidate_id,),
        )
        imp = db.fetchall()
        export["sections"]["imposter_declarations"] = [dict(r) for r in imp]

        # Monitoring alerts
        db.execute(
            "SELECT * FROM monitoring_alerts WHERE candidate_id=%s", (candidate_id,),
        )
        alerts = db.fetchall()
        export["sections"]["monitoring_alerts"] = [dict(r) for r in alerts]

        # Audit log for this export
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'candidate', %s, 'gdpr_data_export', %s, %s, %s)""",
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
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        candidate = db.fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Log the erasure request before processing
        db.execute(
            """INSERT INTO gdpr_erasure_requests
               (id, candidate_id, requested_by, reason, status, created_at)
               VALUES (%s, %s, %s, %s, 'processing', %s)""",
            (erasure_id, candidate_id, current_user.get("sub", "unknown"), data.reason, now),
        )

        # Anonymise personal data (keep structure for audit/compliance but remove PII)
        anon_email = f"erased-{candidate_id[:8]}@anonymised.viperai"
        db.execute(
            """UPDATE candidates SET
               email=%s, first_name='[ERASED]', last_name='[ERASED]',
               phone=NULL, date_of_birth=NULL,
               address_line1=NULL, address_line2=NULL, city=NULL, postcode=NULL,
               profession=NULL, registration_number=NULL, registration_body=NULL,
               password_hash='[ERASED]', status='erased', updated_at=%s
               WHERE id=%s""",
            (anon_email, now, candidate_id),
        )

        # Anonymise references (keep for compliance but strip PII)
        db.execute(
            """UPDATE references_ SET
               referee_name='[ERASED]', referee_email='[ERASED]',
               referee_phone=NULL, referee_organisation='[ERASED]',
               responses=NULL, ip_address=NULL
               WHERE candidate_id=%s""",
            (candidate_id,),
        )

        # Anonymise employment verifications
        db.execute(
            """UPDATE employment_verifications SET
               verifier_name='[ERASED]', verifier_email='[ERASED]',
               additional_comments=NULL, ip_address=NULL
               WHERE candidate_id=%s""",
            (candidate_id,),
        )

        # Clear CV text (keep fraud scores for regulatory compliance)
        db.execute(
            "UPDATE cv_analyses SET cv_text=NULL, ai_summary=NULL WHERE candidate_id=%s",
            (candidate_id,),
        )

        # Remove draft data
        db.execute(
            "DELETE FROM candidate_draft_data WHERE candidate_id=%s",
            (candidate_id,),
        )

        # Delete files from external storage
        files_deleted = 0
        try:
            from app.services.document_storage import get_storage_backend, list_documents
            docs = list_documents(candidate_id=candidate_id)
            if docs:
                storage = get_storage_backend()
                for doc in docs:
                    try:
                        storage.delete(doc["storage_key"])
                        if doc.get("thumbnail_key"):
                            storage.delete(doc["thumbnail_key"])
                        files_deleted += 1
                    except Exception as e:
                        logger.warning("Failed to delete storage file %s: %s", doc.get("storage_key"), e)
                # Remove document metadata records
                db.execute("DELETE FROM documents WHERE candidate_id=%s", (candidate_id,))
        except Exception as e:
            logger.warning("Document cleanup during erasure failed: %s", e)

        # Mark erasure as completed
        db.execute(
            "UPDATE gdpr_erasure_requests SET status='completed', completed_at=%s WHERE id=%s",
            (now, erasure_id),
        )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'candidate', %s, 'gdpr_erasure_completed', %s, %s, %s)""",
            (generate_id(), candidate_id, current_user.get("sub", "unknown"),
             json.dumps({"reason": data.reason, "erasure_id": erasure_id}), now),
        )

    return {
        "erasure_id": erasure_id,
        "status": "completed",
        "candidate_id": candidate_id,
        "message": "Personal data has been anonymised. Regulatory compliance records retained in anonymised form.",
        "files_deleted": files_deleted,
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
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
        db.execute(
            "SELECT * FROM consent_logs WHERE candidate_id=%s ORDER BY timestamp DESC",
            (candidate_id,),
        )
        rows = db.fetchall()
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
        db.execute(
            "SELECT * FROM consent_logs WHERE id=%s AND candidate_id=%s",
            (consent_id, candidate_id),
        )
        existing = db.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Consent record not found")

        # Record the withdrawal as a new entry (don't delete the original — audit trail)
        withdrawal_id = generate_id()
        db.execute(
            """INSERT INTO consent_logs
               (id, candidate_id, consent_type, consent_given, ip_address,
                privacy_policy_version, terms_version, timestamp)
               VALUES (%s, %s, %s, 0, 'withdrawal', %s, %s, %s)""",
            (withdrawal_id, candidate_id, dict(existing)["consent_type"],
             dict(existing).get("privacy_policy_version", "1.0"),
             dict(existing).get("terms_version", "1.0"), now),
        )

    return {"withdrawal_id": withdrawal_id, "withdrawn_at": now}


@router.get("/consent-summary/{candidate_id}")
async def get_consent_summary(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Get a summary of current consent status for all consent types.
    Shows the latest consent decision for each type (data_processing, marketing, etc.)."""
    user_type = current_user.get("type")
    if user_type == "candidate" and current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only view your own consent summary")

    required_consent_types = [
        "data_processing", "background_checks", "data_sharing",
        "marketing", "analytics",
    ]

    with get_db() as db:
        summary = {}
        for consent_type in required_consent_types:
            db.execute(
                """SELECT * FROM consent_logs
                   WHERE candidate_id=%s AND consent_type=%s
                   ORDER BY timestamp DESC LIMIT 1""",
                (candidate_id, consent_type),
            )
            row = db.fetchone()
            if row:
                r = dict(row)
                summary[consent_type] = {
                    "consent_given": bool(r["consent_given"]),
                    "timestamp": r["timestamp"],
                    "privacy_policy_version": r.get("privacy_policy_version"),
                    "terms_version": r.get("terms_version"),
                    "ip_address": r.get("ip_address"),
                }
            else:
                summary[consent_type] = {
                    "consent_given": False,
                    "timestamp": None,
                    "privacy_policy_version": None,
                    "terms_version": None,
                    "ip_address": None,
                }

        all_required = all(
            summary[ct]["consent_given"]
            for ct in ["data_processing", "background_checks"]
        )

    return {
        "candidate_id": candidate_id,
        "consents": summary,
        "all_required_consents_given": all_required,
        "required_types": ["data_processing", "background_checks"],
        "optional_types": ["data_sharing", "marketing", "analytics"],
    }


@router.get("/consent-verify/{candidate_id}")
async def verify_consent(
    candidate_id: str,
    consent_type: str = "data_processing",
    current_user: dict = Depends(get_current_user),
):
    """Verify whether a candidate has given a specific type of consent.
    Used by other services before processing data."""
    with get_db() as db:
        db.execute(
            """SELECT consent_given, timestamp FROM consent_logs
               WHERE candidate_id=%s AND consent_type=%s
               ORDER BY timestamp DESC LIMIT 1""",
            (candidate_id, consent_type),
        )
        row = db.fetchone()

        if not row:
            return {
                "candidate_id": candidate_id,
                "consent_type": consent_type,
                "has_consent": False,
                "message": "No consent record found for this type",
            }

        r = dict(row)
        return {
            "candidate_id": candidate_id,
            "consent_type": consent_type,
            "has_consent": bool(r["consent_given"]),
            "consented_at": r["timestamp"],
        }


# ── DPIA Management (Admin only) ───────────────────────────────────────────

@router.get("/dpias")
async def list_dpias(current_user: dict = Depends(get_current_admin)):
    """List all Data Protection Impact Assessments."""
    with get_db() as db:
        db.execute(
            "SELECT * FROM gdpr_dpias ORDER BY created_at DESC",
        )
        rows = db.fetchall()
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
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
        db.execute("SELECT id FROM gdpr_dpias WHERE id=%s", (dpia_id,))
        existing = db.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="DPIA not found")

        db.execute(
            """UPDATE gdpr_dpias SET
               title=%s, description=%s, data_types=%s, processing_purpose=%s,
               risk_level=%s, mitigations=%s, status=%s, updated_at=%s
               WHERE id=%s""",
            (data.title, data.description, data.data_types, data.processing_purpose,
             data.risk_level, data.mitigations, data.status, now, dpia_id),
        )

    return {"dpia_id": dpia_id, "status": data.status, "updated_at": now}


# ── Retention Policies (Admin only) ────────────────────────────────────────

@router.get("/retention-policies")
async def list_retention_policies(current_user: dict = Depends(get_current_admin)):
    """List all data retention policies."""
    with get_db() as db:
        db.execute(
            "SELECT * FROM gdpr_retention_policies ORDER BY data_category",
        )
        rows = db.fetchall()
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
        db.execute(
            "SELECT id FROM gdpr_retention_policies WHERE data_category=%s",
            (data.data_category,),
        )
        existing = db.fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Retention policy for this category already exists")

        db.execute(
            """INSERT INTO gdpr_retention_policies
               (id, data_category, retention_period_days, legal_basis,
                description, auto_delete, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
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
        db.execute("SELECT id FROM gdpr_retention_policies WHERE id=%s", (policy_id,))
        existing = db.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Retention policy not found")

        db.execute(
            """UPDATE gdpr_retention_policies SET
               data_category=%s, retention_period_days=%s, legal_basis=%s,
               description=%s, auto_delete=%s, updated_at=%s
               WHERE id=%s""",
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
        db.execute("SELECT id FROM gdpr_retention_policies WHERE id=%s", (policy_id,))
        existing = db.fetchone()
        if not existing:
            raise HTTPException(status_code=404, detail="Retention policy not found")
        db.execute("DELETE FROM gdpr_retention_policies WHERE id=%s", (policy_id,))
    return {"deleted": True}


# ── Erasure Request History (Admin only) ────────────────────────────────────

@router.get("/erasure-requests")
async def list_erasure_requests(current_user: dict = Depends(get_current_admin)):
    """List all erasure requests for audit trail."""
    with get_db() as db:
        db.execute(
            "SELECT * FROM gdpr_erasure_requests ORDER BY created_at DESC",
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


# ── Privacy Notice ──────────────────────────────────────────────────────────

@router.get("/privacy-notice")
async def get_privacy_notice():
    """Return the current privacy notice content (public endpoint)."""
    return {
        "version": "1.0",
        "last_updated": "2026-03-01",
        "controller": {
            "name": "Viper AI Ltd",
            "contact_email": "dpo@viperai.io",
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


# ── Downloadable Data Export (CSV) ─────────────────────────────────────────

@router.post("/data-export/download")
async def download_data_export(
    request: Request,
    data: DataExportRequest,
    current_user: dict = Depends(get_current_user),
):
    """Download all personal data as a CSV file (GDPR Article 20 — data portability)."""
    user_type = current_user.get("type")
    candidate_id = data.candidate_id

    if user_type == "candidate" and current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only export your own data")
    if user_type == "agency":
        raise HTTPException(status_code=403, detail="Agencies cannot export candidate data directly")

    with get_db() as db:
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        candidate = db.fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        c = dict(candidate)
        c.pop("password_hash", None)

        # Build CSV with all sections
        buf = io.StringIO()
        writer = csv.writer(buf)

        # Personal data section
        writer.writerow(["== Personal Data =="])
        writer.writerow(list(c.keys()))
        writer.writerow(list(c.values()))
        writer.writerow([])

        # Helper to write a section
        def _write_section(title: str, query: str, params: tuple) -> None:
            db.execute(query, params)
            rows = db.fetchall()
            writer.writerow([f"== {title} =="])
            if rows:
                headers = list(dict(rows[0]).keys())
                writer.writerow(headers)
                for r in rows:
                    writer.writerow(list(dict(r).values()))
            else:
                writer.writerow(["No records"])
            writer.writerow([])

        _write_section("Consent History",
                       "SELECT * FROM consent_logs WHERE candidate_id=%s ORDER BY timestamp DESC", (candidate_id,))
        _write_section("Identity Checks",
                       "SELECT * FROM identity_checks WHERE candidate_id=%s", (candidate_id,))
        _write_section("Right to Work Checks",
                       "SELECT * FROM right_to_work_checks WHERE candidate_id=%s", (candidate_id,))
        _write_section("DBS Checks",
                       "SELECT * FROM dbs_checks WHERE candidate_id=%s", (candidate_id,))
        _write_section("CV Analyses",
                       "SELECT * FROM cv_analyses WHERE candidate_id=%s", (candidate_id,))
        _write_section("Registration Checks",
                       "SELECT * FROM registration_checks WHERE candidate_id=%s", (candidate_id,))
        _write_section("References",
                       "SELECT * FROM references_ WHERE candidate_id=%s", (candidate_id,))
        _write_section("Employment History",
                       "SELECT * FROM employment_history WHERE candidate_id=%s", (candidate_id,))
        _write_section("Employment Verifications",
                       "SELECT * FROM employment_verifications WHERE candidate_id=%s", (candidate_id,))
        _write_section("Compliance Records",
                       "SELECT * FROM compliance_records WHERE candidate_id=%s", (candidate_id,))

        # Audit log
        now = datetime.now(timezone.utc).isoformat()
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'candidate', %s, 'gdpr_csv_download', %s, %s, %s)""",
            (generate_id(), candidate_id, current_user.get("sub", "unknown"),
             json.dumps({"reason": data.reason, "format": "csv"}), now),
        )

    csv_bytes = buf.getvalue().encode("utf-8")
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gdpr_export_{candidate_id[:8]}.csv"},
    )


@router.get("/data-portability/{candidate_id}")
async def data_portability_package(
    candidate_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Generate a comprehensive GDPR Article 20 data portability package.
    Returns a ZIP file containing JSON exports of all candidate data sections
    plus any uploaded documents."""
    user_type = current_user.get("type")
    if user_type == "candidate" and current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only export your own data")
    if user_type == "agency":
        raise HTTPException(status_code=403, detail="Agencies cannot export candidate data directly")

    now = datetime.now(timezone.utc).isoformat()
    zip_buffer = io.BytesIO()

    with get_db() as db:
        db.execute("SELECT * FROM candidates WHERE id=%s", (candidate_id,))
        candidate = db.fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
        c = dict(candidate)
        c.pop("password_hash", None)

        def _fetch_section(query: str, params: tuple) -> list[dict]:
            db.execute(query, params)
            rows = db.fetchall()
            return [dict(r) for r in rows]

        sections = {
            "personal_data": c,
            "consent_history": _fetch_section(
                "SELECT * FROM consent_logs WHERE candidate_id=%s ORDER BY timestamp DESC", (candidate_id,)),
            "identity_checks": _fetch_section(
                "SELECT * FROM identity_checks WHERE candidate_id=%s", (candidate_id,)),
            "right_to_work_checks": _fetch_section(
                "SELECT * FROM right_to_work_checks WHERE candidate_id=%s", (candidate_id,)),
            "dbs_checks": _fetch_section(
                "SELECT * FROM dbs_checks WHERE candidate_id=%s", (candidate_id,)),
            "cv_analyses": _fetch_section(
                "SELECT * FROM cv_analyses WHERE candidate_id=%s", (candidate_id,)),
            "registration_checks": _fetch_section(
                "SELECT * FROM registration_checks WHERE candidate_id=%s", (candidate_id,)),
            "references": _fetch_section(
                "SELECT * FROM references_ WHERE candidate_id=%s", (candidate_id,)),
            "employment_history": _fetch_section(
                "SELECT * FROM employment_history WHERE candidate_id=%s", (candidate_id,)),
            "employment_verifications": _fetch_section(
                "SELECT * FROM employment_verifications WHERE candidate_id=%s", (candidate_id,)),
            "compliance_records": _fetch_section(
                "SELECT * FROM compliance_records WHERE candidate_id=%s", (candidate_id,)),
            "submissions": _fetch_section(
                "SELECT * FROM candidate_submissions WHERE candidate_id=%s", (candidate_id,)),
        }

        # Get documents metadata
        doc_rows = _fetch_section(
            "SELECT * FROM documents WHERE candidate_id=%s", (candidate_id,))
        sections["documents_metadata"] = doc_rows

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # Write manifest
            manifest = {
                "export_type": "GDPR Article 20 Data Portability Package",
                "candidate_id": candidate_id,
                "generated_at": now,
                "generated_by": "Viper AI",
                "sections": list(sections.keys()),
                "total_documents": len(doc_rows),
            }
            zf.writestr("manifest.json", json.dumps(manifest, indent=2, default=str))

            # Write each data section as JSON
            for section_name, section_data in sections.items():
                zf.writestr(
                    f"data/{section_name}.json",
                    json.dumps(section_data, indent=2, default=str),
                )

            # Include actual document files if available
            try:
                from app.services.document_storage import get_storage_backend
                storage = get_storage_backend()
                for doc in doc_rows:
                    storage_key = doc.get("storage_key")
                    if storage_key:
                        try:
                            file_data, original_name, _ = storage.download(storage_key)
                            content = file_data.read()
                            if hasattr(file_data, "close"):
                                file_data.close()
                            zf.writestr(f"documents/{original_name}", content)
                        except Exception as e:
                            logger.warning("Could not include document %s: %s", storage_key, e)
            except Exception as e:
                logger.warning("Could not include documents in portability package: %s", e)

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'candidate', %s, 'gdpr_portability_package', %s, %s, %s)""",
            (generate_id(), candidate_id, current_user.get("sub", "unknown"),
             json.dumps({"format": "zip", "sections": list(sections.keys())}), now),
        )

    zip_bytes = zip_buffer.getvalue()
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=data_portability_{candidate_id[:8]}.zip"},
    )


# ── Data Lifecycle Management ──────────────────────────────────────────────

class AgencyDPAAcceptance(BaseModel):
    agency_id: str = Field(..., max_length=100)
    signatory_name: str = Field(..., min_length=2, max_length=200)
    signatory_role: str = Field(..., min_length=2, max_length=200)
    dpa_version: str = Field("1.0", max_length=20)


@router.post("/agency-dpa")
async def accept_agency_dpa(
    request: Request,
    data: AgencyDPAAcceptance,
    current_user: dict = Depends(get_current_user),
):
    """Record agency acceptance of the Data Processing Agreement.
    The agency confirms lawful basis for retaining candidate data for continuous monitoring."""
    user_type = current_user.get("type")
    if user_type not in ("agency", "admin"):
        raise HTTPException(status_code=403, detail="Only agencies or admins can accept the DPA")

    now = datetime.now(timezone.utc).isoformat()
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    user_agent = request.headers.get("User-Agent", "unknown")
    dpa_id = generate_id()

    dpa_text = (
        f"Data Processing Agreement — Version {data.dpa_version}\n\n"
        "As the Data Controller, the undersigned agency confirms that:\n\n"
        "1. They have a lawful basis under UK GDPR for instructing Viper AI Ltd (Data Processor) "
        "to process candidate personal data for the purposes of pre-employment vetting and "
        "continuous compliance monitoring.\n\n"
        "2. They accept responsibility for ensuring all data subjects (candidates) are appropriately "
        "informed about the processing of their personal data, including the retention period and "
        "their rights under UK GDPR.\n\n"
        "3. Candidate vetting data will be retained for a maximum of 12 months from the date of "
        "the candidate's last active placement for the purpose of continuous compliance monitoring. "
        "After 12 months of inactivity, personal data will be anonymised.\n\n"
        "4. DBS certificate numbers will be automatically purged 6 months after the recruitment "
        "decision, in accordance with the DBS Code of Practice.\n\n"
        "5. The agency may request data export or deletion at any time by contacting "
        "enquiries@viperai.io or via the platform's GDPR tools.\n\n"
        "6. Both parties shall comply with the UK General Data Protection Regulation (UK GDPR) "
        "and the Data Protection Act 2018 at all times."
    )

    with get_db() as db:
        db.execute(
            """INSERT INTO consent_logs
               (id, candidate_id, consent_type, consent_given, ip_address, user_agent,
                privacy_policy_version, terms_version, timestamp)
               VALUES (%s, %s, %s, 1, %s, %s, %s, %s, %s)""",
            (dpa_id, data.agency_id, "agency_dpa_acceptance", ip, user_agent,
             data.dpa_version, data.dpa_version, now),
        )
        # Also store the full DPA text and signatory details in audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'agency', %s, 'dpa_accepted', %s, %s, %s)""",
            (generate_id(), data.agency_id, current_user.get("sub", "unknown"),
             json.dumps({
                 "dpa_id": dpa_id,
                 "signatory_name": data.signatory_name,
                 "signatory_role": data.signatory_role,
                 "dpa_version": data.dpa_version,
                 "dpa_text": dpa_text,
                 "ip_address": ip,
                 "user_agent": user_agent,
             }), now),
        )

    return {
        "dpa_id": dpa_id,
        "agency_id": data.agency_id,
        "accepted_at": now,
        "dpa_version": data.dpa_version,
        "signatory_name": data.signatory_name,
    }


@router.get("/agency-dpa/{agency_id}")
async def get_agency_dpa_status(
    agency_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Check whether an agency has accepted the DPA."""
    with get_db() as db:
        db.execute(
            """SELECT * FROM consent_logs
               WHERE candidate_id=%s AND consent_type='agency_dpa_acceptance' AND consent_given=1
               ORDER BY timestamp DESC LIMIT 1""",
            (agency_id,),
        )
        row = db.fetchone()
        if not row:
            return {"agency_id": agency_id, "dpa_accepted": False}

        r = dict(row)
        return {
            "agency_id": agency_id,
            "dpa_accepted": True,
            "accepted_at": r["timestamp"],
            "dpa_version": r.get("privacy_policy_version"),
        }


@router.post("/dbs-certificate-purge")
async def run_dbs_certificate_purge(
    current_user: dict = Depends(get_current_admin),
):
    """Purge DBS certificate numbers older than 6 months (DBS Code of Practice).
    Retains the check result, status, and audit trail — only removes the certificate number."""
    now = datetime.now(timezone.utc)
    six_months_ago = (now - __import__("datetime").timedelta(days=183)).isoformat()
    purged = 0

    with get_db() as db:
        db.execute(
            """UPDATE dbs_checks
               SET certificate_number = NULL,
                   candidate_certificate_number = NULL
               WHERE (submitted_at < %s OR completed_at < %s)
               AND (certificate_number IS NOT NULL OR candidate_certificate_number IS NOT NULL)""",
            (six_months_ago, six_months_ago),
        )
        purged = db.rowcount

        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'system', 'dbs_purge', 'dbs_certificate_purge', 'system', %s, %s)""",
            (generate_id(), json.dumps({
                "purged_count": purged,
                "cutoff_date": six_months_ago,
                "policy": "DBS Code of Practice — 6 month retention",
            }), now.isoformat()),
        )

    return {"purged_count": purged, "cutoff_date": six_months_ago}


@router.post("/anonymise-inactive")
async def anonymise_inactive_candidates(
    current_user: dict = Depends(get_current_admin),
):
    """Anonymise candidates inactive for 12+ months.
    Replaces personal data with anonymised values; retains compliance audit trail."""
    now = datetime.now(timezone.utc)
    twelve_months_ago = (now - __import__("datetime").timedelta(days=365)).isoformat()
    anonymised = 0

    with get_db() as db:
        # Find candidates with no activity in 12 months
        db.execute(
            """SELECT c.id, c.email FROM candidates c
               LEFT JOIN agency_candidates ac ON ac.candidate_id = c.id
               WHERE c.updated_at < %s
               AND (ac.monitoring_active IS NULL OR ac.monitoring_active = 0)
               AND c.email NOT LIKE '%%@anonymised.viperai.io'""",
            (twelve_months_ago,),
        )
        inactive = db.fetchall()

        for row in inactive:
            cand = dict(row)
            cid = cand["id"]
            anon_email = f"{cid[:8]}@anonymised.viperai.io"

            db.execute(
                """UPDATE candidates SET
                   first_name='[Anonymised]', last_name='[Anonymised]',
                   email=%s, phone=NULL, address=NULL,
                   date_of_birth=NULL, ni_number=NULL,
                   updated_at=%s
                   WHERE id=%s""",
                (anon_email, now.isoformat(), cid),
            )
            anonymised += 1

        # Log the anonymisation run
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'system', 'anonymisation', 'data_lifecycle_anonymise', 'system', %s, %s)""",
            (generate_id(), json.dumps({
                "anonymised_count": anonymised,
                "cutoff_date": twelve_months_ago,
                "policy": "12-month data retention — UK GDPR compliance",
            }), now.isoformat()),
        )

    return {"anonymised_count": anonymised, "cutoff_date": twelve_months_ago}


@router.post("/candidate-deletion-request")
@limiter.limit("3/minute")
async def candidate_deletion_request(
    request: Request,
    data: ErasureRequest,
    current_user: dict = Depends(get_current_user),
):
    """Candidate requests deletion of their data (GDPR Article 17).
    Creates a request that is processed within 30 days.
    Notifies the agency and logs the request for audit."""
    if current_user.get("type") != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can request their own data deletion")

    candidate_id = data.candidate_id
    if current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only request deletion of your own data")

    if not data.confirmed:
        raise HTTPException(status_code=400, detail="You must confirm the deletion request")

    now = datetime.now(timezone.utc).isoformat()
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    request_id = generate_id()

    with get_db() as db:
        # Check candidate exists
        db.execute("SELECT id, email FROM candidates WHERE id=%s", (candidate_id,))
        candidate = db.fetchone()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")

        # Create erasure request with 30-day processing window
        due_date = (datetime.now(timezone.utc) + __import__("datetime").timedelta(days=30)).isoformat()
        db.execute(
            """INSERT INTO gdpr_erasure_requests
               (id, candidate_id, reason, status, requested_at, created_at)
               VALUES (%s, %s, %s, 'pending', %s, %s)""",
            (request_id, candidate_id, data.reason, now, now),
        )

        # Record withdrawal of data retention consent
        db.execute(
            """INSERT INTO consent_logs
               (id, candidate_id, consent_type, consent_given, ip_address,
                privacy_policy_version, terms_version, timestamp)
               VALUES (%s, %s, 'data_retention_withdrawal', 0, %s, '1.0', '1.0', %s)""",
            (generate_id(), candidate_id, ip, now),
        )

        # Notify linked agencies
        db.execute(
            "SELECT agency_id FROM agency_candidates WHERE candidate_id=%s",
            (candidate_id,),
        )
        agencies = db.fetchall()
        for ag in agencies:
            aid = dict(ag)["agency_id"]
            db.execute(
                """INSERT INTO notifications (id, user_id, user_type, title, message, link, created_at)
                   VALUES (%s, %s, 'agency', %s, %s, %s, %s)""",
                (generate_id(), aid,
                 "Candidate Data Deletion Request",
                 f"A candidate has requested deletion of their personal data. "
                 f"Request ID: {request_id}. Processing deadline: 30 days.",
                 "/dashboard?tab=compliance", now),
            )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'candidate', %s, 'data_deletion_requested', %s, %s, %s)""",
            (generate_id(), candidate_id, candidate_id,
             json.dumps({
                 "request_id": request_id,
                 "reason": data.reason,
                 "due_date": due_date,
                 "ip_address": ip,
                 "agencies_notified": [dict(a)["agency_id"] for a in agencies],
             }), now),
        )

    return {
        "request_id": request_id,
        "status": "pending",
        "due_date": due_date,
        "message": "Your deletion request has been received and will be processed within 30 days.",
    }
