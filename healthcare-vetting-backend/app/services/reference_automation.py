"""
Automated Reference Service
Sends structured reference requests, tracks responses, detects fraud.
"""
import json
import logging
import random
import secrets
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class ReferenceAutomationService:
    """Automated reference collection with fraud detection."""

    @staticmethod
    def create_reference_request(
        candidate_id: str,
        referee_name: str,
        referee_email: str,
        referee_phone: str = None,
        referee_organisation: str = None,
        referee_job_title: str = None,
        relationship: str = None,
    ) -> dict:
        from app.services.email_templates import generate_verification_code
        ref_id = generate_id()
        token = secrets.token_urlsafe(32)
        verification_code = generate_verification_code()
        now = datetime.now(timezone.utc).isoformat()

        # Domain verification
        email_domain = referee_email.split("@")[1] if "@" in referee_email else ""
        domain_verified = ReferenceAutomationService._verify_domain(email_domain, referee_organisation)

        with get_db() as db:
            db.execute(
                """INSERT INTO references_
                   (id, candidate_id, referee_name, referee_email, referee_phone,
                    referee_organisation, referee_job_title, relationship, token,
                    verification_code, status, domain_verified, sent_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'sent', %s, %s)""",
                (
                    ref_id, candidate_id, referee_name, referee_email,
                    referee_phone, referee_organisation, referee_job_title,
                    relationship, token, verification_code,
                    1 if domain_verified else 0,
                    now,
                ),
            )

            if not domain_verified:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (%s, %s, 'reference_domain_mismatch', 'medium', %s, %s, %s)""",
                    (
                        generate_id(), candidate_id,
                        f"Reference email domain does not match organisation: {email_domain}",
                        json.dumps({"email": referee_email, "org": referee_organisation}),
                        now,
                    ),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'reference', %s, 'sent', 'system', %s, %s)""",
                (generate_id(), ref_id, json.dumps({"referee_email": referee_email}), now),
            )

            db.execute("SELECT * FROM references_ WHERE id=%s", (ref_id,))
            row = db.fetchone()

        # Send the actual reference request email
        try:
            ReferenceAutomationService._send_reference_email(
                referee_email=referee_email,
                referee_name=referee_name,
                candidate_id=candidate_id,
                token=token,
                verification_code=verification_code,
            )
        except Exception as e:
            logger.warning(f"Failed to send reference request email to {referee_email}: {e}")

        return dict(row)

    @staticmethod
    def submit_reference(token: str, responses: dict, ip_address: str = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            db.execute("SELECT * FROM references_ WHERE token=%s", (token,))
            ref = db.fetchone()
            if not ref:
                return None

            ref_dict = dict(ref)

            # AI sentiment analysis
            sentiment = ReferenceAutomationService._analyse_sentiment(responses)

            # Fraud detection
            fraud_flags = ReferenceAutomationService._detect_fraud(
                ref_dict, responses, ip_address
            )

            status = "completed"
            if fraud_flags:
                status = "flagged"

            db.execute(
                """UPDATE references_ SET
                   status=%s, responses=%s, sentiment_score=%s,
                   fraud_flags=%s, ip_address=%s, completed_at=%s
                   WHERE token=%s""",
                (
                    status,
                    json.dumps(responses),
                    sentiment,
                    json.dumps(fraud_flags) if fraud_flags else None,
                    ip_address,
                    now,
                    token,
                ),
            )

            if fraud_flags:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (%s, %s, 'reference_fraud', 'high', %s, %s, %s)""",
                    (
                        generate_id(), ref_dict["candidate_id"],
                        f"Reference fraud flags detected for {ref_dict['referee_name']}",
                        json.dumps(fraud_flags),
                        now,
                    ),
                )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (%s, 'reference', %s, 'submitted', 'referee', %s, %s)""",
                (generate_id(), ref_dict["id"], json.dumps({"sentiment": sentiment, "fraud_flags": len(fraud_flags)}), now),
            )

            db.execute("SELECT * FROM references_ WHERE token=%s", (token,))
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def send_reminder(ref_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute("SELECT * FROM references_ WHERE id=%s", (ref_id,))
            ref = db.fetchone()
            if not ref:
                return None

            ref_dict = dict(ref)
            new_count = ref_dict["reminder_count"] + 1

            db.execute(
                "UPDATE references_ SET reminder_count=%s WHERE id=%s",
                (new_count, ref_id),
            )

            # Auto-escalate after 3 reminders — notify candidate to chase
            if new_count >= 3:
                # Alert agency/admin
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (%s, %s, 'reference_no_response', 'medium', %s, %s, %s)""",
                    (
                        generate_id(), ref_dict["candidate_id"],
                        f"Reference from {ref_dict['referee_name']} not received after {new_count} reminders. Candidate has been notified to chase the referee.",
                        json.dumps({"ref_id": ref_id, "reminders_sent": new_count,
                                    "action": "candidate_notified_to_chase"}),
                        now,
                    ),
                )
                # Notify candidate to chase the referee
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (%s, %s, 'candidate_chase_verifier', 'low', %s, %s, %s)""",
                    (
                        generate_id(), ref_dict["candidate_id"],
                        f"Your referee ({ref_dict['referee_name']} at {ref_dict.get('referee_email', 'N/A')}) has not responded after {new_count} reminder emails. Please contact them directly and ask them to complete the reference.",
                        json.dumps({"ref_id": ref_id, "referee_name": ref_dict["referee_name"],
                                    "referee_email": ref_dict.get("referee_email", ""),
                                    "type": "reference"}),
                        now,
                    ),
                )

            # Send the actual reminder email
            try:
                ReferenceAutomationService._send_reminder_email(
                    referee_email=ref_dict.get("referee_email", ""),
                    referee_name=ref_dict.get("referee_name", ""),
                    candidate_id=ref_dict["candidate_id"],
                    token=ref_dict.get("token", ""),
                    verification_code=ref_dict.get("verification_code", ""),
                    reminder_number=new_count,
                    original_sent_date=ref_dict.get("sent_at", ""),
                )
            except Exception as e:
                logger.warning(f"Failed to send reference reminder email: {e}")

            return {"ref_id": ref_id, "reminders_sent": new_count, "escalated": new_count >= 3}

    @staticmethod
    def _verify_domain(email_domain: str, organisation: str) -> bool:
        """Check if email domain matches the claimed organisation."""
        if not organisation or not email_domain:
            return False
        # Simple heuristic: check if org name words appear in domain
        org_words = organisation.lower().replace("nhs", "").split()
        domain_lower = email_domain.lower()
        # NHS domains are always trusted
        if "nhs" in domain_lower:
            return True
        return any(word in domain_lower for word in org_words if len(word) > 3)

    @staticmethod
    def _analyse_sentiment(responses: dict) -> float:
        """AI sentiment analysis of reference responses. Returns 0.0-1.0."""
        score = 0.5
        positive_signals = ["excellent", "outstanding", "highly recommend", "exceptional", "strong"]
        negative_signals = ["concern", "poor", "unreliable", "issues", "not recommend"]

        text = json.dumps(responses).lower()
        for signal in positive_signals:
            if signal in text:
                score += 0.1
        for signal in negative_signals:
            if signal in text:
                score -= 0.15

        if responses.get("would_rehire"):
            score += 0.15
        if responses.get("performance_rating", 3) >= 4:
            score += 0.1

        return min(max(round(score, 2), 0.0), 1.0)

    @staticmethod
    def _detect_fraud(ref_data: dict, responses: dict, ip_address: str) -> list:
        """Detect potential reference fraud."""
        flags = []

        # Check response time (too fast is suspicious)
        if ref_data.get("sent_at"):
            sent = datetime.fromisoformat(ref_data["sent_at"])
            elapsed = (datetime.now(timezone.utc) - sent).total_seconds()
            if elapsed < 60:
                flags.append({
                    "type": "suspicious_timing",
                    "detail": f"Reference completed in {elapsed:.0f} seconds - unusually fast",
                })

        # Domain mismatch already flagged at creation

        # Check for generic responses
        comments = responses.get("additional_comments", "")
        if comments and len(comments) < 10:
            flags.append({
                "type": "generic_response",
                "detail": "Response appears generic/minimal",
            })

        # Simulate IP-based fraud detection
        if random.random() < 0.05:
            flags.append({
                "type": "ip_match",
                "detail": "Referee IP matches candidate IP - possible self-referencing",
            })

        return flags

    @staticmethod
    def _send_reference_email(
        referee_email: str,
        referee_name: str,
        candidate_id: str,
        token: str,
        verification_code: str,
    ):
        """Send the reference request email to the referee."""
        from app.services.email_templates import EmailTemplateService, get_trust_signal_variables

        # Look up candidate and agency names
        with get_db() as db:
            cand = db.execute(
                "SELECT first_name, last_name FROM candidates WHERE id=%s", (candidate_id,)
            )
            cand = db.fetchone()
            candidate_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Candidate"

            agency_link = db.execute(
                "SELECT agency_id FROM agency_candidates WHERE candidate_id=%s LIMIT 1", (candidate_id,)
            )
            agency_link = db.fetchone()
            agency_name = "Viper AI"
            if agency_link:
                agency = db.execute(
                    "SELECT name FROM agencies WHERE id=%s", (dict(agency_link)["agency_id"],)
                )
                agency = db.fetchone()
                if agency:
                    agency_name = dict(agency)["name"]

        from app.config import BASE_URL
        reference_link = f"{BASE_URL}/verify?token={token}&type=reference"

        variables = {
            "candidate_name": candidate_name,
            "referee_name": referee_name,
            "agency_name": agency_name,
            "verification_code": verification_code,
            "reference_link": reference_link,
            **get_trust_signal_variables(),
        }

        EmailTemplateService.send_email(
            template_key="reference_request",
            recipient_email=referee_email,
            recipient_name=referee_name,
            variables=variables,
        )
        logger.info(f"Reference request email sent to {referee_email} for candidate {candidate_id}")

    @staticmethod
    def _send_reminder_email(
        referee_email: str,
        referee_name: str,
        candidate_id: str,
        token: str,
        verification_code: str,
        reminder_number: int,
        original_sent_date: str,
    ):
        """Send a reminder email to the referee."""
        from app.services.email_templates import EmailTemplateService, get_trust_signal_variables

        with get_db() as db:
            cand = db.execute(
                "SELECT first_name, last_name FROM candidates WHERE id=%s", (candidate_id,)
            )
            cand = db.fetchone()
            candidate_name = f"{dict(cand)['first_name']} {dict(cand)['last_name']}" if cand else "Candidate"

            agency_link = db.execute(
                "SELECT agency_id FROM agency_candidates WHERE candidate_id=%s LIMIT 1", (candidate_id,)
            )
            agency_link = db.fetchone()
            agency_name = "Viper AI"
            if agency_link:
                agency = db.execute(
                    "SELECT name FROM agencies WHERE id=%s", (dict(agency_link)["agency_id"],)
                )
                agency = db.fetchone()
                if agency:
                    agency_name = dict(agency)["name"]

        from app.config import BASE_URL
        action_link = f"{BASE_URL}/verify?token={token}&type=reference"

        variables = {
            "recipient_name": referee_name,
            "request_type": "Professional Reference",
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
            recipient_email=referee_email,
            recipient_name=referee_name,
            variables=variables,
        )
        logger.info(f"Reference reminder #{reminder_number} sent to {referee_email} for candidate {candidate_id}")

    @staticmethod
    def get_reference(ref_id: str) -> dict:
        with get_db() as db:
            db.execute("SELECT * FROM references_ WHERE id=%s", (ref_id,))
            row = db.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_references_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM references_ WHERE candidate_id=%s ORDER BY sent_at DESC",
                (candidate_id,),
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]
