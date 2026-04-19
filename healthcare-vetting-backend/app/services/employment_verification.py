"""
Employment History Verification Service
Manages employment verification requests — sends structured confirmation
requests to past employers, tracks responses, detects fraud.
Works the same way as references but specifically confirms job titles,
dates of employment, and reasons for leaving.
"""
import json
import logging
import random
import secrets
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class EmploymentVerificationService:
    """Automated employment history verification with fraud detection."""

    # ── Employment History CRUD ──────────────────────────────────────

    @staticmethod
    def get_employment_history(candidate_id: str) -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM employment_history WHERE candidate_id=%s ORDER BY start_date DESC",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_employment_entry(entry_id: str) -> dict | None:
        with get_db() as db:
            db.execute(
                "SELECT * FROM employment_history WHERE id=%s", (entry_id,)
            )
            row = db.fetchone()
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
            db.execute(
                "SELECT * FROM employment_history WHERE id=%s", (entry_id,)
            )
            row = db.fetchone()
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
                   employer_name=%s, job_title=%s, start_date=%s, end_date=%s,
                   is_current=%s, reason_for_leaving=%s, duties=%s,
                   verifier_name=%s, verifier_email=%s, verifier_job_title=%s
                   WHERE id=%s""",
                (
                    updates["employer_name"], updates["job_title"],
                    updates["start_date"], updates["end_date"],
                    updates["is_current"], updates["reason_for_leaving"],
                    updates["duties"], updates["verifier_name"],
                    updates["verifier_email"], updates["verifier_job_title"],
                    entry_id,
                ),
            )

            db.execute(
                "SELECT * FROM employment_history WHERE id=%s", (entry_id,)
            )
            row = db.fetchone()
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
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'manual', %s)""",
                (
                    entry_id, candidate_id, employer_name, job_title,
                    start_date, end_date, 1 if is_current else 0,
                    reason_for_leaving, duties,
                    verifier_name, verifier_email, verifier_job_title,
                    now,
                ),
            )

            db.execute(
                "SELECT * FROM employment_history WHERE id=%s", (entry_id,)
            )
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def delete_employment_entry(entry_id: str) -> bool:
        with get_db() as db:
            db.execute(
                "SELECT * FROM employment_history WHERE id=%s", (entry_id,)
            )
            row = db.fetchone()
            if not row:
                return False
            db.execute("DELETE FROM employment_history WHERE id=%s", (entry_id,))
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
            db.execute(
                "SELECT * FROM employment_history WHERE id=%s", (employment_id,)
            )
            emp = db.fetchone()
            employer_name = dict(emp)["employer_name"] if emp else None

            # Domain verification
            email_domain = verifier_email.split("@")[1] if "@" in verifier_email else ""
            domain_verified = EmploymentVerificationService._verify_domain(email_domain, employer_name)

            db.execute(
                """INSERT INTO employment_verifications
                   (id, candidate_id, employment_id, verifier_name, verifier_email,
                    verifier_job_title, employer_name, token, verification_code, status,
                    domain_verified, sent_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'sent', %s, %s)""",
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
                   verifier_name=%s, verifier_email=%s, verifier_job_title=%s
                   WHERE id=%s""",
                (verifier_name, verifier_email, verifier_job_title, employment_id),
            )

            if not domain_verified:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (%s, %s, 'employment_domain_mismatch', 'medium', %s, %s, %s)""",
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
                   VALUES (%s, 'employment_verification', %s, 'sent', 'system', %s, %s)""",
                (generate_id(), ver_id, json.dumps({"verifier_email": verifier_email}), now),
            )

            # In production the verifier uses the Verification Portal (/verify)
            # to enter their code and submit a structured response.
            # _simulate_verification_response() is retained for dev/demo seeding only.

            db.execute(
                "SELECT * FROM employment_verifications WHERE id=%s", (ver_id,)
            )
            row = db.fetchone()

        # Send the actual verification request email
        try:
            EmploymentVerificationService._send_verification_email(
                verifier_email=verifier_email,
                verifier_name=verifier_name,
                candidate_id=candidate_id,
                employment_id=employment_id,
                token=token,
                verification_code=verification_code,
            )
        except Exception as e:
            logger.warning(f"Failed to send employment verification email to {verifier_email}: {e}")

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
               status=%s, job_title_confirmed=%s, dates_confirmed=%s,
               reason_for_leaving_confirmed=%s, additional_comments=%s,
               fraud_flags=%s, completed_at=%s
               WHERE id=%s""",
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
                   VALUES (%s, %s, 'employment_verification_fraud', 'high', %s, %s, %s)""",
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
            db.execute(
                "SELECT * FROM employment_verifications WHERE id=%s", (verification_id,)
            )
            row = db.fetchone()
            if not row:
                return None

            ver_dict = dict(row)
            new_count = ver_dict["reminder_count"] + 1

            db.execute(
                "UPDATE employment_verifications SET reminder_count=%s WHERE id=%s",
                (new_count, verification_id),
            )

            if new_count >= 3:
                # Alert the agency/admin that verifier hasn't responded
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (%s, %s, 'employment_verification_no_response', 'medium', %s, %s, %s)""",
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
                       VALUES (%s, %s, 'candidate_chase_verifier', 'low', %s, %s, %s)""",
                    (
                        generate_id(), ver_dict["candidate_id"],
                        f"Your employment verifier ({ver_dict['verifier_name']} at {ver_dict.get('verifier_email', 'N/A')}) has not responded after {new_count} reminder emails. Please contact them directly and ask them to complete the verification.",
                        json.dumps({"ver_id": verification_id, "verifier_name": ver_dict["verifier_name"],
                                    "verifier_email": ver_dict.get("verifier_email", ""),
                                    "type": "employment_verification"}),
                        now,
                    ),
                )

            # Send the actual reminder email
            try:
                EmploymentVerificationService._send_reminder_email(
                    verifier_email=ver_dict.get("verifier_email", ""),
                    verifier_name=ver_dict.get("verifier_name", ""),
                    candidate_id=ver_dict["candidate_id"],
                    token=ver_dict.get("token", ""),
                    verification_code=ver_dict.get("verification_code", ""),
                    reminder_number=new_count,
                    original_sent_date=ver_dict.get("sent_at", ""),
                )
            except Exception as e:
                logger.warning(f"Failed to send employment verification reminder email: {e}")

            return {"verification_id": verification_id, "reminders_sent": new_count, "escalated": new_count >= 3}

    @staticmethod
    def _send_verification_email(
        verifier_email: str,
        verifier_name: str,
        candidate_id: str,
        employment_id: str,
        token: str,
        verification_code: str,
    ):
        """Send the employment verification request email to the verifier."""
        from app.services.email_templates import EmailTemplateService, get_trust_signal_variables

        with get_db() as db:
            db.execute(
                "SELECT first_name, last_name FROM candidates WHERE id=%s", (candidate_id,)
            )
            cand = db.fetchone()
            candidate_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Candidate"

            db.execute(
                "SELECT employer_name, job_title, start_date, end_date FROM employment_history WHERE id=%s",
                (employment_id,)
            )
            emp = db.fetchone()
            emp_data = dict(emp) if emp else {}

            db.execute(
                "SELECT agency_id FROM agency_candidates WHERE candidate_id=%s LIMIT 1", (candidate_id,)
            )
            agency_link = db.fetchone()
            agency_name = "Viper AI"
            if agency_link:
                db.execute(
                    "SELECT name FROM agencies WHERE id=%s", (dict(agency_link)["agency_id"],)
                )
                agency = db.fetchone()
                if agency:
                    agency_name = dict(agency)["name"]

        from app.config import BASE_URL
        verification_link = f"{BASE_URL}/verify?token={token}&type=employment"

        variables = {
            "candidate_name": candidate_name,
            "verifier_name": verifier_name,
            "agency_name": agency_name,
            "employer_name": emp_data.get("employer_name", ""),
            "job_title": emp_data.get("job_title", ""),
            "start_date": emp_data.get("start_date", ""),
            "end_date": emp_data.get("end_date", "Present"),
            "verification_code": verification_code,
            "verification_link": verification_link,
            **get_trust_signal_variables(),
        }

        EmailTemplateService.send_email(
            template_key="employment_verification_request",
            recipient_email=verifier_email,
            recipient_name=verifier_name,
            variables=variables,
        )
        logger.info(f"Employment verification email sent to {verifier_email} for candidate {candidate_id}")

    @staticmethod
    def _send_reminder_email(
        verifier_email: str,
        verifier_name: str,
        candidate_id: str,
        token: str,
        verification_code: str,
        reminder_number: int,
        original_sent_date: str,
    ):
        """Send a reminder email to the employment verifier."""
        from app.services.email_templates import EmailTemplateService, get_trust_signal_variables

        with get_db() as db:
            db.execute(
                "SELECT first_name, last_name FROM candidates WHERE id=%s", (candidate_id,)
            )
            cand = db.fetchone()
            candidate_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Candidate"

            db.execute(
                "SELECT agency_id FROM agency_candidates WHERE candidate_id=%s LIMIT 1", (candidate_id,)
            )
            agency_link = db.fetchone()
            agency_name = "Viper AI"
            if agency_link:
                db.execute(
                    "SELECT name FROM agencies WHERE id=%s", (dict(agency_link)["agency_id"],)
                )
                agency = db.fetchone()
                if agency:
                    agency_name = dict(agency)["name"]

        from app.config import BASE_URL
        action_link = f"{BASE_URL}/verify?token={token}&type=employment"

        variables = {
            "recipient_name": verifier_name,
            "request_type": "Employment Verification",
            "candidate_name": candidate_name,
            "agency_name": agency_name,
            "original_sent_date": original_sent_date[:10] if original_sent_date else "",
            "reminder_number": str(reminder_number),
            "verification_code": verification_code,
            "action_link": action_link,
            **get_trust_signal_variables(),
        }

        EmailTemplateService.send_email(
            template_key="verification_reminder",
            recipient_email=verifier_email,
            recipient_name=verifier_name,
            variables=variables,
        )
        logger.info(f"Employment verification reminder #{reminder_number} sent to {verifier_email} for candidate {candidate_id}")

    @staticmethod
    def get_verifications_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM employment_verifications WHERE candidate_id=%s ORDER BY sent_at DESC",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_verifications_for_employment(employment_id: str) -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM employment_verifications WHERE employment_id=%s ORDER BY sent_at DESC",
                (employment_id,),
            )
            rows = db.fetchall()
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
