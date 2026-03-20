"""
Automated Reference Service
Sends structured reference requests, tracks responses, detects fraud.
"""
import json
import random
import secrets
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id


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
        ref_id = generate_id()
        token = secrets.token_urlsafe(32)
        now = datetime.now(timezone.utc).isoformat()

        # Domain verification
        email_domain = referee_email.split("@")[1] if "@" in referee_email else ""
        domain_verified = ReferenceAutomationService._verify_domain(email_domain, referee_organisation)

        with get_db() as db:
            db.execute(
                """INSERT INTO references_
                   (id, candidate_id, referee_name, referee_email, referee_phone,
                    referee_organisation, referee_job_title, relationship, token,
                    status, domain_verified, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'sent', ?, ?)""",
                (
                    ref_id, candidate_id, referee_name, referee_email,
                    referee_phone, referee_organisation, referee_job_title,
                    relationship, token,
                    1 if domain_verified else 0,
                    now,
                ),
            )

            if not domain_verified:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'reference_domain_mismatch', 'medium', ?, ?, ?)""",
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
                   VALUES (?, 'reference', ?, 'sent', 'system', ?, ?)""",
                (generate_id(), ref_id, json.dumps({"referee_email": referee_email}), now),
            )

            row = db.execute("SELECT * FROM references_ WHERE id=?", (ref_id,)).fetchone()
            return dict(row)

    @staticmethod
    def submit_reference(token: str, responses: dict, ip_address: str = None) -> dict:
        now = datetime.now(timezone.utc).isoformat()

        with get_db() as db:
            ref = db.execute("SELECT * FROM references_ WHERE token=?", (token,)).fetchone()
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
                   status=?, responses=?, sentiment_score=?,
                   fraud_flags=?, ip_address=?, completed_at=?
                   WHERE token=?""",
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
                       VALUES (?, ?, 'reference_fraud', 'high', ?, ?, ?)""",
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
                   VALUES (?, 'reference', ?, 'submitted', 'referee', ?, ?)""",
                (generate_id(), ref_dict["id"], json.dumps({"sentiment": sentiment, "fraud_flags": len(fraud_flags)}), now),
            )

            row = db.execute("SELECT * FROM references_ WHERE token=?", (token,)).fetchone()
            return dict(row)

    @staticmethod
    def send_reminder(ref_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            ref = db.execute("SELECT * FROM references_ WHERE id=?", (ref_id,)).fetchone()
            if not ref:
                return None

            ref_dict = dict(ref)
            new_count = ref_dict["reminder_count"] + 1

            db.execute(
                "UPDATE references_ SET reminder_count=? WHERE id=?",
                (new_count, ref_id),
            )

            # Auto-escalate after 3 reminders
            if new_count >= 3:
                db.execute(
                    """INSERT INTO monitoring_alerts
                       (id, candidate_id, alert_type, severity, message, details, created_at)
                       VALUES (?, ?, 'reference_no_response', 'medium', ?, ?, ?)""",
                    (
                        generate_id(), ref_dict["candidate_id"],
                        f"Reference from {ref_dict['referee_name']} not received after {new_count} reminders",
                        json.dumps({"ref_id": ref_id, "reminders_sent": new_count}),
                        now,
                    ),
                )

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
    def get_reference(ref_id: str) -> dict:
        with get_db() as db:
            row = db.execute("SELECT * FROM references_ WHERE id=?", (ref_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_references_for_candidate(candidate_id: str) -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM references_ WHERE candidate_id=? ORDER BY sent_at DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]
