"""Routes for candidate submission workflow (data collection, consent, automated processing)."""
import json
import secrets
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel
from typing import Optional
from app.database import get_db
from app.utils.auth import get_current_user, generate_id

router = APIRouter(prefix="/api/submissions", tags=["Submissions"])


class CreateSubmissionRequest(BaseModel):
    submission_type: str = "full"  # full or partial
    sections_requested: Optional[list[str]] = None
    revet_token: Optional[str] = None  # for partial re-vet via agency link


class SaveSectionRequest(BaseModel):
    data: dict
    completed: bool = False


class ConsentRequest(BaseModel):
    consent_given: bool
    privacy_policy_version: str = "1.0"
    terms_version: str = "1.0"


# ── Create / Get Submissions ─────────────────────────────────────

@router.post("/create")
async def create_submission(body: CreateSubmissionRequest, request: Request, current_user: dict = Depends(get_current_user)):
    """Create a new submission (full vetting or partial re-vet)."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        # If this is a re-vet via token, validate it
        if body.revet_token:
            revet = db.execute(
                "SELECT * FROM revet_requests WHERE token=? AND candidate_id=? AND status='pending'",
                (body.revet_token, candidate_id),
            ).fetchone()
            if not revet:
                raise HTTPException(status_code=404, detail="Invalid or expired re-vet token")
            revet_data = dict(revet)
            sections = json.loads(revet_data["sections"])
            submission_type = "partial"
        else:
            # Check for existing draft full submission
            existing = db.execute(
                "SELECT id FROM candidate_submissions WHERE candidate_id=? AND submission_type='full' AND status='draft'",
                (candidate_id,),
            ).fetchone()
            if existing:
                # Return existing draft
                return await get_submission(dict(existing)["id"], current_user)

            sections = body.sections_requested or [
                "personal", "identity", "rtw", "dbs", "cv", "registration", "references", "training"
            ]
            submission_type = body.submission_type

        sub_id = generate_id()
        db.execute(
            """INSERT INTO candidate_submissions
               (id, candidate_id, submission_type, sections_requested, status, created_at)
               VALUES (?, ?, ?, ?, 'draft', ?)""",
            (sub_id, candidate_id, submission_type, json.dumps(sections), now),
        )

        # If re-vet, link the submission
        if body.revet_token:
            db.execute(
                "UPDATE revet_requests SET submission_id=? WHERE token=?",
                (sub_id, body.revet_token),
            )

        return {
            "id": sub_id,
            "candidate_id": candidate_id,
            "submission_type": submission_type,
            "sections_requested": sections,
            "status": "draft",
            "created_at": now,
            "sections": {},
        }


@router.get("/current")
async def get_current_submission(current_user: dict = Depends(get_current_user)):
    """Get the current active submission for the candidate."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    candidate_id = current_user["sub"]
    with get_db() as db:
        # First check for any submitted/processing submissions (status dashboard)
        active = db.execute(
            """SELECT * FROM candidate_submissions
               WHERE candidate_id=? AND status IN ('submitted', 'processing', 'completed')
               ORDER BY submitted_at DESC LIMIT 1""",
            (candidate_id,),
        ).fetchone()

        if active:
            sub = dict(active)
            sub["sections_requested"] = json.loads(sub["sections_requested"]) if sub["sections_requested"] else []
            # Load draft data
            drafts = db.execute(
                "SELECT * FROM candidate_draft_data WHERE submission_id=?", (sub["id"],)
            ).fetchall()
            sub["sections"] = {}
            for d in drafts:
                dd = dict(d)
                sub["sections"][dd["section"]] = {
                    "data": json.loads(dd["data"]),
                    "completed": bool(dd["completed"]),
                }
            return sub

        # Otherwise check for draft
        draft = db.execute(
            """SELECT * FROM candidate_submissions
               WHERE candidate_id=? AND status='draft'
               ORDER BY created_at DESC LIMIT 1""",
            (candidate_id,),
        ).fetchone()

        if draft:
            sub = dict(draft)
            sub["sections_requested"] = json.loads(sub["sections_requested"]) if sub["sections_requested"] else []
            drafts = db.execute(
                "SELECT * FROM candidate_draft_data WHERE submission_id=?", (sub["id"],)
            ).fetchall()
            sub["sections"] = {}
            for d in drafts:
                dd = dict(d)
                sub["sections"][dd["section"]] = {
                    "data": json.loads(dd["data"]),
                    "completed": bool(dd["completed"]),
                }
            return sub

        return None


