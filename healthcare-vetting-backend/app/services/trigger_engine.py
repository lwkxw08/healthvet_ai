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


class TriggerEngine:
    """Automated check trigger engine - fires all checks after consent."""

    @staticmethod
    def process_submission(submission_id: str) -> dict:
        """Process a submitted application - fire all relevant checks."""
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            sub = db.execute(
                "SELECT * FROM candidate_submissions WHERE id=?", (submission_id,)
            ).fetchone()
            if not sub:
                return {"error": "Submission not found"}

            sub_data = dict(sub)
            candidate_id = sub_data["candidate_id"]
            sections = json.loads(sub_data["sections_requested"]) if sub_data["sections_requested"] else []

            # Mark as processing
            db.execute(
                "UPDATE candidate_submissions SET status='processing', processing_started_at=? WHERE id=?",
                (now, submission_id),
            )

            # Load all section draft data
            drafts = db.execute(
                "SELECT * FROM candidate_draft_data WHERE submission_id=?", (submission_id,)
            ).fetchall()
            section_data = {}
            for d in drafts:
                dd = dict(d)
                section_data[dd["section"]] = json.loads(dd["data"])

        # Fire checks for each section
        results = {}

        if "identity" in sections and "identity" in section_data:
            results["identity"] = TriggerEngine._run_identity(candidate_id, section_data["identity"])

        if "rtw" in sections and "rtw" in section_data:
            results["rtw"] = TriggerEngine._run_rtw(candidate_id, section_data["rtw"])

        if "dbs" in sections:
            results["dbs"] = TriggerEngine._run_dbs(candidate_id, section_data.get("dbs", {}))

        if "cv" in sections and "cv" in section_data:
            results["cv"] = TriggerEngine._run_cv(candidate_id, section_data["cv"])

        if "registration" in sections:
            results["registration"] = TriggerEngine._run_registration(candidate_id, section_data.get("registration", {}))

        if "references" in sections and "references" in section_data:
            results["references"] = TriggerEngine._run_references(candidate_id, section_data["references"])

        if "training" in sections and "training" in section_data:
            results["training"] = TriggerEngine._run_training(candidate_id, section_data["training"])

        # Run compliance evaluation
        ComplianceEngine.evaluate_candidate(candidate_id)

        # Mark as completed
        completed_at = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE candidate_submissions SET status='completed', processing_completed_at=? WHERE id=?",
                (completed_at, submission_id),
            )

            # If this is a re-vet, mark the re-vet request as completed
            revet = db.execute(
                "SELECT id FROM revet_requests WHERE submission_id=?", (submission_id,)
            ).fetchone()
            if revet:
                db.execute(
                    "UPDATE revet_requests SET status='completed', completed_at=? WHERE id=?",
                    (completed_at, dict(revet)["id"]),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'submission', ?, 'processing_completed', 'trigger_engine', ?, ?)""",
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
                cand = db.execute(
                    "SELECT first_name, last_name, date_of_birth FROM candidates WHERE id=?",
                    (candidate_id,),
                ).fetchone()
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
        """Fire right to work check."""
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
            return "completed"
        except Exception as e:
            return f"error: {str(e)}"

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
        """Fire CV analysis."""
        try:
            cv_text = data.get("cv_text", "")
            cv_file_name = data.get("cv_file_name")
            if cv_text:
                CVAnalysisService.analyse_cv(candidate_id, cv_text, cv_file_name)

                # Also create employment history entries from CV data
                entries = data.get("employment_entries", [])
                for entry in entries:
                    if entry.get("employer_name") and entry.get("job_title"):
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
                return "completed"
            return "skipped"
        except Exception as e:
            return f"error: {str(e)}"

    @staticmethod
    def _run_registration(candidate_id: str, data: dict) -> str:
        """Fire professional registration check."""
        try:
            with get_db() as db:
                cand = db.execute(
                    "SELECT registration_body, registration_number FROM candidates WHERE id=?",
                    (candidate_id,),
                ).fetchone()
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
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
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
