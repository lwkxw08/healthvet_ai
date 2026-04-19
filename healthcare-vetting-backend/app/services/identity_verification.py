"""
Identity Verification Service
Simulates integration with Onfido / Yoti / Trulioo APIs.

In production, replace mock logic with real Onfido SDK + API calls:
1. POST /api/checks/identity/sdk-token → calls Onfido API to create applicant + SDK token
2. Frontend uses Onfido Smart Capture SDK with the token to capture document + selfie
3. Onfido webhook callback → updates check status
4. POST /api/checks/identity → finalises and stores results

Current implementation simulates this entire flow server-side.
"""
import json
import random
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id


class IdentityVerificationService:
    """Automated identity verification using document + selfie + liveness detection."""

    PROVIDERS = {
        "onfido": {"name": "Onfido", "cost_gbp": 2.0},
        "yoti": {"name": "Yoti", "cost_gbp": 1.5},
        "trulioo": {"name": "Trulioo", "cost_gbp": 2.5},
    }

    # Document types accepted by Onfido
    DOCUMENT_TYPES = {
        "passport": "Passport",
        "driving_licence": "Driving Licence",
        "national_identity_card": "National Identity Card",
        "residence_permit": "Residence Permit",
    }

    @staticmethod
    def create_sdk_token(candidate_id: str) -> dict:
        """Create an SDK token for the Onfido Smart Capture SDK.

        In production, this would:
        1. Create an Onfido applicant via POST https://api.onfido.com/v3.6/applicants
        2. Create a workflow run via POST https://api.onfido.com/v3.6/workflow_runs
        3. Generate an SDK token via POST https://api.onfido.com/v3.6/sdk_token

        Returns a simulated token for the frontend to use.
        """
        applicant_id = f"onfido-applicant-{generate_id()[:8]}"
        workflow_run_id = f"onfido-wfr-{generate_id()[:8]}"
        sdk_token = f"simulated-sdk-token-{generate_id()}"

        return {
            "sdk_token": sdk_token,
            "applicant_id": applicant_id,
            "workflow_run_id": workflow_run_id,
        }

    @staticmethod
    def initiate_check(
        candidate_id: str,
        document_type: str = "passport",
        provider: str = "onfido",
        document_file_name: str | None = None,
        selfie_file_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        date_of_birth: str | None = None,
    ) -> dict:
        check_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute(
                """INSERT INTO identity_checks
                   (id, candidate_id, provider, status, document_type, started_at)
                   VALUES (%s, %s, %s, 'processing', %s, %s)""",
                (check_id, candidate_id, provider, document_type, now),
            )

            # Simulate Onfido API verification pipeline:
            # 1. Document report (authenticity, MRZ, visual checks)
            # 2. Facial similarity report (selfie vs document photo)
            # 3. Liveness detection (motion analysis)
            result = IdentityVerificationService._simulate_verification(
                document_type, document_file_name, selfie_file_name,
                first_name, last_name, date_of_birth,
            )

            db.execute(
                """UPDATE identity_checks SET
                   status=%s, document_authenticity=%s, facial_match_score=%s,
                   liveness_check=%s, address_verified=%s, result=%s, details=%s, completed_at=%s
                   WHERE id=%s""",
                (
                    result["status"],
                    result["document_authenticity"],
                    result["facial_match_score"],
                    result["liveness_check"],
                    1 if result["address_verified"] else 0,
                    result["result"],
                    json.dumps(result["details"]),
                    now,
                    check_id,
                ),
            )

            # Update candidate status if passed
            if result["result"] == "clear":
                db.execute(
                    "UPDATE candidates SET status='id_verified', updated_at=%s WHERE id=%s",
                    (now, candidate_id),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'identity_check', %s, 'completed', 'system', %s, %s)""",
                (generate_id(), check_id, json.dumps(result), now),
            )

            db.execute("SELECT * FROM identity_checks WHERE id=%s", (check_id,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def _simulate_verification(
        document_type: str,
        document_file_name: str | None = None,
        selfie_file_name: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        date_of_birth: str | None = None,
    ) -> dict:
        """Simulate Onfido-style verification pipeline.

        In production, Onfido runs these report types:
        - document: Checks MRZ/barcode, visual authenticity, data consistency
        - facial_similarity_photo: Compares selfie to document photo
        - facial_similarity_motion: Liveness detection via motion analysis

        Replace with real Onfido webhook handler in production.
        """
        # Higher pass rate when both document and selfie are provided
        has_document = document_file_name is not None
        has_selfie = selfie_file_name is not None
        base_pass_rate = 0.93 if (has_document and has_selfie) else 0.88
        is_pass = random.random() < base_pass_rate

        facial_score = round(
            random.uniform(0.85, 0.99) if is_pass else random.uniform(0.3, 0.6), 2
        )

        # Simulate individual Onfido sub-check results
        document_report = {
            "mrz_check": "clear" if is_pass else "consider",
            "visual_authenticity": "clear" if is_pass else "suspected",
            "data_consistency": "clear" if is_pass else "consider",
            "image_integrity": "clear" if (is_pass or random.random() < 0.8) else "rejected",
            "data_validation": "clear" if is_pass else "consider",
        }

        facial_similarity_report = {
            "face_match_result": "clear" if is_pass else "consider",
            "face_match_score": facial_score,
            "image_quality": "sufficient" if (has_selfie or random.random() < 0.7) else "insufficient",
        }

        liveness_report = {
            "liveness_result": "clear" if is_pass else "consider",
            "motion_score": round(random.uniform(0.90, 0.99) if is_pass else random.uniform(0.2, 0.5), 2),
        }

        details = {
            "provider": "onfido",
            "api_version": "v3.6",
            "document_type": document_type,
            "document_type_label": IdentityVerificationService.DOCUMENT_TYPES.get(
                document_type, document_type.replace("_", " ").title()
            ),
            "document_file": document_file_name,
            "selfie_file": selfie_file_name,
            "processing_time_seconds": round(random.uniform(45, 120), 1),
            "reports": {
                "document": document_report,
                "facial_similarity": facial_similarity_report,
                "liveness": liveness_report,
            },
        }

        if first_name or last_name:
            details["applicant_name"] = f"{first_name or ''} {last_name or ''}".strip()
        if date_of_birth:
            details["applicant_dob"] = date_of_birth

        return {
            "status": "completed",
            "document_authenticity": "verified" if is_pass else "suspected_fraud",
            "facial_match_score": facial_score,
            "liveness_check": "passed" if is_pass else "failed",
            "address_verified": is_pass,
            "result": "clear" if is_pass else "consider",
            "details": details,
        }

    @staticmethod
    def get_check(check_id: str) -> dict:
        with get_db() as db:
            db.execute("SELECT * FROM identity_checks WHERE id=%s", (check_id,))
            row = db.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_checks_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM identity_checks WHERE candidate_id=%s ORDER BY started_at DESC",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]