@router.get("/{submission_id}")
async def get_submission(submission_id: str, current_user: dict = Depends(get_current_user)):
    """Get a specific submission with all its section data."""
    with get_db() as db:
        sub = db.execute(
            "SELECT * FROM candidate_submissions WHERE id=?", (submission_id,)
        ).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")

        result = dict(sub)
        result["sections_requested"] = json.loads(result["sections_requested"]) if result["sections_requested"] else []

        # Verify access
        if current_user["type"] == "candidate" and result["candidate_id"] != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Not your submission")

        # Load section data
        drafts = db.execute(
            "SELECT * FROM candidate_draft_data WHERE submission_id=?", (submission_id,)
        ).fetchall()
        result["sections"] = {}
        for d in drafts:
            dd = dict(d)
            result["sections"][dd["section"]] = {
                "data": json.loads(dd["data"]),
                "completed": bool(dd["completed"]),
            }

        return result


# ── Save Section Data ─────────────────────────────────────────────

@router.put("/{submission_id}/section/{section}")
async def save_section(
    submission_id: str,
    section: str,
    body: SaveSectionRequest,
    current_user: dict = Depends(get_current_user),
):
    """Save draft data for a specific section."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        sub = db.execute(
            "SELECT * FROM candidate_submissions WHERE id=? AND candidate_id=?",
            (submission_id, candidate_id),
        ).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")
        if dict(sub)["status"] != "draft":
            raise HTTPException(status_code=400, detail="Cannot modify a submitted application")

        # Upsert the section data
        existing = db.execute(
            "SELECT id FROM candidate_draft_data WHERE submission_id=? AND section=?",
            (submission_id, section),
        ).fetchone()

        data_json = json.dumps(body.data)
        if existing:
            db.execute(
                "UPDATE candidate_draft_data SET data=?, completed=?, updated_at=? WHERE id=?",
                (data_json, 1 if body.completed else 0, now, dict(existing)["id"]),
            )
        else:
            db.execute(
                """INSERT INTO candidate_draft_data (id, submission_id, candidate_id, section, data, completed, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (generate_id(), submission_id, candidate_id, section, data_json, 1 if body.completed else 0, now),
            )

        # Also update candidate profile fields if this is the personal section
        if section == "personal" and body.data:
            updates = []
            params = []
            for field in ["first_name", "last_name", "phone", "date_of_birth", "address_line1",
                          "address_line2", "city", "postcode", "profession", "registration_body",
                          "registration_number"]:
                if field in body.data and body.data[field]:
                    updates.append(f"{field}=?")
                    params.append(body.data[field])
            if updates:
                params.append(now)
                params.append(candidate_id)
                db.execute(
                    f"UPDATE candidates SET {', '.join(updates)}, updated_at=? WHERE id=?",
                    params,
                )

    return {"status": "saved", "section": section, "completed": body.completed}


# ── Post-Submission Section Update ────────────────────────────────

# Sections that can be edited after submission (additive — can add more data)
EDITABLE_AFTER_SUBMISSION = {"references", "training", "cv", "employment"}
# Sections locked once their check is verified
LOCKED_CHECK_KEYS = {"identity", "rtw", "dbs", "registration", "personal"}


class PostSubmissionUpdateRequest(BaseModel):
    section: str
    data: dict


