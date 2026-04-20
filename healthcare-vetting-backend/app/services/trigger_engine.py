"""
Automated Trigger Engine - fires all vetting checks after candidate consent.
This is the core of the "candidate submits, system automates" architecture.
"""
import json
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id
from app.services.identity_verification import IdentityVerificationService
from app.services.right_to_work import RightToWorkService
from app.services.dbs_checks import DBSCheckService
from app.services.cv_analysis import CVAnalysisService
from app.services.registration_checks import RegistrationCheckService
from app.services.reference_automation import ReferenceAutomationService
from app.services.employment_verification import EmploymentVerificationService
from app.services.compliance_engine import ComplianceEngine
from app.services.trustid_checks import TrustIDService

import logging
logger = logging.getLogger(__name__)


class TriggerEngine:
    """Automated check trigger engine - fires all checks after consent."""

    @staticmethod
    def process_submission(submission_id: str) -> dict:
        """Process a submitted application - fire all relevant checks."""
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute(
                "SELECT * FROM candidate_submissions WHERE id=%s", (submission_id,)
            )
            sub = db.fetchone()
            if not sub:
                return {"error": "Submission not found"}

            sub_data = dict(sub)
            candidate_id = sub_data["candidate_id"]
            sections = json.loads(sub_data["sections_requested"]) if sub_data["sections_requested"] else []

            # Mark as processing
            db.execute(
                "UPDATE candidate_submissions SET status='processing', processing_started_at=%s WHERE id=%s",
                (now, submission_id),
            )

            # Load all section draft data
            db.execute(
                "SELECT * FROM candidate_draft_data WHERE submission_id=%s", (submission_id,)
            )
            drafts = db.fetchall()
            section_data = {}
            for d in drafts:
                dd = dict(d)
                section_data[dd["section"]] = json.loads(dd["data"])

        # Fire checks for each section
        results = {}

        # Check TrustID manual mode for identity/rtw/dbs
        # When in manual mode, create TrustID pending_admin records instead of running simulated checks
        identity_manual = TrustIDService.get_submission_mode("identity_verification") == "manual"
        rtw_manual = TrustIDService.get_submission_mode("right_to_work") == "manual"
        dbs_manual = TrustIDService.get_submission_mode("dbs_check") == "manual"

        trustid_check_types = []

        if "identity" in sections:
            if identity_manual:
                trustid_check_types.append("identity_verification")
                results["identity"] = "pending_trustid_manual"
            elif "identity" in section_data:
                results["identity"] = TriggerEngine._run_identity(candidate_id, section_data["identity"])

        if "rtw" in sections:
            if rtw_manual:
                trustid_check_types.append("right_to_work")
                results["rtw"] = "pending_trustid_manual"
            elif "rtw" in section_data:
                results["rtw"] = TriggerEngine._run_rtw(candidate_id, section_data["rtw"])

        if "dbs" in sections:
            if dbs_manual:
                trustid_check_types.append("dbs_check")
                results["dbs"] = "pending_trustid_manual"
            else:
                results["dbs"] = TriggerEngine._run_dbs(candidate_id, section_data.get("dbs", {}))

        # Create TrustID check records for manual-mode sections
        if trustid_check_types:
            try:
                # Get candidate info for TrustID records
                with get_db() as db:
                    db.execute(
                        "SELECT first_name, last_name, email, date_of_birth FROM candidates WHERE id=%s",
                        (candidate_id,),
                    )
                    cand = db.fetchone()
                    cand_data = dict(cand) if cand else {}

                candidate_name = f"{cand_data.get('first_name', '')} {cand_data.get('last_name', '')}".strip()
                candidate_email = cand_data.get("email", "")
                candidate_dob = cand_data.get("date_of_birth", "")

                for check_type in trustid_check_types:
                    TrustIDService.create_check(
                        candidate_id=candidate_id,
                        check_type=check_type,
                        submitted_by="trigger_engine",
                        candidate_name=candidate_name or None,
                        candidate_email=candidate_email or None,
                        candidate_dob=candidate_dob or None,
                    )
                logger.info(f"Created TrustID pending_admin records for {trustid_check_types} (candidate {candidate_id})")

                # Send TrustID submission confirmation email to candidate
                if candidate_email:
                    try:
                        from app.services.email_service import EmailService
                        EmailService.send_trustid_submission_confirmation(
                            candidate_email=candidate_email,
                            candidate_name=candidate_name or "Candidate",
                            check_types=trustid_check_types,
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send TrustID confirmation email: {e}")
            except Exception as e:
                logger.error(f"Failed to create TrustID check records: {e}")

        if "cv" in sections:
            results["cv"] = TriggerEngine._run_cv(candidate_id, section_data.get("cv", {}))

        if "registration" in sections:
            results["registration"] = TriggerEngine._run_registration(candidate_id, section_data.get("registration", {}))

        if "references" in sections and "references" in section_data:
            results["references"] = TriggerEngine._run_references(candidate_id, section_data["references"])

        if "training" in sections and "training" in section_data:
            results["training"] = TriggerEngine._run_training(candidate_id, section_data["training"])

        # Send employment verification emails for any entries with verifier details
        results["employment_verification"] = TriggerEngine._run_employment_verifications(candidate_id)

        # Run compliance evaluation
        ComplianceEngine.evaluate_candidate(candidate_id)

        # Mark as completed
        completed_at = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE candidate_submissions SET status='completed', processing_completed_at=%s WHERE id=%s",
                (completed_at, submission_id),
            )

            # If this is a re-vet, mark the re-vet request as completed
            db.execute(
                "SELECT id FROM revet_requests WHERE submission_id=%s", (submission_id,)
            )
            revet = db.fetchone()
            if revet:
                db.execute(
                    "UPDATE revet_requests SET status='completed', completed_at=%s WHERE id=%s",
                    (completed_at, dict(revet)["id"]),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'submission', %s, 'processing_completed', 'trigger_engine', %s, %s)""",
                (generate_id(), submission_id,
                 json.dumps({"sections_processed": list(results.keys()), "candidate_id": candidate_id}),
                 completed_at),
            )

        return {"status": "completed", "results": results}

    @staticmethod
    def _run_identity(candidate_id: str, data: dict) -> str:
        """Fire identity verification check."""
        try:
            # Get candidate name for the check
            with get_db() as db:
                db.execute(
                    "SELECT first_name, last_name, date_of_birth FROM candidates WHERE id=%s",
                    (candidate_id,),
                )
                cand = db.fetchone()
                cand_data = dict(cand) if cand else {}

            IdentityVerificationService.create_sdk_token(candidate_id)
            IdentityVerificationService.initiate_check(
                candidate_id=candidate_id,
                document_type=data.get("document_type", "passport"),
                document_file_name=data.get("document_file_name"),
                selfie_file_name=data.get("selfie_file_name"),
                first_name=cand_data.get("first_name"),
                last_name=cand_data.get("last_name"),
                date_of_birth=cand_data.get("date_of_birth"),
            )
            return "completed"
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _run_rtw(candidate_id: str, data: dict) -> str:
        """Fire right to work check and notify agency for imposter declaration."""
        try:
            method = data.get("method", "uk_citizen")
            if method == "uk_citizen":
                RightToWorkService.verify_uk_citizen(
                    candidate_id=candidate_id,
                    document_type=data.get("document_type", "uk_passport"),
                    nationality=data.get("nationality", "british"),
                    document_reference=data.get("document_reference"),
                    ni_number=data.get("ni_number"),
                )
            else:
                RightToWorkService.verify_share_code(
                    candidate_id=candidate_id,
                    share_code=data.get("share_code", ""),
                )

            # Notify the agency that an imposter declaration is required
            TriggerEngine._notify_agency_imposter_check(candidate_id)

            return "completed"
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _notify_agency_imposter_check(candidate_id: str):
        """Create a notification and send email to the agency when imposter declaration is needed."""
        try:
            with get_db() as db:
                # Get candidate details
                db.execute("SELECT first_name, last_name, email FROM candidates WHERE id=%s", (candidate_id,))
                cand = db.fetchone()
                if not cand:
                    return
                cand_d = dict(cand)
                cand_name = f"{cand_d.get('first_name', '')} {cand_d.get('last_name', '')}".strip() or "Unknown"

                # Get linked agency
                db.execute(
                    "SELECT a.id, a.name, a.email, a.contact_email FROM agencies a "
                    "JOIN agency_candidates ac ON a.id = ac.agency_id "
                    "WHERE ac.candidate_id=%s LIMIT 1",
                    (candidate_id,),
                )
                agency = db.fetchone()
                if not agency:
                    return
                agency_data = dict(agency)
                agency_email = agency_data.get("email") or agency_data.get("contact_email")

                # Check if imposter declaration already exists
                db.execute(
                    "SELECT id FROM imposter_declarations WHERE candidate_id=%s AND agency_id=%s",
                    (candidate_id, agency_data["id"]),
                )
                existing = db.fetchone()
                if existing:
                    return  # Already declared

                # Create in-app notification
                now = datetime.now(timezone.utc).isoformat()
                db.execute(
                    """INSERT INTO notifications (id, user_id, user_type, category, title, message, link, created_at, read)
                       VALUES (%s, %s, 'agency', 'compliance', %s, %s, %s, %s, 0)""",
                    (
                        generate_id(),
                        agency_data["id"],
                        f"Imposter Declaration Required - {cand_name}",
                        f"Right to Work check completed for {cand_name}. An imposter declaration is required before RTW compliance can be confirmed. Please verify the candidate's identity in person or via compliant video call.",
                        f"/candidates/{candidate_id}",
                        now,
                    ),
                )

            # Send email notification to agency
            if agency_email:
                try:
                    from app.services.email_templates import EmailTemplateService
                    import os
                    base_url = os.environ.get("BASE_URL", "https://app.viperai.io")
                    EmailTemplateService.send_email(
                        template_key="imposter_check_required",
                        recipient_email=agency_email,
                        recipient_name=agency_data.get("name", "Agency"),
                        variables={
                            "agency_name": agency_data.get("name", "Agency"),
                            "candidate_name": cand_name,
                            "candidate_id": candidate_id,
                            "imposter_check_link": f"{base_url}/candidates/{candidate_id}",
                        },
                    )
                except Exception as email_err:
                    logger.warning(f"Failed to send imposter check email: {email_err}")

        except Exception as e:
            logger.warning(f"Failed to notify agency for imposter check: {e}")

    @staticmethod
    def _run_dbs(candidate_id: str, data: dict) -> str:
        """Fire DBS check."""
        try:
            check_type = data.get("check_type", "enhanced")
            DBSCheckService.submit_check(candidate_id, check_type)
            return "completed"
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _run_cv(candidate_id: str, data: dict) -> str:
        """Fire CV analysis and process employment entries."""
        try:
            cv_text = data.get("cv_text", "")
            cv_file_name = data.get("cv_file_name")
            cv_file_bytes = None
            result = "skipped"

            # If no cv_text in the data dict, also check candidate_draft_data for CV text
            if not cv_text:
                try:
                    with get_db() as db:
                        db.execute(
                            "SELECT data FROM candidate_draft_data WHERE candidate_id=%s AND section='cv' ORDER BY updated_at DESC LIMIT 1",
                            (candidate_id,),
                        )
                        draft = db.fetchone()
                        if draft:
                            draft_data = json.loads(dict(draft)["data"]) if isinstance(dict(draft)["data"], str) else dict(draft)["data"]
                            cv_text = draft_data.get("cv_text", "")
                            if not cv_file_name:
                                cv_file_name = draft_data.get("cv_file_name")
                            logger.info("Found CV text in draft data for candidate %s: %d chars", candidate_id, len(cv_text))
                except Exception as e:
                    logger.warning("Failed to check draft data for CV text: %s", e)

            # If still no cv_text, try to find an uploaded CV document.
            # Check the modern `documents` table (R2-backed) first, then the
            # legacy `candidate_documents` table (local disk) for backwards
            # compatibility.
            if not cv_text and not cv_file_bytes:
                try:
                    with get_db() as db:
                        db.execute(
                            "SELECT id, file_name, storage_key, content_type FROM documents "
                            "WHERE candidate_id=%s AND category='cv' "
                            "ORDER BY created_at DESC LIMIT 1",
                            (candidate_id,),
                        )
                        doc = db.fetchone()
                        if doc:
                            doc_data = dict(doc)
                            if not cv_file_name:
                                cv_file_name = doc_data.get("file_name")
                            storage_key = doc_data.get("storage_key")
                            if storage_key:
                                try:
                                    from app.services.document_storage import get_storage_backend
                                    storage = get_storage_backend()
                                    file_obj, _name, _ct = storage.download(storage_key)
                                    cv_file_bytes = file_obj.read()
                                    logger.info(
                                        "Read CV file from documents table for candidate %s: key=%s bytes=%d",
                                        candidate_id, storage_key, len(cv_file_bytes),
                                    )
                                except Exception as e_dl:
                                    logger.warning(
                                        "Could not download CV from storage key %s: %s",
                                        storage_key, e_dl,
                                    )
                except Exception as e:
                    logger.warning("Failed to query documents table for CV: %s", e)

            if not cv_text and not cv_file_bytes:
                try:
                    with get_db() as db:
                        db.execute(
                            "SELECT file_name, file_path FROM candidate_documents WHERE candidate_id=%s AND document_type='cv' ORDER BY uploaded_at DESC LIMIT 1",
                            (candidate_id,),
                        )
                        doc = db.fetchone()
                        if doc:
                            doc_data = dict(doc)
                            if not cv_file_name:
                                cv_file_name = doc_data.get("file_name")
                            file_path = doc_data.get("file_path")
                            if file_path:
                                import os
                                if os.path.exists(file_path):
                                    with open(file_path, "rb") as f:
                                        cv_file_bytes = f.read()
                                    logger.info("Read CV file from local storage: %s", file_path)
                                else:
                                    try:
                                        from app.services.document_storage import get_storage_backend
                                        storage = get_storage_backend()
                                        file_obj, _name, _ct = storage.download(file_path)
                                        cv_file_bytes = file_obj.read()
                                        logger.info("Read CV file from cloud storage: %s", file_path)
                                    except Exception as e2:
                                        logger.warning("Could not read CV from cloud storage: %s", e2)
                except Exception as e:
                    logger.warning("Failed to retrieve uploaded CV document: %s", e)

            if cv_text or cv_file_bytes:
                CVAnalysisService.analyse_cv(candidate_id, cv_text or "", cv_file_name, cv_file_bytes)
                result = "completed"
            else:
                # If we still have no CV data at all, log it clearly and mark as skipped
                logger.warning("CV check skipped for candidate %s: no cv_text in submission data, no draft data, and no uploaded file found", candidate_id)

            # Create employment history entries (independent of CV text)
            entries = data.get("employment_entries", [])
            added = 0
            if entries:
                # Get existing entries to avoid duplicates
                with get_db() as db:
                    db.execute(
                        "SELECT employer_name, job_title FROM employment_history WHERE candidate_id=%s",
                        (candidate_id,),
                    )
                    existing = {
                        (row["employer_name"], row["job_title"])
                        for row in [dict(r) for r in db.fetchall()]
                    }
                for entry in entries:
                    if entry.get("employer_name") and entry.get("job_title"):
                        if (entry["employer_name"], entry["job_title"]) in existing:
                            continue
                        EmploymentVerificationService.add_employment_entry(
                            candidate_id=candidate_id,
                            employer_name=entry["employer_name"],
                            job_title=entry["job_title"],
                            start_date=entry.get("start_date"),
                            end_date=entry.get("end_date"),
                            reason_for_leaving=entry.get("reason_for_leaving"),
                            verifier_name=entry.get("verifier_name"),
                            verifier_email=entry.get("verifier_email"),
                            verifier_job_title=entry.get("verifier_job_title"),
                        )
                        added += 1
                result = "completed"

            # Trigger verification emails for any entries with verifier details
            if added > 0 or entries:
                TriggerEngine._run_employment_verifications(candidate_id)

            return result
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _run_registration(candidate_id: str, data: dict) -> str:
        """Fire professional registration check."""
        try:
            with get_db() as db:
                db.execute(
                    "SELECT registration_body, registration_number FROM candidates WHERE id=%s",
                    (candidate_id,),
                )
                cand = db.fetchone()
                if cand:
                    cand_data = dict(cand)
                    body = data.get("registration_body") or cand_data.get("registration_body")
                    reg_num = data.get("registration_number") or cand_data.get("registration_number")
                    if body and reg_num:
                        RegistrationCheckService.check_registration(candidate_id, body, reg_num)
                        return "completed"
            return "skipped"
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _run_references(candidate_id: str, data: dict) -> str:
        """Fire reference requests."""
        try:
            referees = data.get("referees", [])
            sent = 0
            for ref in referees:
                if ref.get("name") and ref.get("email"):
                    ReferenceAutomationService.create_reference_request(
                        candidate_id=candidate_id,
                        referee_name=ref["name"],
                        referee_email=ref["email"],
                        referee_organisation=ref.get("organisation"),
                        referee_job_title=ref.get("job_title"),
                    )
                    sent += 1
            return f"completed ({sent} requests sent)"
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _run_employment_verifications(candidate_id: str) -> str:
        """Send verification emails for all employment entries that have verifier details but no verification sent yet."""
        try:
            with get_db() as db:
                # Get all employment entries with verifier details
                db.execute(
                    "SELECT * FROM employment_history WHERE candidate_id=%s AND verifier_name IS NOT NULL AND verifier_email IS NOT NULL",
                    (candidate_id,),
                )
                entries = db.fetchall()

                # Get existing verifications to avoid duplicates
                db.execute(
                    "SELECT employment_id FROM employment_verifications WHERE candidate_id=%s",
                    (candidate_id,),
                )
                existing = db.fetchall()
                existing_ids = {dict(e)["employment_id"] for e in existing}

            sent = 0
            for entry in entries:
                ed = dict(entry)
                if ed["id"] not in existing_ids and ed.get("verifier_name") and ed.get("verifier_email"):
                    try:
                        EmploymentVerificationService.send_verification_request(
                            candidate_id=candidate_id,
                            employment_id=ed["id"],
                            verifier_name=ed["verifier_name"],
                            verifier_email=ed["verifier_email"],
                            verifier_job_title=ed.get("verifier_job_title"),
                        )
                        sent += 1
                    except Exception as e:
                        logger.warning(f"Failed to send employment verification for entry {ed['id']}: {e}")

            return f"completed ({sent} verification requests sent)"
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _run_training(candidate_id: str, data: dict) -> str:
        """Record training certificates."""
        try:
            certs = data.get("certificates", [])
            added = 0
            with get_db() as db:
                for cert in certs:
                    if cert.get("certificate_name"):
                        db.execute(
                            """INSERT INTO training_certificates
                               (id, candidate_id, certificate_name, category, provider,
                                issue_date, expiry_date, certificate_ref, created_at)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (generate_id(), candidate_id,
                             cert["certificate_name"],
                             cert.get("category", "mandatory"),
                             cert.get("provider"),
                             cert.get("issue_date"),
                             cert.get("expiry_date"),
                             cert.get("certificate_ref"),
                             datetime.now(timezone.utc).isoformat()),
                        )
                        added += 1
            return f"completed ({added} certificates recorded)"
        except Exception as e:
            return f"error: {str(e)}"
