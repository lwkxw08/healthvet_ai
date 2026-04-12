"""
Email Notification Service
Handles sending email notifications for monitoring alerts, expiry warnings, and invoices.
Now uses the template system for rendering and SendGrid for delivery when configured.
Falls back to DB-only storage when no SendGrid API key is set.
"""
import json
import logging
from datetime import datetime, timezone
from app.config import DASHBOARD_URL
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class EmailService:
    """Email notification service. Uses rules engine + templates + SendGrid when available."""

    @staticmethod
    def _resolve_template_key(
        action_trigger: str,
        default_template_key: str,
        recipient_type: str = None,
        context: dict = None,
    ) -> str:
        """Resolve which template to use via the rules engine, falling back to the hardcoded default."""
        try:
            from app.services.email_rules import EmailRulesService
            matched = EmailRulesService.resolve_template_for_action(
                action_trigger, recipient_type=recipient_type, context=context,
            )
            if matched:
                resolved_key = matched[0]["template_key"]
                logger.debug(f"Rule resolved: {action_trigger} -> {resolved_key} (rule: {matched[0]['rule_name']})")
                return resolved_key
        except Exception as e:
            logger.warning(f"Rules engine lookup failed, using default: {e}")
        return default_template_key

    @staticmethod
    def _send_via_template(template_key: str, recipient_email: str,
                           recipient_name: str, variables: dict,
                           fallback_subject: str = "", fallback_body: str = "",
                           notification_type: str = None, related_id: str = None):
        """Try to send via template system; fall back to legacy storage."""
        try:
            from app.services.email_templates import EmailTemplateService
            result = EmailTemplateService.send_email(
                template_key=template_key,
                recipient_email=recipient_email,
                recipient_name=recipient_name,
                variables=variables,
            )
            if result and result.get("status") != "error":
                return result
        except Exception as e:
            logger.warning(f"Template send failed, using fallback: {e}")

        # Fallback: store in legacy email_notifications table
        EmailService._store_notification(
            recipient_email, recipient_name,
            fallback_subject, fallback_body,
            notification_type or template_key, related_id,
        )
        return {"status": "fallback"}

    @staticmethod
    def _store_notification(recipient_email: str, recipient_name: str, subject: str,
                           body: str, notification_type: str, related_id: str = None):
        """Store notification in database (legacy)."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            with get_db() as db:
                db.execute(
                    """INSERT INTO email_notifications
                       (id, recipient_email, recipient_name, subject, body,
                        notification_type, related_id, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, %s, 'sent', %s)""",
                    (generate_id(), recipient_email, recipient_name, subject,
                     body, notification_type, related_id, now),
                )
        except Exception as e:
            logger.error(f"Failed to store notification: {e}")

    @staticmethod
    def send_monitoring_summary(results: dict):
        """Send monitoring summary to all agencies with affected candidates."""
        with get_db() as db:
            db.execute("SELECT * FROM agencies")
            agencies = db.fetchall()
            for agency in agencies:
                a = dict(agency)
                candidates = db.execute(
                    "SELECT candidate_id FROM agency_candidates WHERE agency_id=%s",
                    (a["id"],),
                )
                candidates = db.fetchall()
                candidate_ids = {dict(c)["candidate_id"] for c in candidates}

                affected = []
                for alert_type, alerts in results.items():
                    for alert in alerts:
                        if alert.get("candidate_id") in candidate_ids:
                            affected.append({"type": alert_type, **alert})

                if affected:
                    # Build alert list HTML and text
                    alert_items_html = ""
                    alert_items_text = ""
                    for alert in affected:
                        label = alert["type"].replace("_", " ").title()
                        cid = alert.get("candidate_id", "N/A")
                        alert_items_html += f'<p style="margin:4px 0;">&#8226; <strong>{label}</strong>: Candidate {cid}</p>'
                        alert_items_text += f"  - {label}: Candidate {cid}\n"

                    variables = {
                        "agency_name": a.get("contact_name", a["name"]),
                        "alert_count": str(len(affected)),
                        "alert_items_html": alert_items_html,
                        "alert_items_text": alert_items_text,
                        "dashboard_link": f"{DASHBOARD_URL}/agency/dashboard",
                    }

                    fallback_subject = f"HealthVet AI - {len(affected)} New Monitoring Alert(s)"
                    fallback_body = f"Dear {a.get('contact_name', a['name'])},\n\n"
                    fallback_body += f"Our automated monitoring has detected {len(affected)} new alert(s) for your candidates:\n\n"
                    fallback_body += alert_items_text
                    fallback_body += "\nPlease log in to your dashboard to review these alerts.\n"
                    fallback_body += "\nBest regards,\nHealthVet AI Compliance Team"

                    resolved_key = EmailService._resolve_template_key(
                        "monitoring_alerts_detected", "monitoring_alert_summary",
                        recipient_type="agency",
                    )
                    EmailService._send_via_template(
                        resolved_key, a["email"], a["name"],
                        variables, fallback_subject, fallback_body,
                        "monitoring_summary",
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
            items_html = ""
            items_text = ""
            for item in data["items"]:
                type_label = item["type"].replace("_", " ").title()
                items_html += f'<p style="margin:4px 0;">&#8226; <strong>{item["candidate_name"]}</strong>: {type_label} expires in {item["days_left"]} days ({item["expiry_date"]})</p>'
                items_text += f"  - {item['candidate_name']}: {type_label} expires in {item['days_left']} days ({item['expiry_date']})\n"

            variables = {
                "agency_name": data["name"],
                "expiry_count": str(len(data["items"])),
                "expiry_items_html": items_html,
                "expiry_items_text": items_text,
                "dashboard_link": f"{DASHBOARD_URL}/agency/dashboard",
            }

            fallback_subject = f"HealthVet AI - {len(data['items'])} Credential(s) Expiring Soon"
            fallback_body = f"Dear {data['name']},\n\nThe following credentials are expiring soon:\n\n{items_text}\nPlease take action.\n\nBest regards,\nHealthVet AI"

            resolved_key = EmailService._resolve_template_key(
                "credential_expiring", "expiry_warning_agency",
                recipient_type="agency",
            )
            EmailService._send_via_template(
                resolved_key, email, data["name"],
                variables, fallback_subject, fallback_body,
                "expiry_warning",
            )

        # Send candidate notification emails
        for n in notifications:
            candidate_email = n.get("candidate_email")
            if candidate_email:
                type_label = n["type"].replace("_", " ").title()
                variables = {
                    "candidate_name": n["candidate_name"],
                    "credential_type": type_label,
                    "expiry_date": n["expiry_date"],
                    "days_left": str(n["days_left"]),
                    "portal_link": f"{DASHBOARD_URL}/candidate/portal",
                }

                fallback_subject = f"HealthVet AI - Your {type_label} Expires in {n['days_left']} Days"
                fallback_body = f"Dear {n['candidate_name']},\n\nYour {type_label} expires on {n['expiry_date']} ({n['days_left']} days).\n\nBest regards,\nHealthVet AI"

                resolved_key = EmailService._resolve_template_key(
                    "credential_expiring", "expiry_warning_candidate",
                    recipient_type="candidate",
                    context={"days_left": n.get("days_left", 0)},
                )
                EmailService._send_via_template(
                    resolved_key, candidate_email, n["candidate_name"],
                    variables, fallback_subject, fallback_body,
                    "expiry_warning_candidate",
                )

    @staticmethod
    def send_invoice_notification(agency_email: str, agency_name: str,
                                  invoice_id: str, amount: float, description: str):
        """Send invoice notification to agency."""
        variables = {
            "agency_name": agency_name,
            "invoice_ref": invoice_id[:8],
            "amount": f"\u00a3{amount:.2f}",
            "description": description,
            "invoice_date": datetime.now(timezone.utc).strftime("%d %B %Y"),
            "payment_link": f"{DASHBOARD_URL}/agency/billing",
        }

        fallback_subject = f"HealthVet AI - New Invoice #{invoice_id[:8]}"
        fallback_body = f"Dear {agency_name},\n\nInvoice #{invoice_id[:8]}: \u00a3{amount:.2f}\nDescription: {description}\n\nBest regards,\nHealthVet AI"

        resolved_key = EmailService._resolve_template_key(
            "invoice_created", "invoice_notification",
            recipient_type="agency",
        )
        EmailService._send_via_template(
            resolved_key, agency_email, agency_name,
            variables, fallback_subject, fallback_body,
            "invoice", invoice_id,
        )

    @staticmethod
    def send_subscription_confirmation(agency_email: str, agency_name: str,
                                        plan_name: str, amount: float):
        """Send subscription / credit pack confirmation email."""
        variables = {
            "agency_name": agency_name,
            "plan_name": plan_name,
            "credits": "",
            "amount": f"\u00a3{amount:.2f}",
            "expiry_date": "",
            "dashboard_link": f"{DASHBOARD_URL}/agency/dashboard",
        }

        fallback_subject = f"HealthVet AI - Subscription Confirmed: {plan_name}"
        fallback_body = f"Dear {agency_name},\n\nPlan: {plan_name}\nAmount: \u00a3{amount:.2f}\n\nBest regards,\nHealthVet AI"

        resolved_key = EmailService._resolve_template_key(
            "subscription_purchased", "subscription_confirmation",
            recipient_type="agency",
        )
        EmailService._send_via_template(
            resolved_key, agency_email, agency_name,
            variables, fallback_subject, fallback_body,
            "subscription",
        )

    @staticmethod
    def send_payment_reminder(agency_email: str, agency_name: str,
                               invoice_id: str, amount: float, description: str,
                               urgency: str = "Reminder"):
        """Send payment reminder for unpaid invoice."""
        urgency_msg = ""
        if urgency == "Final Notice":
            urgency_msg = '<p style="color:#ef4444;font-weight:600;">IMPORTANT: This is your final payment reminder.</p>'

        variables = {
            "agency_name": agency_name,
            "invoice_ref": invoice_id[:8],
            "amount": f"\u00a3{amount:.2f}",
            "description": description,
            "urgency": urgency,
            "urgency_message": urgency_msg,
            "payment_link": f"{DASHBOARD_URL}/agency/billing",
        }

        fallback_subject = f"HealthVet AI - {urgency}: Invoice #{invoice_id[:8]} Payment Due"
        fallback_body = f"Dear {agency_name},\n\nInvoice #{invoice_id[:8]}: \u00a3{amount:.2f}\n{description}\n\nBest regards,\nHealthVet AI"

        resolved_key = EmailService._resolve_template_key(
            "payment_overdue", "payment_reminder",
            recipient_type="agency",
            context={"urgency": urgency},
        )
        EmailService._send_via_template(
            resolved_key, agency_email, agency_name,
            variables, fallback_subject, fallback_body,
            "payment_reminder", invoice_id,
        )

    @staticmethod
    def send_trustid_submission_confirmation(
        candidate_email: str, candidate_name: str, check_types: list[str] | None = None,
    ):
        """Send confirmation to candidate that TrustID checks have been submitted.
        Informs them to expect contact from TrustID within 24 hours."""
        check_labels = {
            "identity_verification": "Identity Verification",
            "dbs_check": "Enhanced DBS Check",
            "right_to_work": "Right to Work Verification",
        }
        if not check_types:
            check_types = list(check_labels.keys())

        checks_html = "".join(
            f'<li style="margin:4px 0;">{check_labels.get(ct, ct)}</li>' for ct in check_types
        )
        checks_text = "\n".join(f"  - {check_labels.get(ct, ct)}" for ct in check_types)

        variables = {
            "candidate_name": candidate_name or "Candidate",
            "checks_html": f"<ul>{checks_html}</ul>",
            "checks_text": checks_text,
            "partner_name": "TrustID",
            "contact_window": "24 hours",
        }

        fallback_subject = "HealthVet AI - Your Verification Checks Have Been Submitted"
        fallback_body = (
            f"Dear {candidate_name or 'Candidate'},\n\n"
            "Thank you for completing your submission on HealthVet AI.\n\n"
            "The following checks will now be carried out by our trusted partner, TrustID:\n\n"
            f"{checks_text}\n\n"
            "WHAT HAPPENS NEXT:\n"
            "TrustID will contact you within 24 hours to complete the verification process. "
            "They will guide you through their secure identity verification, DBS application, "
            "and right to work checks.\n\n"
            "Please keep an eye on your email (including spam/junk folders) for correspondence "
            "from TrustID.\n\n"
            "If you have not been contacted within 24 hours, please reach out to your agency "
            "or contact us at support@healthvet.ai.\n\n"
            "Best regards,\n"
            "HealthVet AI Compliance Team"
        )

        resolved_key = EmailService._resolve_template_key(
            "trustid_checks_submitted", "trustid_submission_confirmation",
            recipient_type="candidate",
        )
        EmailService._send_via_template(
            resolved_key, candidate_email, candidate_name or "Candidate",
            variables, fallback_subject, fallback_body,
            "trustid_submission", None,
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
                conditions.append("recipient_email=%s")
                params.append(recipient_email)
            if notification_type:
                conditions.append("notification_type=%s")
                params.append(notification_type)
            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            db.execute(query, params)
            rows = db.fetchall()
            return [dict(r) for r in rows]