@router.post("/{submission_id}/update-section")
async def update_section_post_submission(
    submission_id: str,
    body: PostSubmissionUpdateRequest,
    current_user: dict = Depends(get_current_user),
):
    """Allow candidates to update specific sections after submission.
    
    Rules:
    - references, training, cv, employment: always editable (additive)
    - identity, rtw, dbs, registration, personal: locked once check is verified
    """
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    candidate_id = current_user["sub"]
    section = body.section
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        sub = db.execute(
            "SELECT * FROM candidate_submissions WHERE id=? AND candidate_id=?",
            (submission_id, candidate_id),
        ).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")

        sub_data = dict(sub)
        if sub_data["status"] == "draft":
            raise HTTPException(status_code=400, detail="Use the regular save endpoint for draft submissions")

        # Check if section is editable
        if section in LOCKED_CHECK_KEYS:
            raise HTTPException(
                status_code=400,
                detail=f"The {section} section is locked after submission. Contact your agency if changes are needed.",
            )

        if section not in EDITABLE_AFTER_SUBMISSION:
            raise HTTPException(status_code=400, detail=f"Section '{section}' cannot be edited after submission")

        # Save the updated section data
        existing = db.execute(
            "SELECT id FROM candidate_draft_data WHERE submission_id=? AND section=?",
            (submission_id, section),
        ).fetchone()

        data_json = json.dumps(body.data)
        if existing:
            db.execute(
                "UPDATE candidate_draft_data SET data=?, completed=1, updated_at=? WHERE id=?",
                (data_json, now, dict(existing)["id"]),
            )
        else:
            db.execute(
                """INSERT INTO candidate_draft_data (id, submission_id, candidate_id, section, data, completed, updated_at)
                   VALUES (?, ?, ?, ?, ?, 1, ?)""",
                (generate_id(), submission_id, candidate_id, section, data_json, now),
            )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (?, 'submission', ?, 'section_updated_post_submission', ?, ?, ?)""",
            (generate_id(), submission_id, candidate_id,
             json.dumps({"section": section, "submission_status": sub_data["status"]}),
             now),
        )

    # Re-process the updated section
    from app.services.trigger_engine import TriggerEngine
    try:
        if section == "cv":
            TriggerEngine._run_cv(candidate_id, body.data)
        elif section == "references":
            TriggerEngine._run_references(candidate_id, body.data)
        elif section == "training":
            TriggerEngine._run_training(candidate_id, body.data)
        elif section == "employment":
            # Send verification emails for any new entries with verifier details
            TriggerEngine._run_employment_verifications(candidate_id)
    except Exception:
        pass  # Section data saved even if re-processing fails

    # Re-evaluate compliance
    from app.services.compliance_engine import ComplianceEngine
    try:
        ComplianceEngine.evaluate_candidate(candidate_id)
    except Exception:
        pass

    return {
        "status": "updated",
        "section": section,
        "message": f"{section.replace('_', ' ').title()} section updated successfully. Checks are being re-processed.",
    }


# ── Validate Submission ───────────────────────────────────────────

@router.post("/{submission_id}/validate")
async def validate_submission(submission_id: str, current_user: dict = Depends(get_current_user)):
    """Run validation checks on all sections before allowing consent."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    with get_db() as db:
        sub = db.execute(
            "SELECT * FROM candidate_submissions WHERE id=? AND candidate_id=?",
            (submission_id, current_user["sub"]),
        ).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")

        sub_data = dict(sub)
        sections_requested = json.loads(sub_data["sections_requested"]) if sub_data["sections_requested"] else []

        drafts = db.execute(
            "SELECT * FROM candidate_draft_data WHERE submission_id=?", (submission_id,)
        ).fetchall()
        sections = {}
        for d in drafts:
            dd = dict(d)
            sections[dd["section"]] = {
                "data": json.loads(dd["data"]),
                "completed": bool(dd["completed"]),
            }

        errors = []
        warnings = []

        for section_name in sections_requested:
            if section_name not in sections:
                errors.append({"section": section_name, "message": f"{section_name} section has not been filled in"})
                continue
            sec = sections[section_name]
            if not sec["completed"]:
                errors.append({"section": section_name, "message": f"{section_name} section is incomplete"})

            data = sec["data"]

            # Section-specific validation
            # Skip field-level validation for sections handled by TrustID in manual mode
            is_trustid_manual = data.get("trustid_manual", False)

            if section_name == "personal":
                for req in ["first_name", "last_name"]:
                    if not data.get(req):
                        errors.append({"section": "personal", "message": f"{req.replace('_', ' ').title()} is required"})
            elif section_name == "identity":
                if not is_trustid_manual:
                    if not data.get("document_type"):
                        errors.append({"section": "identity", "message": "Document type is required"})
                    if not data.get("document_file_name"):
                        errors.append({"section": "identity", "message": "Identity document upload is required"})
                    if not data.get("selfie_file_name"):
                        errors.append({"section": "identity", "message": "Selfie photo is required"})
            elif section_name == "rtw":
                if not is_trustid_manual:
                    method = data.get("method", "uk_citizen")
                    if method == "share_code" and not data.get("share_code"):
                        errors.append({"section": "rtw", "message": "Share code is required for non-UK citizens"})
            elif section_name == "dbs":
                pass  # DBS has no required fields in either mode
            elif section_name == "references":
                refs = data.get("referees", [])
                if len(refs) < 2:
                    errors.append({"section": "references", "message": "At least 2 references are required"})
                for i, ref in enumerate(refs):
                    if not ref.get("name") or not ref.get("email"):
                        errors.append({"section": "references", "message": f"Reference {i+1}: name and email are required"})

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "sections_completed": sum(1 for s in sections.values() if s["completed"]),
            "sections_required": len(sections_requested),
        }


