"""
Admin API routes for Email Provider Configuration.
Allows admins to configure email provider settings (API keys, sender info)
directly from the admin UI instead of requiring environment variables.
"""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.utils.auth import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/email-config", tags=["email-config"])

# Settings keys used for email configuration
EMAIL_SETTING_KEYS = [
    "email_provider",        # "sendgrid", "mailgun", "resend", or "" for auto-detect
    "sendgrid_api_key",
    "mailgun_api_key",
    "mailgun_domain",
    "resend_api_key",
    "email_from_address",
    "email_from_name",
]


class EmailConfigUpdate(BaseModel):
    email_provider: Optional[str] = ""
    sendgrid_api_key: Optional[str] = ""
    mailgun_api_key: Optional[str] = ""
    mailgun_domain: Optional[str] = ""
    resend_api_key: Optional[str] = ""
    email_from_address: Optional[str] = ""
    email_from_name: Optional[str] = ""


def _get_setting(db, key: str) -> str:
    """Get a single setting value from the database."""
    row = db.execute(
        "SELECT setting_value FROM system_settings WHERE setting_key = ?", (key,)
    ).fetchone()
    return dict(row)["setting_value"] if row else ""


def _set_setting(db, key: str, value: str):
    """Upsert a single setting value in the database."""
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO system_settings (setting_key, setting_value, updated_at)
           VALUES (?, ?, ?)
           ON CONFLICT(setting_key) DO UPDATE SET setting_value = ?, updated_at = ?""",
        (key, value, now, value, now),
    )


def get_email_config_from_db() -> dict:
    """Read all email config settings from the database.
    Returns a dict of setting_key -> setting_value.
    Used by the email service to load config from DB.
    """
    result = {}
    try:
        with get_db() as db:
            for key in EMAIL_SETTING_KEYS:
                result[key] = _get_setting(db, key)
    except Exception:
        # Table might not exist yet during startup
        pass
    return result


def mask_api_key(key: str) -> str:
    """Mask an API key for display, showing only last 4 characters."""
    if not key or len(key) < 8:
        return "****" if key else ""
    return "*" * (len(key) - 4) + key[-4:]


@router.get("")
async def get_email_config(admin=Depends(get_current_admin)):
    """Get current email provider configuration (API keys are masked)."""
    with get_db() as db:
        config = {}
        for key in EMAIL_SETTING_KEYS:
            val = _get_setting(db, key)
            # Mask API keys for security
            if "api_key" in key and val:
                config[key] = mask_api_key(val)
                config[f"{key}_set"] = True
            else:
                config[key] = val
                if "api_key" in key:
                    config[f"{key}_set"] = False

        # Show which provider is currently active
        from app.services.email_templates import get_active_provider_info
        config["active_provider"] = get_active_provider_info()

    return config


@router.put("")
async def update_email_config(data: EmailConfigUpdate, admin=Depends(get_current_admin)):
    """Update email provider configuration."""
    with get_db() as db:
        updates = data.dict()
        for key, value in updates.items():
            if value is None:
                value = ""
            # Don't overwrite API keys with masked values
            if "api_key" in key and value and value.startswith("*"):
                continue
            _set_setting(db, key, value)

    # Reload config in the email service
    from app.services.email_templates import reload_email_config
    reload_email_config()

    logger.info(f"Email configuration updated by admin {admin.get('email', 'unknown')}")
    return {"status": "ok", "message": "Email configuration updated"}


@router.post("/test")
async def test_email_config(admin=Depends(get_current_admin)):
    """Test the current email configuration by checking provider connectivity."""
    from app.services.email_templates import get_active_provider_info, reload_email_config
    reload_email_config()
    info = get_active_provider_info()

    if not info.get("provider"):
        return {
            "status": "no_provider",
            "message": "No email provider configured. Emails will be logged to the database only.",
        }

    return {
        "status": "ok",
        "message": f"Provider '{info['provider']}' is configured and ready to send emails.",
        "provider": info["provider"],
        "from_email": info.get("from_email", ""),
        "from_name": info.get("from_name", ""),
    }
