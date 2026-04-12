"""
SMS Notification Channel — scaffolding for future SMS integration.

Currently supports a pluggable provider architecture with:
  - Twilio (production)
  - Console/log (development/testing)

To enable SMS:
  1. Set SMS_ENABLED=1 in environment
  2. Set SMS_PROVIDER=twilio (or 'console' for testing)
  3. Configure provider-specific credentials (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER)

SMS notifications are stored in the sms_notifications table for audit/retry.
"""
import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone

from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────────────────

SMS_ENABLED = os.environ.get("SMS_ENABLED", "0") in ("1", "true", "yes")
SMS_PROVIDER = os.environ.get("SMS_PROVIDER", "console")  # twilio | console


# ── Provider Interface ───────────────────────────────────────────────────────

class SMSProvider(ABC):
    """Base class for SMS providers."""

    @abstractmethod
    def send(self, to: str, message: str) -> dict:
        """Send an SMS message. Returns provider-specific response dict."""
        ...


class ConsoleSMSProvider(SMSProvider):
    """Development provider — logs messages to console instead of sending."""

    def send(self, to: str, message: str) -> dict:
        logger.info("[SMS-CONSOLE] To: %s | Message: %s", to, message)
        return {"provider": "console", "status": "logged", "to": to}


class TwilioSMSProvider(SMSProvider):
    """Twilio SMS provider — sends real SMS via Twilio REST API."""

    def __init__(self) -> None:
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.environ.get("TWILIO_FROM_NUMBER", "")

    def send(self, to: str, message: str) -> dict:
        if not all([self.account_sid, self.auth_token, self.from_number]):
            logger.error("Twilio credentials not configured")
            return {"provider": "twilio", "status": "error", "error": "credentials_missing"}

        try:
            import urllib.request
            import urllib.parse
            import base64

            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            data = urllib.parse.urlencode({
                "To": to,
                "From": self.from_number,
                "Body": message,
            }).encode("utf-8")

            credentials = base64.b64encode(
                f"{self.account_sid}:{self.auth_token}".encode()
            ).decode("ascii")

            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Authorization", f"Basic {credentials}")

            with urllib.request.urlopen(req, timeout=15) as resp:
                resp_data = json.loads(resp.read().decode("utf-8"))
                return {
                    "provider": "twilio",
                    "status": "sent",
                    "sid": resp_data.get("sid"),
                    "to": to,
                }

        except Exception as e:
            logger.error("Twilio SMS send failed: %s", e)
            return {"provider": "twilio", "status": "error", "error": str(e)}


# ── Provider Factory ─────────────────────────────────────────────────────────

_providers: dict[str, type[SMSProvider]] = {
    "console": ConsoleSMSProvider,
    "twilio": TwilioSMSProvider,
}


def _get_provider() -> SMSProvider:
    provider_cls = _providers.get(SMS_PROVIDER, ConsoleSMSProvider)
    return provider_cls()


# ── SMS Service ──────────────────────────────────────────────────────────────

class SMSService:
    """High-level SMS notification service with persistence and audit trail."""

    @staticmethod
    def is_enabled() -> bool:
        """Check if SMS notifications are enabled."""
        return SMS_ENABLED

    @staticmethod
    def send_sms(
        to_number: str,
        message: str,
        user_id: str | None = None,
        user_type: str | None = None,
        category: str = "general",
        reference_id: str | None = None,
    ) -> dict:
        """Send an SMS and record it in the database.

        Returns dict with status and provider response.
        """
        if not SMS_ENABLED:
            return {"status": "disabled", "message": "SMS notifications are not enabled"}

        now = datetime.now(timezone.utc).isoformat()
        sms_id = generate_id()
        provider = _get_provider()

        # Send via provider
        result = provider.send(to_number, message)
        status = "sent" if result.get("status") == "sent" or result.get("status") == "logged" else "failed"

        # Persist to database for audit
        with get_db() as db:
            db.execute(
                """INSERT INTO sms_notifications
                   (id, user_id, user_type, to_number, message, category,
                    reference_id, provider, status, provider_response, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (sms_id, user_id, user_type, to_number, message, category,
                 reference_id, SMS_PROVIDER, status, json.dumps(result), now),
            )

        return {"sms_id": sms_id, "status": status, "provider_response": result}

    @staticmethod
    def send_verification_reminder(candidate_phone: str, candidate_name: str, check_type: str) -> dict:
        """Send a reminder SMS to a candidate about a pending verification."""
        message = (
            f"Hi {candidate_name}, your {check_type.replace('_', ' ')} verification is pending. "
            f"Please log in to complete it. — HealthVet AI"
        )
        return SMSService.send_sms(
            to_number=candidate_phone,
            message=message,
            category="verification_reminder",
        )

    @staticmethod
    def send_expiry_warning(candidate_phone: str, candidate_name: str, check_type: str, days_until: int) -> dict:
        """Send an SMS warning about an upcoming expiry."""
        message = (
            f"Hi {candidate_name}, your {check_type.replace('_', ' ')} expires in {days_until} days. "
            f"Please renew before it lapses. — HealthVet AI"
        )
        return SMSService.send_sms(
            to_number=candidate_phone,
            message=message,
            category="expiry_warning",
        )

    @staticmethod
    def send_status_update(candidate_phone: str, candidate_name: str, status_message: str) -> dict:
        """Send a general status update SMS."""
        message = f"Hi {candidate_name}, {status_message} — HealthVet AI"
        return SMSService.send_sms(
            to_number=candidate_phone,
            message=message,
            category="status_update",
        )

    @staticmethod
    def get_sms_history(
        user_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Get SMS notification history."""
        with get_db() as db:
            if user_id:
                rows = db.execute(
                    "SELECT * FROM sms_notifications WHERE user_id=%s ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (user_id, limit, offset),
                )
                rows = db.fetchall()
            else:
                rows = db.execute(
                    "SELECT * FROM sms_notifications ORDER BY created_at DESC LIMIT %s OFFSET %s",
                    (limit, offset),
                )
                rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_config() -> dict:
        """Get current SMS configuration (without secrets)."""
        return {
            "enabled": SMS_ENABLED,
            "provider": SMS_PROVIDER,
            "twilio_configured": bool(
                os.environ.get("TWILIO_ACCOUNT_SID")
                and os.environ.get("TWILIO_AUTH_TOKEN")
                and os.environ.get("TWILIO_FROM_NUMBER")
            ),
        }