# ── Consent & Submit ──────────────────────────────────────────────

@router.post("/{submission_id}/consent")
async def submit_with_consent(
    submission_id: str,
    body: ConsentRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Record consent and submit the application for automated processing."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Candidates only")

    if not body.consent_given:
        raise HTTPException(status_code=400, detail="Consent is required to proceed")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent", "")

    with get_db() as db:
        sub = db.execute(
            "SELECT * FROM candidate_submissions WHERE id=? AND candidate_id=?",
            (submission_id, candidate_id),
        ).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")
        if dict(sub)["status"] != "draft":
            raise HTTPException(status_code=400, detail="This application has already been submitted")

        # Record consent logs
        for consent_type in ["vetting_consent", "data_processing", "dbs_consent"]:
            db.execute(
                """INSERT INTO consent_logs (id, candidate_id, submission_id, consent_type,
                   consent_given, ip_address, user_agent, privacy_policy_version, terms_version, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (generate_id(), candidate_id, submission_id, consent_type,
                 1, ip_address, user_agent, body.privacy_policy_version, body.terms_version, now),
            )

        # Update submission status
        db.execute(
            """UPDATE candidate_submissions SET
               status='submitted', consent_given=1, consent_timestamp=?,
               consent_ip_address=?, privacy_policy_version=?, terms_version=?,
               submitted_at=?
               WHERE id=?""",
            (now, ip_address, body.privacy_policy_version, body.terms_version, now, submission_id),
        )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (?, 'submission', ?, 'consent_submitted', ?, ?, ?)""",
            (generate_id(), submission_id, candidate_id,
             json.dumps({"consent_types": ["vetting_consent", "data_processing", "dbs_consent"],
                          "ip_address": ip_address, "privacy_policy": body.privacy_policy_version}),
             now),
        )

    # Trigger automated processing in the background
    from app.services.trigger_engine import TriggerEngine
    TriggerEngine.process_submission(submission_id)

    return {"status": "submitted", "message": "Application submitted successfully. Automated checks are now running."}


