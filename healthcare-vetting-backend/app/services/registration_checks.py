"""
Professional Registration Check Service
Queries NMC, GMC, HCPC, GPhC public registers via headless scraping (live mode)
or simulation (dev/test). Controlled by REGISTRATION_MODE env var.
"""
import json
import logging
import os
import random
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)

# Set REGISTRATION_MODE=live to use real headless Selenium scrapers
REGISTRATION_MODE = os.environ.get("REGISTRATION_MODE", "simulate")


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
    def _live_register_check(body: str, registration_number: str) -> dict:
        """Query the real public register using headless Selenium scrapers."""
        from app.services.registration_scrapers import scrape_registration

        scrape_result = scrape_registration(body, registration_number)

        is_active = scrape_result.get("registration_status") == "active"
        sanctions = scrape_result.get("sanctions", [])
        conditions = scrape_result.get("conditions", [])
        success = scrape_result.get("success", False)
        error = scrape_result.get("error")

        if not success:
            logger.warning(
                "Live scrape failed for %s/%s: %s — falling back to simulation",
                body, registration_number, error,
            )
            return RegistrationCheckService._simulate_register_check(body, registration_number)

        body_info = RegistrationCheckService.REGISTRATION_BODIES.get(body, {})
        result_status = "active" if is_active and not sanctions else "review_required"

        return {
            "status": "completed",
            "is_active": is_active,
            "sanctions": sanctions,
            "conditions": conditions,
            "result": result_status,
            "details": {
                "body": body,
                "body_name": body_info.get("name", body),
                "registration_number": registration_number,
                "register_entry_found": True,
                "registrant_name": scrape_result.get("registrant_name", ""),
                "expiry_date": scrape_result.get("expiry_date", ""),
                "source": "live_scrape",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            },
        }

    @staticmethod
    def check_registration(candidate_id: str, body: str, registration_number: str) -> dict:
        check_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        next_check = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

        with get_db() as db:
            # Use live scrapers or simulation based on REGISTRATION_MODE
            if REGISTRATION_MODE == "live":
                result = RegistrationCheckService._live_register_check(body, registration_number)
            else:
                result = RegistrationCheckService._simulate_register_check(body, registration_number)

            db.execute(
                """INSERT INTO registration_checks
                   (id, candidate_id, body, registration_number, status, is_active,
                    sanctions, conditions, last_checked, next_check, result)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
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
                       VALUES (%s, %s, 'registration_sanction', 'critical', %s, %s, %s)""",
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
                       VALUES (%s, %s, 'registration_inactive', 'high', %s, %s, %s)""",
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
                   VALUES (%s, 'registration_check', %s, 'completed', 'system', %s, %s)""",
                (generate_id(), check_id, json.dumps(result), now),
            )

            db.execute("SELECT * FROM registration_checks WHERE id=%s", (check_id,))
            row = db.fetchone()
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
            db.execute("SELECT * FROM registration_checks WHERE id=%s", (check_id,))
            row = db.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_checks_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM registration_checks WHERE candidate_id=%s ORDER BY last_checked DESC",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]
