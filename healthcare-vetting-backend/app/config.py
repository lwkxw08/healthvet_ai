"""
Centralised application configuration — all environment-driven settings in one place.

Usage:
    from app.config import BASE_URL, DASHBOARD_URL
"""
import os

# ── Base URL for outbound links (verification emails, reference requests) ────
# Must be set to the public-facing URL of this deployment.
BASE_URL = os.environ.get("BASE_URL", "https://app-wwjesgoe.fly.dev")

# ── Dashboard URL for notification emails (may differ if frontend is hosted separately) ──
DASHBOARD_URL = os.environ.get("DASHBOARD_URL", BASE_URL)
