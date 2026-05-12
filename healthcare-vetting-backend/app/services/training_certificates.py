"""
Training Certificates Module
Upload, track, and manage mandatory training certificates with expiry monitoring.
Healthcare-specific: manual handling, infection control, safeguarding, BLS, etc.
"""
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id


# Standard healthcare training certificates
STANDARD_CERTIFICATES = [
    {"name": "Manual Handling", "category": "mandatory", "validity_months": 12},
    {"name": "Infection Prevention & Control", "category": "mandatory", "validity_months": 12},
    {"name": "Safeguarding Adults", "category": "mandatory", "validity_months": 36},
    {"name": "Safeguarding Children", "category": "mandatory", "validity_months": 36},
    {"name": "Basic Life Support (BLS)", "category": "mandatory", "validity_months": 12},
    {"name": "Fire Safety", "category": "mandatory", "validity_months": 12},
    {"name": "Health & Safety", "category": "mandatory", "validity_months": 12},
    {"name": "Food Hygiene", "category": "recommended", "validity_months": 36},
    {"name": "Mental Capacity Act", "category": "recommended", "validity_months": 36},
    {"name": "GDPR / Data Protection", "category": "recommended", "validity_months": 12},
    {"name": "Equality & Diversity", "category": "recommended", "validity_months": 36},
    {"name": "Medication Administration", "category": "role_specific", "validity_months": 12},
    {"name": "Venepuncture", "category": "role_specific", "validity_months": 24},
    {"name": "Catheterisation", "category": "role_specific", "validity_months": 24},
    {"name": "Wound Care", "category": "role_specific", "validity_months": 24},
]


class TrainingCertificateService:
    """Manage training certificates for candidates."""

    @staticmethod
    def get_certificates(candidate_id: str) -> list:
        """Get all training certificates for a candidate."""
        with get_db() as db:
            db.execute(
                "SELECT * FROM training_certificates WHERE candidate_id=%s ORDER BY certificate_name",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def add_certificate(candidate_id: str, data: dict) -> dict:
        """Add a training certificate."""
        now = datetime.now(timezone.utc).isoformat()
        cert_id = generate_id()

        # Determine status based on expiry
        status = "valid"
        expiry = data.get("expiry_date")
        if expiry:
            try:
                exp_date = datetime.fromisoformat(expiry)
                if exp_date < datetime.now(timezone.utc):
                    status = "expired"
            except (ValueError, TypeError):
                pass

        with get_db() as db:
            db.execute(
                """INSERT INTO training_certificates
                   (id, candidate_id, certificate_name, category, provider,
                    issue_date, expiry_date, certificate_ref, file_name,
                    status, course_id, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (cert_id, candidate_id, data["certificate_name"],
                 data.get("category", "mandatory"), data.get("provider", ""),
                 data.get("issue_date", now[:10]), expiry,
                 data.get("certificate_ref", ""), data.get("file_name", ""),
                 status, data.get("course_id"), now),
            )
            db.execute("SELECT * FROM training_certificates WHERE id=%s", (cert_id,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def update_certificate(cert_id: str, data: dict) -> dict:
        """Update a training certificate."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            sets = []
            params = []
            for field in ["certificate_name", "category", "provider", "issue_date",
                          "expiry_date", "certificate_ref", "file_name", "status"]:
                if field in data:
                    sets.append(f"{field}=%s")
                    params.append(data[field])

            if sets:
                sets.append("updated_at=%s")
                params.append(now)
                params.append(cert_id)
                db.execute(
                    f"UPDATE training_certificates SET {', '.join(sets)} WHERE id=%s",
                    params,
                )
            db.execute("SELECT * FROM training_certificates WHERE id=%s", (cert_id,))
            row = db.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def delete_certificate(cert_id: str) -> bool:
        """Delete a training certificate."""
        with get_db() as db:
            db.execute("DELETE FROM training_certificates WHERE id=%s", (cert_id,))
            return True

    @staticmethod
    def get_standard_certificates() -> list:
        """Get list of standard healthcare training certificates.
        Falls back to hardcoded list if no industry courses exist."""
        return STANDARD_CERTIFICATES

    @staticmethod
    def _get_industry_courses(candidate_id: str) -> list:
        """Get training courses from the candidate's industry training matrix.
        Falls back to STANDARD_CERTIFICATES if no industry courses are found."""
        try:
            from app.services.training_catalogue import list_courses_for_candidate
            result = list_courses_for_candidate(candidate_id)
            courses = result.get("courses", [])
            if courses:
                return courses
        except Exception:
            pass
        return STANDARD_CERTIFICATES

    @staticmethod
    def get_training_compliance(candidate_id: str) -> dict:
        """Check training compliance against the candidate's industry training matrix."""
        certs = TrainingCertificateService.get_certificates(candidate_id)
        industry_courses = TrainingCertificateService._get_industry_courses(candidate_id)

        # Build lookup: cert name → cert record, and course_id → cert record
        cert_by_name = {c["certificate_name"].lower(): c for c in certs}
        cert_by_course_id = {c["course_id"]: c for c in certs if c.get("course_id")}

        # Use industry courses for mandatory checks
        is_industry = isinstance(industry_courses[0], dict) and "id" in industry_courses[0] if industry_courses else False

        total_count = len(certs)
        valid_count = sum(1 for c in certs if c.get("status") == "valid")
        expired_count = sum(1 for c in certs if c.get("status") == "expired")
        missing_mandatory = []

        if is_industry:
            mandatory = [c for c in industry_courses if c.get("is_mandatory")]
            mandatory_valid = 0
            results = []
            for req in mandatory:
                # Match by course_id first, then by name/aliases
                cert = cert_by_course_id.get(req["id"])
                if not cert:
                    cert = cert_by_name.get(req["name"].lower())
                if not cert:
                    aliases = req.get("aliases", [])
                    if isinstance(aliases, str):
                        import json
                        try:
                            aliases = json.loads(aliases)
                        except Exception:
                            aliases = []
                    for alias in aliases:
                        cert = cert_by_name.get(alias.lower())
                        if cert:
                            break

                if cert and cert.get("status") == "valid":
                    results.append({"name": req["name"], "status": "valid", "expiry": cert.get("expiry_date")})
                    mandatory_valid += 1
                elif cert and cert.get("status") == "expired":
                    results.append({"name": req["name"], "status": "expired", "expiry": cert.get("expiry_date")})
                else:
                    results.append({"name": req["name"], "status": "missing", "expiry": None})
                    missing_mandatory.append(req["name"])
        else:
            mandatory = [c for c in industry_courses if c.get("category") == "mandatory"]
            mandatory_valid = 0
            results = []
            for req in mandatory:
                cert = cert_by_name.get(req["name"].lower())
                if cert and cert.get("status") == "valid":
                    results.append({"name": req["name"], "status": "valid", "expiry": cert.get("expiry_date")})
                    mandatory_valid += 1
                elif cert and cert.get("status") == "expired":
                    results.append({"name": req["name"], "status": "expired", "expiry": cert.get("expiry_date")})
                else:
                    results.append({"name": req["name"], "status": "missing", "expiry": None})
                    missing_mandatory.append(req["name"])

        return {
            "total_certificates": total_count,
            "valid": valid_count,
            "expired": expired_count,
            "mandatory_total": len(mandatory),
            "mandatory_valid": mandatory_valid,
            "compliance_rate": round(mandatory_valid / len(mandatory) * 100, 1) if mandatory else 100.0,
            "missing_mandatory": missing_mandatory,
            "certificates": results,
        }
