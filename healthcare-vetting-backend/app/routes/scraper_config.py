"""
Admin API routes for Scraper Configuration.
Allows admins to configure API keys for lead-generation scrapers
(currently only the CQC Syndication API key) directly from the admin UI
instead of requiring environment variables.
"""
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.database import get_db
from app.utils.auth import get_current_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/scraper-config", tags=["scraper-config"])

SCRAPER_SETTING_KEYS = [
    "cqc_api_subscription_key",
]


class ScraperConfigUpdate(BaseModel):
    cqc_api_subscription_key: Optional[str] = ""


def _get_setting(db, key: str) -> str:
    db.execute(
        "SELECT setting_value FROM system_settings WHERE setting_key = %s",
        (key,),
    )
    row = db.fetchone()
    return dict(row)["setting_value"] if row else ""


def _set_setting(db, key: str, value: str):
    now = datetime.now(timezone.utc).isoformat()
    db.execute(
        """INSERT INTO system_settings (setting_key, setting_value, updated_at)
           VALUES (%s, %s, %s)
           ON CONFLICT(setting_key) DO UPDATE
             SET setting_value = %s, updated_at = %s""",
        (key, value, now, value, now),
    )


def _mask(key: str) -> str:
    if not key:
        return ""
    if len(key) < 8:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


@router.get("")
async def get_scraper_config(admin=Depends(get_current_admin)):
    """Return the current scraper configuration. API keys are masked."""
    with get_db() as db:
        config = {}
        for key in SCRAPER_SETTING_KEYS:
            val = _get_setting(db, key)
            if val:
                config[key] = _mask(val)
                config[f"{key}_set"] = True
            else:
                config[key] = ""
                config[f"{key}_set"] = False
    return config


@router.put("")
async def update_scraper_config(
    data: ScraperConfigUpdate,
    admin=Depends(get_current_admin),
):
    """Upsert scraper configuration values.

    Masked values (leading '*') are ignored so editing one key doesn't
    wipe the others.
    """
    with get_db() as db:
        updates = data.dict()
        for key, value in updates.items():
            if value is None:
                value = ""
            if value and value.startswith("*"):
                continue
            _set_setting(db, key, value)
    logger.info(
        "Scraper configuration updated by admin %s",
        admin.get("email", "unknown"),
    )
    return {"status": "ok", "message": "Scraper configuration updated"}


@router.post("/test-cqc")
async def test_cqc_connectivity(admin=Depends(get_current_admin)):
    """Smoke-test the CQC API with the currently stored key."""
    import requests as _rq
    from app.services.lead_scrapers import _get_cqc_api_key
    key = _get_cqc_api_key()
    if not key:
        return {
            "status": "no_key",
            "message": (
                "No CQC API subscription key configured. "
                "Request one from https://www.cqc.org.uk/about-us/transparency/"
                "using-cqc-data and save it above."
            ),
        }
    try:
        resp = _rq.get(
            "https://api.cqc.org.uk/public/v1/providers",
            params={"perPage": 1, "page": 1},
            headers={
                "Ocp-Apim-Subscription-Key": key,
                "User-Agent": "ViperAI/1.0 (compliance platform)",
                "Accept": "application/json",
            },
            timeout=15,
        )
    except Exception as e:
        return {
            "status": "error",
            "message": f"CQC API unreachable: {e}",
        }

    if resp.status_code == 200:
        total = ""
        try:
            total = str(resp.json().get("total", ""))
        except Exception:
            pass
        return {
            "status": "ok",
            "message": (
                "CQC API connectivity OK"
                + (f" (total providers: {total})" if total else "")
            ),
        }
    if resp.status_code in (401, 403):
        return {
            "status": "auth_failed",
            "message": (
                f"CQC API rejected the key ({resp.status_code}). "
                f"Double-check the subscription key. Body: {resp.text[:200]}"
            ),
        }
    return {
        "status": "error",
        "message": (
            f"CQC API returned HTTP {resp.status_code}: {resp.text[:200]}"
        ),
    }
