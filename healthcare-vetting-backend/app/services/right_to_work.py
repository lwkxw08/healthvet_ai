"""
Right to Work Verification Service
Simulates integration with UK Home Office digital share code system
and manual document-based checks for British/Irish citizens.
In production, replace mock logic with real API calls.
"""
import json
import re
import random
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id


class RightToWorkService:
    """Automated Right to Work verification using Home Office share codes
    or document-based checks for British/Irish citizens."""

    VISA_TYPES = [
        "Indefinite Leave to Remain",
        "Tier 2 (General)",
        "Skilled Worker Visa",
        "Health and Care Worker Visa",
        "Student Visa (with work rights)",
        "Pre-Settled Status",
        "Settled Status",
    ]

    # Documents that prove RTW for British/Irish citizens (per Home Office List A)
    UK_CITIZEN_DOCUMENTS = {
        "uk_passport": {
            "label": "UK Passport (current or expired)",
            "needs_ni": False,
            "list_a_item": 1,
        },
        "irish_passport": {
            "label": "Irish Passport or Passport Card (current or expired)",
            "needs_ni": False,
            "list_a_item": 2,
        },
        "birth_certificate": {
            "label": "UK Birth or Adoption Certificate",
            "needs_ni": True,
            "list_a_item": 6,
        },
        "adoption_certificate": {
            "label": "UK Adoption Certificate",
            "needs_ni": True,
            "list_a_item": 6,
        },
        "naturalisation_certificate": {
            "label": "Certificate of Registration or Naturalisation as a British Citizen",
            "needs_ni": True,
            "list_a_item": 6,
        },
    }

    @staticmethod
    def _validate_ni_number(ni_number: str) -> bool:
        """Validate UK National Insurance number format: 2 letters, 6 digits, 1 letter (A-D)."""
        if not ni_number:
            return False
        cleaned = ni_number.replace(" ", "").replace("-", "").upper()
        return bool(re.match(r"^[A-CEGHJ-PR-TW-Z]{2}\d{6}[A-D]$", cleaned))

    @staticmethod
    def verify_share_code(candidate_id: str, share_code: str) -> dict:
        """Verify right to work via Home Office share code (for non-UK/Irish nationals)."""
        check_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute(
                """INSERT INTO right_to_work_checks
                   (id, candidate_id, share_code, verification_method, status, checked_at)
                   VALUES (%s, %s, %s, 'share_code', 'processing', %s)""",
                (check_id, candidate_id, share_code, now),
            )

            # Simulate Home Office API verification
            result = RightToWorkService._simulate_share_code_verification(share_code)

            next_check = None
            if result["visa_expiry"]:
                expiry = datetime.fromisoformat(result["visa_expiry"])
                next_check = (expiry - timedelta(days=30)).isoformat()

            db.execute(
                """UPDATE right_to_work_checks SET
                   status=%s, visa_type=%s, visa_expiry=%s, work_restrictions=%s,
                   verified=%s, result=%s, details=%s, next_check_at=%s
                   WHERE id=%s""",
                (
                    result["status"],
                    result["visa_type"],
                    result["visa_expiry"],
                    result["work_restrictions"],
                    1 if result["verified"] else 0,
                    result["result"],
                    json.dumps(result["details"]),
                    next_check,
                    check_id,
                ),
            )

            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'rtw_check', %s, 'completed', 'system', %s, %s)""",
                (generate_id(), check_id, json.dumps(result), now),
            )

            db.execute("SELECT * FROM right_to_work_checks WHERE id=%s", (check_id,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def verify_uk_citizen(
        candidate_id: str,
        document_type: str,
        nationality: str = "british",
        document_reference: str | None = None,
        ni_number: str | None = None,
    ) -> dict:
        """Verify right to work for British/Irish citizens using accepted documents.

        Per Home Office guidance (List A):
        - UK/Irish passport (current or expired) = sufficient on its own
        - UK birth/adoption certificate OR naturalisation certificate
          + official document showing NI number and name = sufficient
        """
        check_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()

        doc_info = RightToWorkService.UK_CITIZEN_DOCUMENTS.get(document_type)
        if not doc_info:
            raise ValueError(f"Invalid document type: {document_type}")

        # Validate NI number is provided when required
        needs_ni = doc_info["needs_ni"]
        if needs_ni and not ni_number:
            raise ValueError(
                f"{doc_info['label']} requires a National Insurance number "
                "plus an official document (e.g. HMRC letter, P60, DWP letter) showing your NI number and name."
            )

        ni_valid = True
        if ni_number:
            ni_valid = RightToWorkService._validate_ni_number(ni_number)

        with get_db() as db:
            db.execute(
                """INSERT INTO right_to_work_checks
                   (id, candidate_id, verification_method, nationality, document_type,
                    document_reference, ni_number, status, checked_at)
                   VALUES (%s, %s, 'uk_citizen', %s, %s, %s, %s, 'processing', %s)""",
                (check_id, candidate_id, nationality, document_type,
                 document_reference, ni_number, now),
            )

            # Simulate document verification
            result = RightToWorkService._simulate_uk_citizen_verification(
                document_type, nationality, document_reference, ni_number, ni_valid
            )

            db.execute(
                """UPDATE right_to_work_checks SET
                   status=%s, visa_type=%s, visa_expiry=%s, work_restrictions=%s,
                   verified=%s, result=%s, details=%s
                   WHERE id=%s""",
                (
                    result["status"],
                    result["visa_type"],
                    result["visa_expiry"],
                    result["work_restrictions"],
                    1 if result["verified"] else 0,
                    result["result"],
                    json.dumps(result["details"]),
                    check_id,
                ),
            )

            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'rtw_check', %s, 'completed', 'system', %s, %s)""",
                (generate_id(), check_id, json.dumps(result), now),
            )

            db.execute("SELECT * FROM right_to_work_checks WHERE id=%s", (check_id,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def _simulate_share_code_verification(share_code: str) -> dict:
        """Simulate Home Office share code verification."""
        is_valid = len(share_code) >= 9 and random.random() < 0.92
        visa_type = random.choice(RightToWorkService.VISA_TYPES) if is_valid else None

        has_expiry = visa_type not in ["Indefinite Leave to Remain", "Settled Status"] if visa_type else False
        visa_expiry = None
        if has_expiry:
            visa_expiry = (datetime.now(timezone.utc) + timedelta(days=random.randint(90, 730))).isoformat()

        work_restrictions = None
        if visa_type == "Student Visa (with work rights)":
            work_restrictions = "20 hours per week during term time"
        elif visa_type == "Health and Care Worker Visa":
            work_restrictions = "Healthcare sector only"

        return {
            "status": "completed",
            "visa_type": visa_type,
            "visa_expiry": visa_expiry,
            "work_restrictions": work_restrictions,
            "verified": is_valid,
            "result": "valid" if is_valid else "invalid",
            "details": {
                "method": "share_code",
                "share_code": share_code,
                "check_date": datetime.now(timezone.utc).isoformat(),
                "home_office_ref": f"HO-{generate_id()[:8].upper()}",
                "employer_check_completed": is_valid,
            },
        }

    @staticmethod
    def _simulate_uk_citizen_verification(
        document_type: str,
        nationality: str,
        document_reference: str | None,
        ni_number: str | None,
        ni_valid: bool,
    ) -> dict:
        """Simulate document-based RTW verification for British/Irish citizens."""
        doc_info = RightToWorkService.UK_CITIZEN_DOCUMENTS[document_type]

        # Passports are high confidence; certificates + NI slightly lower
        if document_type in ("uk_passport", "irish_passport"):
            is_valid = random.random() < 0.97  # Very high pass rate for passports
        else:
            # Certificate + NI: valid if NI format is correct
            is_valid = ni_valid and random.random() < 0.95

        citizen_type = "British Citizen" if nationality == "british" else "Irish Citizen"

        details = {
            "method": "uk_citizen_document",
            "document_type": document_type,
            "document_label": doc_info["label"],
            "list_a_item": doc_info["list_a_item"],
            "nationality": nationality,
            "check_date": datetime.now(timezone.utc).isoformat(),
            "document_authenticated": is_valid,
        }

        if document_reference:
            details["document_reference_provided"] = True
        if ni_number:
            details["ni_number_format_valid"] = ni_valid
            details["ni_number_verified"] = is_valid and ni_valid

        return {
            "status": "completed",
            "visa_type": citizen_type,
            "visa_expiry": None,  # Citizens have no expiry
            "work_restrictions": None,  # Citizens have no restrictions
            "verified": is_valid,
            "result": "valid" if is_valid else "invalid",
            "details": details,
        }

    @staticmethod
    def get_check(check_id: str) -> dict:
        with get_db() as db:
            db.execute("SELECT * FROM right_to_work_checks WHERE id=%s", (check_id,))
            row = db.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_checks_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM right_to_work_checks WHERE candidate_id=%s ORDER BY checked_at DESC",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]
