"""
Email Notification Service
Handles sending email notifications for monitoring alerts, expiry warnings, and invoices.
In production, integrate with SendGrid, AWS SES, or similar.
Currently logs emails (simulated) and stores them in the database for the UI to display.
"""
import json
import logging
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class EmailService:
    """Email notification service. Currently simulated - stores in DB and logs."""

    @staticmethod
    def _store_notification(recipient_email: str, recipient_name: str, subject: str,
                           body: str, notification_type: str, related_id: str = None):
        """Store notification in database."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with get_db() as db:
                db.execute(
                    """INSERT INTO email_notifications
                       (id, recipient_email, recipient_name, subject, body,
                        notification_type, related_id, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, 'sent', ?)""",
                    (generate_id(), recipient_email, recipient_name, subject,
                     body, notification_type, related_id, now),
                )
        except Exception as e:
            logger.error(f"Failed to store notification: {e}")

    @staticmethod
    def send_monitoring_summary(results: dict):
        """Send monitoring summary to all agencies with affected candidates."""
        from app.database import get_db

        with get_db() as db:
            agencies = db.execute("SELECT * FROM agencies").fetchall()
            for agency in agencies:
                a = dict(agency)
                # Get agency's candidates
                candidates = db.execute(
                    "SELECT candidate_id FROM agency_candidates WHERE agency_id=?",
                    (a["id"],),
                ).fetchall()
                candidate_ids = {dict(c)["candidate_id"] for c in candidates}

                # Check if any alerts affect this agency's candidates
                affected = []
                for alert_type, alerts in results.items():
                    for alert in alerts:
                        if alert.get("candidate_id") in candidate_ids:
                            affected.append({"type": alert_type, **alert})

                if affected:
                    subject = f"HealthVet AI - {len(affected)} New Monitoring Alert(s)"
                    body = f"Dear {a.get('contact_name', a['name'])},\n\n"
                    body += f"Our automated monitoring has detected {len(affected)} new alert(s) "
                    body += "for your candidates:\n\n"
                    for alert in affected:
                        body += f"  - {alert['type'].replace('_', ' ').title()}: "
                        body += f"Candidate {alert.get('candidate_id', 'N/A')}\n"
                    body += "\nPlease log in to your dashboard to review these alerts.\n"
                    body += "\nBest regards,\nHealthVet AI Compliance Team"

                    EmailService._store_notification(
                        a["email"], a["name"], subject, body,
                        "monitoring_summary", None,
                    )
                    logger.info(f"Monitoring summary sent to {a['email']}: {len(affected)} alerts")

    @staticmethod
    def send_expiry_warnings(notifications: list):
        """Send expiry warning emails to agencies and candidates."""
        # Group by agency
        by_agency = {}
        for n in notifications:
            agency_email = n.get("agency_email")
            if agency_email:
                if agency_email not in by_agency:
                    by_agency[agency_email] = {"name": n.get("agency_name", ""), "items": []}
                by_agency[agency_email]["items"].append(n)

        # Send agency summary emails
        for email, data in by_agency.items():
            subject = f"HealthVet AI - {len(data['items'])} Credential(s) Expiring Soon"
            body = f"Dear {data['name']},\n\n"
            body += "The following credentials are expiring soon:\n\n"
            for item in data["items"]:
                type_label = item["type"].replace("_", " ").title()
                body += f"  - {item['candidate_name']}: {type_label} "
                body += f"expires in {item['days_left']} days ({item['expiry_date']})\n"
            body += "\nPlease take action to ensure continued compliance.\n"
            body += "\nBest regards,\nHealthVet AI Compliance Team"

            EmailService._store_notification(
                email, data["name"], subject, body,
                "expiry_warning", None,
            )

        # Send candidate notification emails
        for n in notifications:
            candidate_email = n.get("candidate_email")
            if candidate_email:
                type_label = n["type"].replace("_", " ").title()
                subject = f"HealthVet AI - Your {type_label} Expires in {n['days_left']} Days"
                body = f"Dear {n['candidate_name']},\n\n"
                body += f"Your {type_label} is due to expire on {n['expiry_date']} "
                body += f"({n['days_left']} days from now).\n\n"
                body += "Please take action to renew this credential to maintain your compliance status.\n"
                body += "\nBest regards,\nHealthVet AI Compliance Team"

                EmailService._store_notification(
                    candidate_email, n["candidate_name"], subject, body,
                    "expiry_warning_candidate", None,
                )

    @staticmethod
    def send_invoice_notification(agency_email: str, agency_name: str,
                                  invoice_id: str, amount: float, description: str):
        """Send invoice notification to agency."""
        subject = f"HealthVet AI - New Invoice #{invoice_id[:8]}"
        body = f"Dear {agency_name},\n\n"
        body += f"A new invoice has been generated:\n\n"
        body += f"  Invoice: #{invoice_id[:8]}\n"
        body += f"  Amount: \u00a3{amount:.2f}\n"
        body += f"  Description: {description}\n\n"
        body += "Please log in to your dashboard to view and pay this invoice.\n"
        body += "\nBest regards,\nHealthVet AI Billing Team"

        EmailService._store_notification(
            agency_email, agency_name, subject, body,
            "invoice", invoice_id,
        )

    @staticmethod
    def send_subscription_confirmation(agency_email: str, agency_name: str,
                                        plan_name: str, amount: float):
        """Send subscription confirmation email."""
        subject = f"HealthVet AI - Subscription Confirmed: {plan_name}"
        body = f"Dear {agency_name},\n\n"
        body += f"Your subscription has been confirmed:\n\n"
        body += f"  Plan: {plan_name}\n"
        body += f"  Monthly Amount: \u00a3{amount:.2f}\n\n"
        body += "Thank you for choosing HealthVet AI.\n"
        body += "\nBest regards,\nHealthVet AI Team"

        EmailService._store_notification(
            agency_email, agency_name, subject, body,
            "subscription", None,
        )

    @staticmethod
    def get_notifications(recipient_email: str = None, notification_type: str = None,
                          limit: int = 50) -> list:
        """Get stored notifications."""
        with get_db() as db:
            query = "SELECT * FROM email_notifications"
            conditions = []
            params = []
            if recipient_email:
                conditions.append("recipient_email=?")
                params.append(recipient_email)
            if notification_type:
                conditions.append("notification_type=?")
                params.append(notification_type)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = db.execute(query, params).fetchall()
            return [dict(r) for r in rows]
