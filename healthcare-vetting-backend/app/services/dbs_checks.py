"""
DBS Check Service
Simulates integration with uCheck / CareCheck / First Advantage APIs.
In production, replace mock logic with real API calls.
"""
import json
import random
import string
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id


class DBSCheckService:
    """Automated DBS check submission and tracking via API providers."""

    PROVIDERS = {
        "ucheck": {"name": "uCheck", "cost_gbp": 49.0, "avg_days": 2},
        "carecheck": {"name": "CareCheck", "cost_gbp": 55.0, "avg_days": 3},
        "first_advantage": {"name": "First Advantage", "cost_gbp": 60.0, "avg_days": 2},
    }

    CHECK_TYPES = ["basic", "standard", "enhanced", "enhanced_barred"]

    @staticmethod
    def submit_check(candidate_id: str, check_type: str = "enhanced", provider: str = "ucheck") -> dict:
        check_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        app_ref = f"DBS-{''.join(random.choices(string.ascii_uppercase + string.digits, k=8))}"

        with get_db() as db:
            db.execute(
                """INSERT INTO dbs_checks
                   (id, candidate_id, provider, check_type, status, application_ref, submitted_at)
                   VALUES (%s, %s, %s, %s, 'submitted', %s, %s)""",
                (check_id, candidate_id, provider, check_type, app_ref, now),
            )

            # Simulate DBS processing
            result = DBSCheckService._simulate_dbs_result(check_type)

            cert_number = None
            issue_date = None
            next_renewal = None

            if result["status"] == "completed":
                cert_number = f"{''.join(random.choices(string.digits, k=12))}"
                issue_date = now
                next_renewal = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()

            db.execute(
                """UPDATE dbs_checks SET
                   status=%s, certificate_number=%s, issue_date=%s,
                   result=%s, details=%s, next_renewal=%s, completed_at=%s
                   WHERE id=%s""",
                (
                    result["status"],
                    cert_number,
                    issue_date,
                    result["result"],
                    json.dumps(result["details"]),
                    next_renewal,
                    now if result["status"] == "completed" else None,
                    check_id,
                ),
            )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'dbs_check', %s, 'submitted', 'system', %s, %s)""",
                (generate_id(), check_id, json.dumps({"provider": provider, "type": check_type}), now),
            )

            row = db.execute("SELECT * FROM dbs_checks WHERE id=%s", (check_id,)).fetchone()
            return dict(row)

    @staticmethod
    def _simulate_dbs_result(check_type: str) -> dict:
        """Simulate DBS check result. In production, this comes via webhook."""
        is_clear = random.random() < 0.88
        has_info = not is_clear and random.random() < 0.7

        if is_clear:
            result = "clear"
            details = {
                "convictions": "none",
                "cautions": "none",
                "barred_list": "not listed" if "barred" in check_type else "n/a",
                "police_info": "none disclosed",
            }
        elif has_info:
            result = "has_information"
            details = {
                "convictions": "minor offence - review required",
                "cautions": "none",
                "barred_list": "not listed" if "barred" in check_type else "n/a",
                "police_info": "information disclosed - manual review required",
                "requires_human_review": True,
            }
        else:
            result = "flagged"
            details = {
                "convictions": "serious offence recorded",
                "barred_list": "listed" if "barred" in check_type else "n/a",
                "requires_human_review": True,
                "recommendation": "do_not_clear",
            }

        return {
            "status": "completed",
            "result": result,
            "details": details,
        }

    @staticmethod
    def check_update_service(candidate_id: str, certificate_number: str) -> dict:
        """Check DBS Update Service for changes since certificate was issued."""
        is_current = random.random() < 0.95
        return {
            "certificate_number": certificate_number,
            "status": "no_change" if is_current else "changed",
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "recommendation": "valid" if is_current else "new_check_required",
        }

    @staticmethod
    def get_check(check_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM dbs_checks WHERE id=%s", (check_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_checks_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM dbs_checks WHERE candidate_id=%s ORDER BY submitted_at DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]