# ── Processing Status (for candidate status dashboard) ────────────

@router.get("/{submission_id}/status")
async def get_processing_status(submission_id: str, current_user: dict = Depends(get_current_user)):
    """Get the processing status of a submission (status-only view for candidates)."""
    with get_db() as db:
        sub = db.execute(
            "SELECT * FROM candidate_submissions WHERE id=?", (submission_id,)
        ).fetchone()
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")

        sub_data = dict(sub)
        candidate_id = sub_data["candidate_id"]

        if current_user["type"] == "candidate" and candidate_id != current_user["sub"]:
            raise HTTPException(status_code=403, detail="Not your submission")

        # Get check statuses (status only, not detailed analysis)
        check_statuses = {}

        # Personal Details — verified when core candidate fields are populated
        cand = db.execute(
            "SELECT first_name, last_name, email, phone, date_of_birth FROM candidates WHERE id=?",
            (candidate_id,),
        ).fetchone()
        if cand:
            cand_data = dict(cand)
            has_name = bool(cand_data.get("first_name") and cand_data.get("last_name"))
            has_contact = bool(cand_data.get("email"))
            if has_name and has_contact:
                check_statuses["personal"] = {"status": "verified", "label": "Personal Details Complete"}
            else:
                missing = []
                if not has_name:
                    missing.append("name")
                if not has_contact:
                    missing.append("email")
                check_statuses["personal"] = {"status": "processing", "label": f"Missing: {', '.join(missing)}"}
        else:
            check_statuses["personal"] = {"status": "pending", "label": "Personal Details Pending"}

        # Identity
        identity = db.execute(
            "SELECT status, result FROM identity_checks WHERE candidate_id=? ORDER BY started_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        if identity:
            id_data = dict(identity)
            if id_data["result"] == "clear":
                check_statuses["identity"] = {"status": "verified", "label": "Identity Verified"}
            elif id_data["status"] == "pending":
                check_statuses["identity"] = {"status": "processing", "label": "Identity Check Processing"}
            else:
                check_statuses["identity"] = {"status": "review", "label": "Identity Check Under Review"}
        else:
            check_statuses["identity"] = {"status": "pending", "label": "Identity Check Pending"}

        # Right to Work
        rtw = db.execute(
            "SELECT status, verified FROM right_to_work_checks WHERE candidate_id=? ORDER BY checked_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        if rtw:
            rtw_data = dict(rtw)
            if rtw_data["verified"]:
                check_statuses["rtw"] = {"status": "verified", "label": "Right to Work Verified"}
            else:
                check_statuses["rtw"] = {"status": "processing", "label": "Right to Work Processing"}
        else:
            check_statuses["rtw"] = {"status": "pending", "label": "Right to Work Pending"}

        # DBS
        dbs = db.execute(
            "SELECT status, result FROM dbs_checks WHERE candidate_id=? ORDER BY submitted_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        if dbs:
            dbs_data = dict(dbs)
            if dbs_data["result"] == "clear":
                check_statuses["dbs"] = {"status": "verified", "label": "DBS Check Clear"}
            elif dbs_data["status"] in ("pending", "processing"):
                check_statuses["dbs"] = {"status": "processing", "label": "DBS Check Submitted - Processing"}
            else:
                check_statuses["dbs"] = {"status": "review", "label": "DBS Check Under Review"}
        else:
            check_statuses["dbs"] = {"status": "pending", "label": "DBS Check Pending"}

        # CV
        cv = db.execute(
            "SELECT status FROM cv_analyses WHERE candidate_id=? ORDER BY analysed_at DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        if cv:
            check_statuses["cv"] = {"status": "verified", "label": "CV Validated"}
        else:
            check_statuses["cv"] = {"status": "pending", "label": "CV Analysis Pending"}

        # Registration
        reg = db.execute(
            "SELECT is_active FROM registration_checks WHERE candidate_id=? ORDER BY last_checked DESC LIMIT 1",
            (candidate_id,),
        ).fetchone()
        if reg:
            if dict(reg)["is_active"]:
                check_statuses["registration"] = {"status": "verified", "label": "Registration Active"}
            else:
                check_statuses["registration"] = {"status": "review", "label": "Registration Under Review"}
        else:
            check_statuses["registration"] = {"status": "pending", "label": "Registration Check Pending"}

        # References
        refs = db.execute(
            "SELECT status FROM references_ WHERE candidate_id=?", (candidate_id,)
        ).fetchall()
        completed_refs = sum(1 for r in refs if dict(r)["status"] == "completed")
        total_refs = len(refs)
        if completed_refs >= 2:
            check_statuses["references"] = {"status": "verified", "label": f"References Complete ({completed_refs}/{total_refs})"}
        elif total_refs > 0:
            check_statuses["references"] = {"status": "processing", "label": f"References: {completed_refs}/{total_refs} Received"}
        else:
            check_statuses["references"] = {"status": "pending", "label": "References Pending"}

        # Employment
        emp_count = db.execute(
            "SELECT COUNT(*) as cnt FROM employment_verifications WHERE candidate_id=? AND status='completed'",
            (candidate_id,),
        ).fetchone()
        emp_total = db.execute(
            "SELECT COUNT(*) as cnt FROM employment_history WHERE candidate_id=?",
            (candidate_id,),
        ).fetchone()
        emp_done = dict(emp_count)["cnt"] if emp_count else 0
        emp_all = dict(emp_total)["cnt"] if emp_total else 0
        if emp_done > 0:
            check_statuses["employment"] = {"status": "verified", "label": f"Employment: {emp_done}/{emp_all} Verified"}
        elif emp_all > 0:
            check_statuses["employment"] = {"status": "processing", "label": f"Employment Verification in Progress"}
        else:
            check_statuses["employment"] = {"status": "pending", "label": "Employment Verification Pending"}

        # Training
        training = db.execute(
            "SELECT COUNT(*) as cnt FROM training_certificates WHERE candidate_id=?",
            (candidate_id,),
        ).fetchone()
        if training and dict(training)["cnt"] > 0:
            check_statuses["training"] = {"status": "verified", "label": f"{dict(training)['cnt']} Certificates Recorded"}
        else:
            check_statuses["training"] = {"status": "pending", "label": "Training Certificates Pending"}

        # Compliance score
        compliance = db.execute(
            "SELECT score, overall_status, cqc_ready FROM compliance_records WHERE candidate_id=?",
            (candidate_id,),
        ).fetchone()

        return {
            "submission_id": submission_id,
            "submission_status": sub_data["status"],
            "submitted_at": sub_data["submitted_at"],
            "check_statuses": check_statuses,
            "compliance_score": dict(compliance)["score"] if compliance else 0,
            "compliance_status": dict(compliance)["overall_status"] if compliance else "pending",
            "cqc_ready": bool(dict(compliance)["cqc_ready"]) if compliance else False,
        }


# ── Re-vet Request Info (public) ──────────────────────────────────

@router.get("/revet-info/{token}")
async def get_revet_info(token: str):
    """Public endpoint: get re-vet request details by token."""
    with get_db() as db:
        row = db.execute(
            """SELECT rr.*, a.name as agency_name, c.first_name, c.last_name, c.email
               FROM revet_requests rr
               JOIN agencies a ON rr.agency_id = a.id
               JOIN candidates c ON rr.candidate_id = c.id
               WHERE rr.token=? AND rr.status='pending'""",
            (token,),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Invalid or expired re-vet link")

        data = dict(row)
        return {
            "token": data["token"],
            "agency_name": data["agency_name"],
            "candidate_name": f"{data['first_name']} {data['last_name']}",
            "candidate_email": data["email"],
            "sections": json.loads(data["sections"]),
        }
