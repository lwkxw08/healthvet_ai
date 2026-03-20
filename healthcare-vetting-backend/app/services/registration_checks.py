"""
Professional Registration Check Service
Simulates querying NMC, GMC, HCPC public registers.
In production, scrape or API-query the actual public registers.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id


class RegistrationCheckService:
    """Verify healthcare professional registrations against public registers."""

    REGISTRATION_BODIES = {
        "NMC": {
            "name": "Nursing and Midwifery Council",
            "url": "https://www.nmc.org.uk/registration/search-the-register/",
            "professions": ["Nurse", "Midwife", "Nursing Associate"],
        },
        "GMC": {
            "name": "General Medical Council",
            "url": "https://www.gmc-uk.org/registration-and-licensing/the-medical-register",
            "professions": ["Doctor", "Physician", "Surgeon", "GP"],
        },
        "HCPC": {
            "name": "Health and Care Professions Council",
            "url": "https://www.hcpc-uk.org/check-the-register/",
            "professions": [
                "Physiotherapist", "Occupational Therapist", "Paramedic",
                "Speech Therapist", "Dietitian", "Radiographer",
                "Operating Department Practitioner", "Biomedical Scientist",
            ],
        },
        "GPhC": {
            "name": "General Pharmaceutical Council",
            "url": "https://www.pharmacyregulation.org/registers",
            "professions": ["Pharmacist", "Pharmacy Technician"],
        },
    }

    @staticmethod
    def check_registration(candidate_id: str, body: str, registration_number: str) -> dict:
        check_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        next_check = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

        with get_db() as db:
            # Simulate register query
            result = RegistrationCheckService._simulate_register_check(body, registration_number)

            db.execute(
                """INSERT INTO registration_checks
                   (id, candidate_id, body, registration_number, status, is_active,
                    sanctions, conditions, last_checked, next_check, result)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    check_id, candidate_id, body, registration_number,
                    result["status"],
                    1 if result["is_active"] else 0,
                    json.dumps(result["sanctions"]),
                    json.dumps(result["conditions"]),
                    now, next_check,
                    result["result"],
                ),
            )

            # Create alerts for issues
            if result["sanctions"]:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'registration_sanction', 'critical', ?, ?, ?)""",
                    (
                        generate_id(), candidate_id,
                        f"Active sanctions found on {body} registration",
                        json.dumps(result["sanctions"]),
                        now,
                    ),
                )

            if not result["is_active"]:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'registration_inactive', 'high', ?, ?, ?)""",
                    (
                        generate_id(), candidate_id,
                        f"{body} registration is not active",
                        json.dumps({"body": body, "reg_number": registration_number}),
                        now,
                    ),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'registration_check', ?, 'completed', 'system', ?, ?)""",
                (generate_id(), check_id, json.dumps(result), now),
            )

            row = db.execute("SELECT * FROM registration_checks WHERE id=?", (check_id,)).fetchone()
            return dict(row)

    @staticmethod
    def _simulate_register_check(body: str, registration_number: str) -> dict:
        """Simulate public register query. Replace with real scraping/API in production."""
        is_active = random.random() < 0.90
        has_sanctions = random.random() < 0.05
        has_conditions = random.random() < 0.08

        sanctions = []
        if has_sanctions:
            sanctions = [{
                "type": "conditions_of_practice",
                "imposed_date": "2024-06-15",
                "detail": "Conditions of practice order - supervision required",
                "review_date": "2025-06-15",
            }]

        conditions = []
        if has_conditions:
            conditions = [{
                "type": "annotation",
                "detail": "Must work under supervision for 12 months",
                "start_date": "2025-01-01",
            }]

        body_info = RegistrationCheckService.REGISTRATION_BODIES.get(body, {})

        return {
            "status": "completed",
            "is_active": is_active,
            "sanctions": sanctions,
            "conditions": conditions,
            "result": "active" if is_active and not sanctions else "review_required",
            "details": {
                "body": body,
                "body_name": body_info.get("name", body),
                "registration_number": registration_number,
                "register_entry_found": True,
                "last_renewal": (datetime.now(timezone.utc) - timedelta(days=random.randint(30, 300))).isoformat(),
            },
        }

    @staticmethod
    def get_check(check_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM registration_checks WHERE id=?", (check_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_checks_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM registration_checks WHERE candidate_id=? ORDER BY last_checked DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]
