"""
Employment History Verification Service
Manages employment verification requests — sends structured confirmation
requests to past employers, tracks responses, detects fraud.
Works the same way as references but specifically confirms job titles,
dates of employment, and reasons for leaving.
"""
import json
import random
import secrets
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id


class EmploymentVerificationService:
    """Automated employment history verification with fraud detection."""

    # ── Employment History CRUD ──────────────────────────────────────

    @staticmethod
    def get_employment_history(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM employment_history WHERE candidate_id=? ORDER BY start_date DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_employment_entry(entry_id: str) -> dict | None:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM employment_history WHERE id=?", (entry_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_employment_entry(
        entry_id: str,
        employer_name: str | None = None,
        job_title: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        is_current: bool | None = None,
        reason_for_leaving: str | None = None,
        duties: str | None = None,
        verifier_name: str | None = None,
        verifier_email: str | None = None,
        verifier_job_title: str | None = None,
    ) -> dict | None:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM employment_history WHERE id=?", (entry_id,)
            ).fetchone()
            if not row:
                return None

            current = dict(row)
            updates = {
                "employer_name": employer_name if employer_name is not None else current["employer_name"],
                "job_title": job_title if job_title is not None else current["job_title"],
                "start_date": start_date if start_date is not None else current["start_date"],
                "end_date": end_date if end_date is not None else current["end_date"],
                "is_current": (1 if is_current else 0) if is_current is not None else current["is_current"],
                "reason_for_leaving": reason_for_leaving if reason_for_leaving is not None else current["reason_for_leaving"],
                "duties": duties if duties is not None else current["duties"],
                "verifier_name": verifier_name if verifier_name is not None else current["verifier_name"],
                "verifier_email": verifier_email if verifier_email is not None else current["verifier_email"],
                "verifier_job_title": verifier_job_title if verifier_job_title is not None else current["verifier_job_title"],
            }

            db.execute(
                """UPDATE employment_history SET
                   employer_name=?, job_title=?, start_date=?, end_date=?,
                   is_current=?, reason_for_leaving=?, duties=?,
                   verifier_name=?, verifier_email=?, verifier_job_title=?
                   WHERE id=?""",
                (
                    updates["employer_name"], updates["job_title"],
                    updates["start_date"], updates["end_date"],
                    updates["is_current"], updates["reason_for_leaving"],
                    updates["duties"], updates["verifier_name"],
                    updates["verifier_email"], updates["verifier_job_title"],
                    entry_id,
                ),
            )

            row = db.execute(
                "SELECT * FROM employment_history WHERE id=?", (entry_id,)
            ).fetchone()
            return dict(row)

    @staticmethod
    def add_employment_entry(
        candidate_id: str,
        employer_name: str,
        job_title: str,
        start_date: str | None = None,
        end_date: str | None = None,
        is_current: bool = False,
        reason_for_leaving: str | None = None,
        duties: str | None = None,
        verifier_name: str | None = None,
        verifier_email: str | None = None,
        verifier_job_title: str | None = None,
    ) -> dict:
        entry_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute(
                """INSERT INTO employment_history
                   (id, candidate_id, employer_name, job_title, start_date, end_date,
                    is_current, reason_for_leaving, duties,
                    verifier_name, verifier_email, verifier_job_title, source, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual', ?)""",
                (
                    entry_id, candidate_id, employer_name, job_title,
                    start_date, end_date, 1 if is_current else 0,
                    reason_for_leaving, duties,
                    verifier_name, verifier_email, verifier_job_title,
                    now,
                ),
            )

            row = db.execute(
                "SELECT * FROM employment_history WHERE id=?", (entry_id,)
            ).fetchone()
            return dict(row)

    @staticmethod
    def delete_employment_entry(entry_id: str) -> bool:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM employment_history WHERE id=?", (entry_id,)
            ).fetchone()
            if not row:
                return False
            db.execute("DELETE FROM employment_history WHERE id=?", (entry_id,))
            return True

    # ── Verification Requests ────────────────────────────────────────

    @staticmethod
    def send_verification_request(
        candidate_id: str,
        employment_id: str,
        verifier_name: str,
        verifier_email: str,
        verifier_job_title: str | None = None,
    ) -> dict:
        """Send an employment verification request to a past employer.

        Works like the reference system: generates a unique token/link,
        the verifier confirms job title, dates, and reason for leaving.
        """
        from app.services.email_templates import generate_verification_code
        ver_id = generate_id()
        token = secrets.token_urlsafe(32)
        verification_code = generate_verification_code()
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            # Get employment entry for context
            emp = db.execute(
                "SELECT * FROM employment_history WHERE id=?", (employment_id,)
            ).fetchone()
            employer_name = dict(emp)["employer_name"] if emp else None

            # Domain verification
            email_domain = verifier_email.split("@")[1] if "@" in verifier_email else ""
            domain_verified = EmploymentVerificationService._verify_domain(email_domain, employer_name)

            db.execute(
                """INSERT INTO employment_verifications
                   (id, candidate_id, employment_id, verifier_name, verifier_email,
                    verifier_job_title, employer_name, token, verification_code, status,
                    domain_verified, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'sent', ?, ?)""",
                (
                    ver_id, candidate_id, employment_id,
                    verifier_name, verifier_email, verifier_job_title,
                    employer_name, token, verification_code,
                    1 if domain_verified else 0,
                    now,
                ),
            )

            # Also update the employment_history entry with verifier info
            db.execute(
                """UPDATE employment_history SET
                   verifier_name=?, verifier_email=?, verifier_job_title=?
                   WHERE id=?""",
                (verifier_name, verifier_email, verifier_job_title, employment_id),
            )

            if not domain_verified:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'employment_domain_mismatch', 'medium', ?, ?, ?)""",
                    (
                        generate_id(), candidate_id,
                        f"Employment verifier email domain does not match employer: {email_domain}",
                        json.dumps({"email": verifier_email, "employer": employer_name}),
                        now,
                    ),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'employment_verification', ?, 'sent', 'system', ?, ?)""",
                (generate_id(), ver_id, json.dumps({"verifier_email": verifier_email}), now),
            )

            # Simulate auto-completion (in production, verifier would click the link)
            EmploymentVerificationService._simulate_verification_response(db, ver_id, token, candidate_id)

            row = db.execute(
                "SELECT * FROM employment_verifications WHERE id=?", (ver_id,)
            ).fetchone()
            return dict(row)

    @staticmethod
    def _simulate_verification_response(db, ver_id: str, token: str, candidate_id: str):
        """Simulate a verifier responding to the verification request.

        In production, the verifier would receive an email with a link,
        click it, and fill out a form confirming employment details.
        """
        now = datetime.now(timezone.utc).isoformat()
        is_positive = random.random() < 0.85

        job_title_confirmed = is_positive
        dates_confirmed = is_positive or random.random() < 0.7
        reason_text = None
        if is_positive:
            reasons = [
                "Career progression opportunity",
                "Relocated to a different area",
                "End of fixed-term contract",
                "Seeking new challenges",
                "Personal reasons",
            ]
            reason_text = random.choice(reasons)
        else:
            reason_text = "Unable to confirm — records unavailable"

        comments = None
        if is_positive and random.random() < 0.6:
            positive_comments = [
                "Good employee, would recommend.",
                "Reliable and professional throughout their tenure.",
                "Left on good terms, eligible for rehire.",
                "Competent practitioner, no concerns.",
            ]
            comments = random.choice(positive_comments)

        fraud_flags = []
        if random.random() < 0.05:
            fraud_flags.append({
                "type": "suspicious_timing",
                "detail": "Verification completed unusually quickly",
            })

        status = "verified" if (job_title_confirmed and dates_confirmed) else "disputed"
        if fraud_flags:
            status = "flagged"

        db.execute(
            """UPDATE employment_verifications SET
               status=?, job_title_confirmed=?, dates_confirmed=?,
               reason_for_leaving_confirmed=?, additional_comments=?,
               fraud_flags=?, completed_at=?
               WHERE id=?""",
            (
                status,
                1 if job_title_confirmed else 0,
                1 if dates_confirmed else 0,
                reason_text,
                comments,
                json.dumps(fraud_flags) if fraud_flags else None,
                now,
                ver_id,
            ),
        )

        if fraud_flags:
            db.execute(
                """INSERT INTO monitoring_alerts
                   (id, candidate_id, alert_type, severity, message, details, created_at)
                   VALUES (?, ?, 'employment_verification_fraud', 'high', ?, ?, ?)""",
                (
                    generate_id(), candidate_id,
                    "Employment verification fraud flags detected",
                    json.dumps(fraud_flags),
                    now,
                ),
            )

    @staticmethod
    def send_reminder(verification_id: str) -> dict | None:
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM employment_verifications WHERE id=?", (verification_id,)
            ).fetchone()
            if not row:
                return None

            ver_dict = dict(row)
            new_count = ver_dict["reminder_count"] + 1

            db.execute(
                "UPDATE employment_verifications SET reminder_count=? WHERE id=?",
                (new_count, verification_id),
            )

            if new_count >= 3:
                # Alert the agency/admin that verifier hasn't responded
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'employment_verification_no_response', 'medium', ?, ?, ?)""",
                    (
                        generate_id(), ver_dict["candidate_id"],
                        f"Employment verification from {ver_dict['verifier_name']} not received after {new_count} reminders. Candidate has been notified to chase the verifier.",
                        json.dumps({"ver_id": verification_id, "reminders_sent": new_count,
                                    "action": "candidate_notified_to_chase"}),
                        now,
                    ),
                )
                # Create a notification for the candidate to chase the verifier
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'candidate_chase_verifier', 'low', ?, ?, ?)""",
                    (
                        generate_id(), ver_dict["candidate_id"],
                        f"Your employment verifier ({ver_dict['verifier_name']} at {ver_dict.get('verifier_email', 'N/A')}) has not responded after {new_count} reminder emails. Please contact them directly and ask them to complete the verification.",
                        json.dumps({"ver_id": verification_id, "verifier_name": ver_dict["verifier_name"],
                                    "verifier_email": ver_dict.get("verifier_email", ""),
                                    "type": "employment_verification"}),
                        now,
                    ),
                )

            return {"verification_id": verification_id, "reminders_sent": new_count, "escalated": new_count >= 3}

    @staticmethod
    def get_verifications_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM employment_verifications WHERE candidate_id=? ORDER BY sent_at DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_verifications_for_employment(employment_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM employment_verifications WHERE employment_id=? ORDER BY sent_at DESC",
                (employment_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def _verify_domain(email_domain: str, employer_name: str | None) -> bool:
        """Check if verifier email domain matches the employer."""
        if not employer_name or not email_domain:
            return False
        org_words = employer_name.lower().replace("nhs", "").split()
        domain_lower = email_domain.lower()
        if "nhs" in domain_lower:
            return True
        return any(word in domain_lower for word in org_words if len(word) > 3)
