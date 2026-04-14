"""
Email Template Management Service
Stores, retrieves, and renders email templates with variable substitution.
Supports multiple email providers: SendGrid, Mailgun, and Resend.
"""
import json
import logging
import os
import re
import secrets
import string
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


# ── Verification Code Generation ─────────────────────────────────────────────

# Alphabet excludes ambiguous characters: 0/O, 1/I/L
_CODE_ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


def generate_verification_code() -> str:
    """Generate a short human-readable verification code like HV-7X9K-2M4P."""
    part1 = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
    part2 = "".join(secrets.choice(_CODE_ALPHABET) for _ in range(4))
    return f"HV-{part1}-{part2}"


# ── Trust Signal Defaults ─────────────────────────────────────────────────────
# These are injected into verification templates automatically.
# Admins can override them via Admin → Settings → Email Provider (trust settings).

TRUST_SIGNAL_DEFAULTS = {
    "company_reg_info": "Registered in England & Wales",
    "ico_registration": "Pending",
    "verification_phone": "+44 (0) XXX XXX XXXX",
    "verification_email": "verify@viperai.io",
    "privacy_url": "https://viperai.io/privacy",
    "verification_url": "verify.viperai.io",
}

INVOICE_SETTINGS_DEFAULTS = {
    "company_name": "Viper AI Ltd",
    "company_address": "",
    "company_email": "billing@viperai.io",
    "company_phone": "+44 (0) XXX XXX XXXX",
    "company_reg_info": "Registered in England & Wales",
    "vat_number": "",
    "vat_rate": "20",
    "bank_account_name": "",
    "bank_sort_code": "",
    "bank_account_number": "",
    "bank_iban": "",
    "payment_terms": "Net 30",
}


def get_trust_signal_variables() -> dict:
    """Load trust signal values from DB settings, falling back to defaults."""
    result = dict(TRUST_SIGNAL_DEFAULTS)
    try:
        with get_db() as db:
            for key in TRUST_SIGNAL_DEFAULTS:
                db.execute(
                    "SELECT setting_value FROM system_settings WHERE setting_key=%s",
                    (f"trust_{key}",),
                )
                row = db.fetchone()
                if row and row["setting_value"]:
                    result[key] = row["setting_value"]
    except Exception:
        pass
    return result


def get_invoice_settings() -> dict:
    """Load invoice / company / bank settings from DB, falling back to defaults."""
    result = dict(INVOICE_SETTINGS_DEFAULTS)
    try:
        with get_db() as db:
            for key in INVOICE_SETTINGS_DEFAULTS:
                db.execute(
                    "SELECT setting_value FROM system_settings WHERE setting_key=%s",
                    (f"invoice_{key}",),
                )
                row = db.fetchone()
                if row and row["setting_value"]:
                    result[key] = row["setting_value"]
    except Exception:
        pass
    return result

# ── Email Provider Configuration ───────────────────────────────────────────
# Config is loaded from DB (admin UI) first, then falls back to env vars.
# This allows admins to configure email providers from the Settings page.

_config = {
    "email_provider": os.environ.get("EMAIL_PROVIDER", "").lower(),
    "sendgrid_api_key": os.environ.get("SENDGRID_API_KEY", ""),
    "mailgun_api_key": os.environ.get("MAILGUN_API_KEY", ""),
    "mailgun_domain": os.environ.get("MAILGUN_DOMAIN", ""),
    "resend_api_key": os.environ.get("RESEND_API_KEY", ""),
    "email_from_address": os.environ.get(
        "EMAIL_FROM_ADDRESS",
        os.environ.get("SENDGRID_FROM_EMAIL", "noreply@viperai.io"),
    ),
    "email_from_name": os.environ.get(
        "EMAIL_FROM_NAME",
        os.environ.get("SENDGRID_FROM_NAME", "Viper AI"),
    ),
}


def reload_email_config():
    """Reload email config from the database, falling back to env vars."""
    try:
        from app.routes.email_config import get_email_config_from_db
        db_cfg = get_email_config_from_db()
        for key in list(_config.keys()):
            db_val = db_cfg.get(key, "")
            if db_val:
                _config[key] = db_val
    except Exception as e:
        logger.debug(f"Could not load email config from DB (using env vars): {e}")


def _detect_provider() -> str:
    """Auto-detect which provider to use based on available API keys."""
    provider = _config["email_provider"]
    if provider in ("sendgrid", "mailgun", "resend"):
        return provider
    if _config["sendgrid_api_key"]:
        return "sendgrid"
    if _config["mailgun_api_key"] and _config["mailgun_domain"]:
        return "mailgun"
    if _config["resend_api_key"]:
        return "resend"
    return ""


def _provider_configured() -> bool:
    return bool(_detect_provider())


def get_active_provider_info() -> dict:
    """Get info about the currently active email provider (used by admin UI)."""
    reload_email_config()
    provider = _detect_provider()
    return {
        "provider": provider or None,
        "configured": bool(provider),
        "from_email": _config["email_from_address"],
        "from_name": _config["email_from_name"],
    }


# ── Default Templates ────────────────────────────────────────────────────────

DEFAULT_TEMPLATES = [
    {
        "template_key": "employment_verification_request",
        "name": "Employment Verification Request",
        "description": "Sent to a previous employer to verify a candidate's employment history.",
        "category": "verification",
        "subject": "{{agency_name}} — Please confirm {{candidate_name}}'s employment",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">{{agency_name}}</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Employment Verification Request via Viper AI</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{verifier_name}},</p>
    <p><strong>{{candidate_name}}</strong> should have notified you prior to this request.</p>
    <p>We are conducting a pre-employment compliance check on behalf of <strong>{{agency_name}}</strong> and would appreciate your assistance in verifying the following employment details.</p>
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px 0; color: #64748b; width: 40%;">Candidate:</td><td style="padding: 8px 0; font-weight: 600;">{{candidate_name}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Employer:</td><td style="padding: 8px 0; font-weight: 600;">{{employer_name}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Job Title:</td><td style="padding: 8px 0; font-weight: 600;">{{job_title}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Period:</td><td style="padding: 8px 0; font-weight: 600;">{{start_date}} — {{end_date}}</td></tr>
        </table>
    </div>
    <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 15px; margin: 20px 0; text-align: center;">
        <p style="margin: 0 0 5px; color: #1e40af; font-weight: 600;">Verification Code</p>
        <p style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: 3px; color: #1e3a5f;">{{verification_code}}</p>
        <p style="margin: 8px 0 0; color: #64748b; font-size: 13px;">Visit <strong>{{verification_url}}</strong> and enter this code to respond.<br>This avoids clicking any links — you type the address yourself.</p>
    </div>
    <p style="color: #64748b; font-size: 13px;">Alternatively, click the button below:</p>
    <div style="text-align: center; margin: 15px 0;">
        <a href="{{verification_link}}" style="background: #3b82f6; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Verify Employment</a>
    </div>
    <p style="color: #64748b; font-size: 12px;">If the button doesn't work, copy and paste this link: {{verification_link}}</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <div style="color: #64748b; font-size: 11px; line-height: 1.5;">
        <p style="margin: 0 0 8px;"><strong>Why am I receiving this%s</strong> {{agency_name}} is conducting pre-employment checks as required under the Conduct of Employment Agencies and Employment Businesses Regulations 2003.</p>
        <p style="margin: 0 0 8px;">Viper AI Ltd | {{company_reg_info}} | ICO Registration: {{ico_registration}} | To verify this request is genuine, call {{verification_phone}} or email {{verification_email}}</p>
        <p style="margin: 0;">We process personal data in accordance with UK GDPR. Your response will be retained for 6 years in line with regulatory requirements. See our privacy policy at {{privacy_url}}.</p>
    </div>
</div>
</div>""",
        "body_text": """{{agency_name}} — Employment Verification Request

Dear {{verifier_name}},

{{candidate_name}} should have notified you prior to this request.

We are conducting a pre-employment compliance check on behalf of {{agency_name}} and would appreciate your assistance in verifying the following employment details.

Candidate: {{candidate_name}}
Employer: {{employer_name}}
Job Title: {{job_title}}
Period: {{start_date}} — {{end_date}}

VERIFICATION CODE: {{verification_code}}
Visit {{verification_url}} and enter the code above to respond.
This avoids clicking any links — you type the address yourself.

Alternatively, visit this link:
{{verification_link}}

This should take approximately 2 minutes. The code will expire in 14 days.

---
This request is made under the Conduct of Employment Agencies and Employment Businesses Regulations 2003.
Viper AI Ltd | {{company_reg_info}} | ICO Registration: {{ico_registration}}
To verify this request is genuine, call {{verification_phone}} or email {{verification_email}}
Privacy policy: {{privacy_url}}

Best regards,
{{agency_name}} via Viper AI Compliance""",
        "variables": json.dumps([
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "verifier_name", "description": "Name of the employer/verifier"},
            {"key": "agency_name", "description": "Name of the hiring agency"},
            {"key": "employer_name", "description": "Name of the employer organisation"},
            {"key": "job_title", "description": "Job title to verify"},
            {"key": "start_date", "description": "Employment start date"},
            {"key": "end_date", "description": "Employment end date"},
            {"key": "verification_code", "description": "Short verification code (e.g. HV-7X9K-2M4P)"},
            {"key": "verification_url", "description": "Domain for manual code entry (e.g. verify.viperai.io)"},
            {"key": "verification_link", "description": "Direct link for the verifier to submit their response"},
            {"key": "company_reg_info", "description": "Company registration details"},
            {"key": "ico_registration", "description": "ICO registration number"},
            {"key": "verification_phone", "description": "Phone number to verify request authenticity"},
            {"key": "verification_email", "description": "Email to verify request authenticity"},
            {"key": "privacy_url", "description": "Link to privacy policy"},
        ]),
    },
    {
        "template_key": "reference_request",
        "name": "Reference Request",
        "description": "Sent to a referee to request a professional reference for a candidate.",
        "category": "verification",
        "subject": "{{agency_name}} — Professional reference for {{candidate_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">{{agency_name}}</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Professional Reference Request via Viper AI</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{referee_name}},</p>
    <p><strong>{{candidate_name}}</strong> should have notified you prior to this request.</p>
    <p>{{candidate_name}} has listed you as a professional referee as part of their compliance vetting with <strong>{{agency_name}}</strong>. We would be grateful if you could take a few minutes to complete a structured reference form covering their professional conduct, competency, and suitability.</p>
    <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 15px; margin: 20px 0; text-align: center;">
        <p style="margin: 0 0 5px; color: #1e40af; font-weight: 600;">Verification Code</p>
        <p style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: 3px; color: #1e3a5f;">{{verification_code}}</p>
        <p style="margin: 8px 0 0; color: #64748b; font-size: 13px;">Visit <strong>{{verification_url}}</strong> and enter this code to respond.<br>This avoids clicking any links — you type the address yourself.</p>
    </div>
    <p style="color: #64748b; font-size: 13px;">Alternatively, click the button below:</p>
    <div style="text-align: center; margin: 15px 0;">
        <a href="{{reference_link}}" style="background: #3b82f6; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Submit Reference</a>
    </div>
    <p style="color: #64748b; font-size: 12px;">If the button doesn't work, copy and paste this link: {{reference_link}}</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <div style="color: #64748b; font-size: 11px; line-height: 1.5;">
        <p style="margin: 0 0 8px;"><strong>Why am I receiving this?</strong> {{agency_name}} is conducting pre-employment checks as required under the Conduct of Employment Agencies and Employment Businesses Regulations 2003.</p>
        <p style="margin: 0 0 8px;">Viper AI Ltd | {{company_reg_info}} | ICO Registration: {{ico_registration}} | To verify this request is genuine, call {{verification_phone}} or email {{verification_email}}</p>
        <p style="margin: 0;">We process personal data in accordance with UK GDPR. Your response will be treated in confidence and retained for 6 years in line with regulatory requirements. See our privacy policy at {{privacy_url}}.</p>
    </div>
</div>
</div>""",
        "body_text": """{{agency_name}} — Professional Reference Request

Dear {{referee_name}},

{{candidate_name}} should have notified you prior to this request.

{{candidate_name}} has listed you as a professional referee as part of their compliance vetting with {{agency_name}}. We would be grateful if you could take a few minutes to complete a structured reference form.

VERIFICATION CODE: {{verification_code}}
Visit {{verification_url}} and enter the code above to respond.
This avoids clicking any links — you type the address yourself.

Alternatively, visit this link:
{{reference_link}}

Your response will be treated in confidence. The code will expire in 14 days.

---
This request is made under the Conduct of Employment Agencies and Employment Businesses Regulations 2003.
Viper AI Ltd | {{company_reg_info}} | ICO Registration: {{ico_registration}}
To verify this request is genuine, call {{verification_phone}} or email {{verification_email}}
Privacy policy: {{privacy_url}}

Best regards,
{{agency_name}} via Viper AI Compliance""",
        "variables": json.dumps([
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "referee_name", "description": "Name of the referee"},
            {"key": "agency_name", "description": "Name of the hiring agency"},
            {"key": "verification_code", "description": "Short verification code (e.g. HV-7X9K-2M4P)"},
            {"key": "verification_url", "description": "Domain for manual code entry (e.g. verify.viperai.io)"},
            {"key": "reference_link", "description": "Direct link for the referee to submit their reference"},
            {"key": "company_reg_info", "description": "Company registration details"},
            {"key": "ico_registration", "description": "ICO registration number"},
            {"key": "verification_phone", "description": "Phone number to verify request authenticity"},
            {"key": "verification_email", "description": "Email to verify request authenticity"},
            {"key": "privacy_url", "description": "Link to privacy policy"},
        ]),
    },
    {
        "template_key": "verification_reminder",
        "name": "Verification / Reference Reminder",
        "description": "Follow-up reminder sent when a verification or reference request has not been completed.",
        "category": "verification",
        "subject": "{{agency_name}} — Reminder: {{request_type}} for {{candidate_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">{{agency_name}}</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Friendly Reminder via Viper AI</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{recipient_name}},</p>
    <p>This is a friendly reminder regarding a pending <strong>{{request_type}}</strong> for <strong>{{candidate_name}}</strong> that was sent on {{original_sent_date}}.</p>
    <p>We understand you may be busy, but your response is important for the candidate's compliance process. This is reminder {{reminder_number}} of 3.</p>
    <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 15px; margin: 20px 0; text-align: center;">
        <p style="margin: 0 0 5px; color: #1e40af; font-weight: 600;">Your Verification Code</p>
        <p style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: 3px; color: #1e3a5f;">{{verification_code}}</p>
        <p style="margin: 8px 0 0; color: #64748b; font-size: 13px;">Visit <strong>{{verification_url}}</strong> and enter this code to respond.</p>
    </div>
    <p style="color: #64748b; font-size: 13px;">Alternatively, click the button below:</p>
    <div style="text-align: center; margin: 15px 0;">
        <a href="{{action_link}}" style="background: #f59e0b; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Complete Now</a>
    </div>
    <p style="color: #64748b; font-size: 12px;">If the button doesn't work, copy and paste this link: {{action_link}}</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <div style="color: #64748b; font-size: 11px; line-height: 1.5;">
        <p style="margin: 0 0 8px;">This request is made under the Conduct of Employment Agencies and Employment Businesses Regulations 2003.</p>
        <p style="margin: 0 0 8px;">Viper AI Ltd | {{company_reg_info}} | ICO Registration: {{ico_registration}} | To verify this request is genuine, call {{verification_phone}} or email {{verification_email}}</p>
        <p style="margin: 0;">Privacy policy: {{privacy_url}} | If you have already responded, please disregard this reminder.</p>
    </div>
</div>
</div>""",
        "body_text": """{{agency_name}} — Reminder: {{request_type}} for {{candidate_name}}

Dear {{recipient_name}},

This is a friendly reminder regarding a pending {{request_type}} for {{candidate_name}} that was sent on {{original_sent_date}}.

We understand you may be busy, but your response is important for the candidate's compliance process. This is reminder {{reminder_number}} of 3.

VERIFICATION CODE: {{verification_code}}
Visit {{verification_url}} and enter the code above to respond.

Alternatively, visit this link:
{{action_link}}

If you have already responded, please disregard this reminder.

---
This request is made under the Conduct of Employment Agencies and Employment Businesses Regulations 2003.
Viper AI Ltd | {{company_reg_info}} | ICO Registration: {{ico_registration}}
To verify this request is genuine, call {{verification_phone}} or email {{verification_email}}
Privacy policy: {{privacy_url}}

Best regards,
{{agency_name}} via Viper AI Compliance""",
        "variables": json.dumps([
            {"key": "recipient_name", "description": "Name of the verifier or referee"},
            {"key": "request_type", "description": "Type of request (e.g., Employment Verification, Reference)"},
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "agency_name", "description": "Name of the hiring agency"},
            {"key": "original_sent_date", "description": "Date the original request was sent"},
            {"key": "reminder_number", "description": "Which reminder this is (1, 2, or 3)"},
            {"key": "verification_code", "description": "Short verification code (e.g. HV-7X9K-2M4P)"},
            {"key": "verification_url", "description": "Domain for manual code entry"},
            {"key": "action_link", "description": "Direct link to complete the verification or reference"},
            {"key": "company_reg_info", "description": "Company registration details"},
            {"key": "ico_registration", "description": "ICO registration number"},
            {"key": "verification_phone", "description": "Phone number to verify request authenticity"},
            {"key": "verification_email", "description": "Email to verify request authenticity"},
            {"key": "privacy_url", "description": "Link to privacy policy"},
        ]),
    },
    {
        "template_key": "expiry_warning_agency",
        "name": "Expiry Warning (Agency)",
        "description": "Sent to an agency when candidate credentials are expiring soon.",
        "category": "compliance",
        "subject": "Credential Expiry Alert — {{expiry_count}} item(s) expiring soon",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">Viper AI</h1>
    <p style="color: #f59e0b; margin: 5px 0 0; font-size: 14px;">Credential Expiry Warning</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{agency_name}},</p>
    <p>The following credentials for your candidates are expiring soon and require attention:</p>
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0;">
        {{expiry_items_html}}
    </div>
    <p>Please log in to your dashboard to take appropriate action and ensure continued compliance.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{dashboard_link}}" style="background: #3b82f6; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">View Dashboard</a>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This is an automated compliance alert from Viper AI.</p>
</div>
</div>""",
        "body_text": """Credential Expiry Alert

Dear {{agency_name}},

The following credentials for your candidates are expiring soon:

{{expiry_items_text}}

Please log in to your dashboard to take appropriate action.

Dashboard: {{dashboard_link}}

Best regards,
Viper AI Compliance Team""",
        "variables": json.dumps([
            {"key": "agency_name", "description": "Name of the agency"},
            {"key": "expiry_count", "description": "Number of expiring items"},
            {"key": "expiry_items_html", "description": "HTML list of expiring credentials"},
            {"key": "expiry_items_text", "description": "Plain text list of expiring credentials"},
            {"key": "dashboard_link", "description": "Link to the agency dashboard"},
        ]),
    },
    {
        "template_key": "expiry_warning_candidate",
        "name": "Expiry Warning (Candidate)",
        "description": "Sent to a candidate when their credentials are expiring soon.",
        "category": "compliance",
        "subject": "Your {{credential_type}} expires in {{days_left}} days",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">Viper AI</h1>
    <p style="color: #f59e0b; margin: 5px 0 0; font-size: 14px;">Credential Expiry Warning</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{candidate_name}},</p>
    <p>Your <strong>{{credential_type}}</strong> is due to expire on <strong>{{expiry_date}}</strong> ({{days_left}} days from now).</p>
    <div style="background: #fef3c7; border: 1px solid #fbbf24; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e;"><strong>Action Required:</strong> Please renew this credential to maintain your compliance status and avoid disruption to your employment.</p>
    </div>
    <p>You can log in to your portal to view your full compliance status and update your details.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{portal_link}}" style="background: #3b82f6; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">View My Portal</a>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This is an automated compliance alert from Viper AI.</p>
</div>
</div>""",
        "body_text": """Credential Expiry Warning

Dear {{candidate_name}},

Your {{credential_type}} is due to expire on {{expiry_date}} ({{days_left}} days from now).

Action Required: Please renew this credential to maintain your compliance status.

Log in to your portal: {{portal_link}}

Best regards,
Viper AI Compliance Team""",
        "variables": json.dumps([
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "credential_type", "description": "Type of credential expiring"},
            {"key": "expiry_date", "description": "Expiry date"},
            {"key": "days_left", "description": "Number of days until expiry"},
            {"key": "portal_link", "description": "Link to the candidate portal"},
        ]),
    },
    {
        "template_key": "monitoring_alert_summary",
        "name": "Monitoring Alert Summary",
        "description": "Sent to agencies after automated monitoring detects new compliance issues.",
        "category": "compliance",
        "subject": "Monitoring Alert — {{alert_count}} new issue(s) detected",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">Viper AI</h1>
    <p style="color: #ef4444; margin: 5px 0 0; font-size: 14px;">Compliance Monitoring Alert</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{agency_name}},</p>
    <p>Our automated compliance monitoring has detected <strong>{{alert_count}} new issue(s)</strong> affecting your candidates:</p>
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0;">
        {{alert_items_html}}
    </div>
    <p>Please log in to your dashboard to review these alerts and take appropriate action.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{dashboard_link}}" style="background: #ef4444; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Review Alerts</a>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This is an automated monitoring alert from Viper AI.</p>
</div>
</div>""",
        "body_text": """Compliance Monitoring Alert

Dear {{agency_name}},

Our automated monitoring has detected {{alert_count}} new issue(s):

{{alert_items_text}}

Please log in to your dashboard to review these alerts.
Dashboard: {{dashboard_link}}

Best regards,
Viper AI Compliance Team""",
        "variables": json.dumps([
            {"key": "agency_name", "description": "Name of the agency"},
            {"key": "alert_count", "description": "Number of new alerts"},
            {"key": "alert_items_html", "description": "HTML list of alert details"},
            {"key": "alert_items_text", "description": "Plain text list of alert details"},
            {"key": "dashboard_link", "description": "Link to the agency dashboard"},
        ]),
    },
    {
        "template_key": "invoice_notification",
        "name": "Itemised Invoice",
        "description": "Professional itemised invoice sent to an agency with company details, line items, totals, and bank payment information.",
        "category": "billing",
        "subject": "Invoice #{{invoice_ref}} — {{total_due}} from {{company_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px; background: #f1f5f9;">
<div style="background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
    <!-- Header -->
    <div style="background: #1e293b; padding: 30px;">
        <table style="width: 100%;">
            <tr>
                <td style="vertical-align: top;">
                    <h1 style="color: #60a5fa; margin: 0; font-size: 28px;">INVOICE</h1>
                    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 13px;">#{{invoice_ref}}</p>
                </td>
                <td style="text-align: right; color: #94a3b8; font-size: 13px; vertical-align: top;">
                    <p style="margin: 0; color: white; font-weight: 600; font-size: 16px;">{{company_name}}</p>
                    <p style="margin: 4px 0 0;">{{company_address}}</p>
                    <p style="margin: 2px 0 0;">{{company_email}}</p>
                    <p style="margin: 2px 0 0;">{{company_phone}}</p>
                </td>
            </tr>
        </table>
    </div>

    <div style="padding: 30px;">
        <!-- Invoice Meta -->
        <table style="width: 100%; margin-bottom: 25px;">
            <tr>
                <td style="vertical-align: top; width: 50%;">
                    <p style="color: #64748b; font-size: 11px; text-transform: uppercase; margin: 0 0 5px;">Bill To</p>
                    <p style="margin: 0; font-weight: 600; font-size: 15px; color: #1e293b;">{{agency_name}}</p>
                    <p style="margin: 2px 0 0; color: #64748b; font-size: 13px;">{{agency_email}}</p>
                </td>
                <td style="vertical-align: top; text-align: right;">
                    <table style="margin-left: auto;">
                        <tr><td style="color: #64748b; font-size: 12px; padding: 2px 10px 2px 0;">Invoice Date:</td><td style="font-size: 12px; font-weight: 600;">{{invoice_date}}</td></tr>
                        <tr><td style="color: #64748b; font-size: 12px; padding: 2px 10px 2px 0;">Due Date:</td><td style="font-size: 12px; font-weight: 600;">{{due_date}}</td></tr>
                        <tr><td style="color: #64748b; font-size: 12px; padding: 2px 10px 2px 0;">Payment Terms:</td><td style="font-size: 12px; font-weight: 600;">{{payment_terms}}</td></tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Line Items Table -->
        <table style="width: 100%; border-collapse: collapse; margin-bottom: 20px;">
            <thead>
                <tr style="background: #f8fafc;">
                    <th style="text-align: left; padding: 10px; font-size: 11px; color: #64748b; text-transform: uppercase; border-bottom: 2px solid #e2e8f0;">Description</th>
                    <th style="text-align: left; padding: 10px; font-size: 11px; color: #64748b; text-transform: uppercase; border-bottom: 2px solid #e2e8f0;">Candidate</th>
                    <th style="text-align: right; padding: 10px; font-size: 11px; color: #64748b; text-transform: uppercase; border-bottom: 2px solid #e2e8f0;">Amount</th>
                </tr>
            </thead>
            <tbody>
                {{line_items_html}}
            </tbody>
        </table>

        <!-- Totals -->
        <table style="width: 100%; margin-bottom: 25px;">
            <tr>
                <td style="width: 60%;"></td>
                <td>
                    <table style="width: 100%; border-collapse: collapse;">
                        <tr><td style="padding: 6px 10px; color: #64748b; font-size: 13px;">Subtotal:</td><td style="padding: 6px 10px; text-align: right; font-size: 13px;">{{subtotal}}</td></tr>
                        <tr><td style="padding: 6px 10px; color: #64748b; font-size: 13px;">VAT ({{vat_rate}}):</td><td style="padding: 6px 10px; text-align: right; font-size: 13px;">{{vat_amount}}</td></tr>
                        <tr style="border-top: 2px solid #1e293b;"><td style="padding: 10px; font-weight: 700; font-size: 16px; color: #1e293b;">Total Due:</td><td style="padding: 10px; text-align: right; font-weight: 700; font-size: 16px; color: #1e293b;">{{total_due}}</td></tr>
                    </table>
                </td>
            </tr>
        </table>

        <!-- Bank Details -->
        <div style="background: #f0f9ff; border: 1px solid #bae6fd; border-radius: 6px; padding: 15px; margin-bottom: 20px;">
            <p style="margin: 0 0 8px; font-weight: 600; color: #0369a1; font-size: 13px;">Payment Details — Bank Transfer</p>
            <table style="width: 100%; font-size: 13px;">
                <tr><td style="padding: 3px 0; color: #64748b; width: 35%;">Account Name:</td><td style="padding: 3px 0; font-weight: 600;">{{bank_account_name}}</td></tr>
                <tr><td style="padding: 3px 0; color: #64748b;">Sort Code:</td><td style="padding: 3px 0; font-weight: 600;">{{bank_sort_code}}</td></tr>
                <tr><td style="padding: 3px 0; color: #64748b;">Account Number:</td><td style="padding: 3px 0; font-weight: 600;">{{bank_account_number}}</td></tr>
                <tr><td style="padding: 3px 0; color: #64748b;">Reference:</td><td style="padding: 3px 0; font-weight: 600;">#{{invoice_ref}}</td></tr>
            </table>
        </div>

        <!-- Company Registration -->
        <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
        <div style="color: #94a3b8; font-size: 11px; line-height: 1.6;">
            <p style="margin: 0;">{{company_name}} | {{company_reg_info}} | VAT No: {{vat_number}}</p>
            <p style="margin: 2px 0 0;">{{company_address}}</p>
            <p style="margin: 6px 0 0;">If you have any questions about this invoice, please contact {{company_email}} or call {{company_phone}}.</p>
        </div>
    </div>
</div>
</div>""",
        "body_text": """INVOICE #{{invoice_ref}}
From: {{company_name}}
Date: {{invoice_date}}
Due: {{due_date}}
Payment Terms: {{payment_terms}}

Bill To: {{agency_name}} ({{agency_email}})

LINE ITEMS
{{line_items_text}}

Subtotal: {{subtotal}}
VAT ({{vat_rate}}): {{vat_amount}}
TOTAL DUE: {{total_due}}

PAYMENT DETAILS — Bank Transfer
Account Name: {{bank_account_name}}
Sort Code: {{bank_sort_code}}
Account Number: {{bank_account_number}}
Reference: #{{invoice_ref}}

---
{{company_name}} | {{company_reg_info}} | VAT No: {{vat_number}}
{{company_address}}
Questions%s Contact {{company_email}} or call {{company_phone}}""",
        "variables": json.dumps([
            {"key": "invoice_ref", "description": "Invoice reference number"},
            {"key": "invoice_date", "description": "Date the invoice was issued"},
            {"key": "due_date", "description": "Payment due date"},
            {"key": "payment_terms", "description": "Payment terms (e.g. Net 30)"},
            {"key": "agency_name", "description": "Name of the agency being billed"},
            {"key": "agency_email", "description": "Agency email address"},
            {"key": "line_items_html", "description": "HTML table rows of invoice line items"},
            {"key": "line_items_text", "description": "Plain text list of invoice line items"},
            {"key": "subtotal", "description": "Subtotal before VAT"},
            {"key": "vat_rate", "description": "VAT rate percentage (e.g. 20%)"},
            {"key": "vat_amount", "description": "VAT amount"},
            {"key": "total_due", "description": "Total amount due including VAT"},
            {"key": "company_name", "description": "Your company name"},
            {"key": "company_address", "description": "Your company address"},
            {"key": "company_email", "description": "Your company email"},
            {"key": "company_phone", "description": "Your company phone"},
            {"key": "company_reg_info", "description": "Company registration info"},
            {"key": "vat_number", "description": "VAT registration number"},
            {"key": "bank_account_name", "description": "Bank account name"},
            {"key": "bank_sort_code", "description": "Bank sort code"},
            {"key": "bank_account_number", "description": "Bank account number"},
        ]),
    },
    {
        "template_key": "payment_reminder",
        "name": "Payment Reminder",
        "description": "Sent as a reminder for unpaid invoices.",
        "category": "billing",
        "subject": "{{urgency}}: Invoice #{{invoice_ref}} — Payment Due",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">Viper AI</h1>
    <p style="color: #f59e0b; margin: 5px 0 0; font-size: 14px;">Payment {{urgency}}</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{agency_name}},</p>
    {{urgency_message}}
    <p>We have an outstanding invoice that requires your attention:</p>
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px 0; color: #64748b; width: 40%;">Invoice:</td><td style="padding: 8px 0; font-weight: 600;">#{{invoice_ref}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Amount Due:</td><td style="padding: 8px 0; font-weight: 600; color: #ef4444;">{{amount}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Description:</td><td style="padding: 8px 0;">{{description}}</td></tr>
        </table>
    </div>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{payment_link}}" style="background: #f59e0b; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Pay Now</a>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This is an automated payment reminder from Viper AI.</p>
</div>
</div>""",
        "body_text": """Payment {{urgency}}: Invoice #{{invoice_ref}}

Dear {{agency_name}},

We have an outstanding invoice that requires your attention:

Invoice: #{{invoice_ref}}
Amount Due: {{amount}}
Description: {{description}}

Please log in to your dashboard to make payment:
{{payment_link}}

Best regards,
Viper AI Billing Team""",
        "variables": json.dumps([
            {"key": "agency_name", "description": "Name of the agency"},
            {"key": "invoice_ref", "description": "Invoice reference number"},
            {"key": "amount", "description": "Amount due"},
            {"key": "description", "description": "Invoice description"},
            {"key": "urgency", "description": "Urgency level (e.g., Reminder, Final Notice)"},
            {"key": "urgency_message", "description": "Optional urgency message HTML"},
            {"key": "payment_link", "description": "Link to pay the invoice"},
        ]),
    },
    {
        "template_key": "candidate_invite",
        "name": "Candidate Invitation",
        "description": "Sent to a candidate inviting them to register and complete their vetting.",
        "category": "onboarding",
        "subject": "You've been invited to complete your compliance vetting",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">Viper AI</h1>
    <p style="color: #22c55e; margin: 5px 0 0; font-size: 14px;">Compliance Vetting Invitation</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{candidate_name}},</p>
    <p><strong>{{agency_name}}</strong> has invited you to complete your pre-employment compliance vetting through Viper AI.</p>
    <p>This process includes identity verification, right to work checks, DBS screening, reference collection, and professional registration verification — all handled digitally for your convenience.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{invite_link}}" style="background: #22c55e; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Start Your Vetting</a>
    </div>
    <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <p style="margin: 0 0 10px; font-weight: 600; color: #166534;">What you'll need:</p>
        <ul style="margin: 0; padding-left: 20px; color: #166534;">
            <li>A valid photo ID (passport or driving licence)</li>
            <li>Your National Insurance number</li>
            <li>DBS certificate number (if you have one)</li>
            <li>Details of 2 professional referees</li>
            <li>Your CV or work history</li>
        </ul>
    </div>
    <p style="color: #64748b; font-size: 13px;">If the button doesn't work, copy and paste this link:<br>{{invite_link}}</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This invitation was sent by {{agency_name}} via Viper AI. If you were not expecting this, please disregard.</p>
</div>
</div>""",
        "body_text": """Compliance Vetting Invitation

Dear {{candidate_name}},

{{agency_name}} has invited you to complete your pre-employment compliance vetting through Viper AI.

Please visit the following link to start your vetting:
{{invite_link}}

What you'll need:
- A valid photo ID (passport or driving licence)
- Your National Insurance number
- DBS certificate number (if you have one)
- Details of 2 professional referees
- Your CV or work history

Best regards,
Viper AI""",
        "variables": json.dumps([
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "agency_name", "description": "Name of the inviting agency"},
            {"key": "invite_link", "description": "Unique registration/invite link"},
        ]),
    },
    {
        "template_key": "subscription_confirmation",
        "name": "Subscription / Credit Pack Confirmation",
        "description": "Sent to an agency after purchasing a credit pack or subscribing to a plan.",
        "category": "billing",
        "subject": "Credit Pack Confirmed — {{plan_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">Viper AI</h1>
    <p style="color: #22c55e; margin: 5px 0 0; font-size: 14px;">Purchase Confirmed</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{agency_name}},</p>
    <p>Thank you for your purchase! Your credit pack has been activated:</p>
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px 0; color: #64748b; width: 40%;">Plan:</td><td style="padding: 8px 0; font-weight: 600;">{{plan_name}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Credits:</td><td style="padding: 8px 0; font-weight: 600;">{{credits}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Amount Paid:</td><td style="padding: 8px 0; font-weight: 600;">{{amount}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Valid Until:</td><td style="padding: 8px 0;">{{expiry_date}}</td></tr>
        </table>
    </div>
    <p>Your credits are now available in your dashboard. Start vetting candidates today!</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{dashboard_link}}" style="background: #3b82f6; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Go to Dashboard</a>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">Thank you for choosing Viper AI.</p>
</div>
</div>""",
        "body_text": """Credit Pack Confirmed — {{plan_name}}

Dear {{agency_name}},

Thank you for your purchase! Your credit pack has been activated:

Plan: {{plan_name}}
Credits: {{credits}}
Amount Paid: {{amount}}
Valid Until: {{expiry_date}}

Your credits are now available in your dashboard.

Dashboard: {{dashboard_link}}

Best regards,
Viper AI Team""",
        "variables": json.dumps([
            {"key": "agency_name", "description": "Name of the agency"},
            {"key": "plan_name", "description": "Credit pack/plan name"},
            {"key": "credits", "description": "Number of credits purchased"},
            {"key": "amount", "description": "Amount paid"},
            {"key": "expiry_date", "description": "Credit expiry date"},
            {"key": "dashboard_link", "description": "Link to the agency dashboard"},
        ]),
    },
    {
        "template_key": "imposter_check_required",
        "name": "Imposter Declaration Required",
        "description": "Sent to agency when a candidate's RTW check completes and an imposter declaration is needed.",
        "category": "compliance",
        "subject": "Imposter Declaration Required — {{candidate_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #f59e0b; margin: 0; font-size: 24px;">Action Required</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Imposter Declaration — Viper AI</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{agency_name}},</p>
    <p>The Right to Work check for <strong>{{candidate_name}}</strong> has been completed. Before RTW compliance can be confirmed, an <strong>imposter declaration</strong> is required.</p>
    <div style="background: #fffbeb; border: 1px solid #f59e0b; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <p style="margin: 0; color: #92400e; font-weight: 600;">What you need to do:</p>
        <ol style="color: #92400e; margin: 10px 0 0; padding-left: 20px;">
            <li>Conduct an in-person or compliant video identity check with the candidate</li>
            <li>Verify the individual matches the documentation provided</li>
            <li>Log in to your dashboard and submit the imposter declaration</li>
        </ol>
    </div>
    <div style="text-align: center; margin: 20px 0;">
        <a href="{{imposter_check_link}}" style="background: #f59e0b; color: #1e293b; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Complete Imposter Declaration</a>
    </div>
    <p style="color: #64748b; font-size: 13px;">This declaration is a legal requirement under UK Right to Work regulations. RTW compliance cannot be confirmed without it.</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 11px;">Viper AI — Vetting Intelligence Platform for Enterprise Risk</p>
</div>
</div>""",
        "body_text": """Imposter Declaration Required — {{candidate_name}}

Dear {{agency_name}},

The Right to Work check for {{candidate_name}} has been completed. Before RTW compliance can be confirmed, an imposter declaration is required.

What you need to do:
1. Conduct an in-person or compliant video identity check with the candidate
2. Verify the individual matches the documentation provided
3. Log in to your dashboard and submit the imposter declaration

Complete the declaration here: {{imposter_check_link}}

This declaration is a legal requirement under UK Right to Work regulations.

Best regards,
Viper AI Team""",
        "variables": json.dumps([
            {"key": "agency_name", "description": "Name of the agency"},
            {"key": "candidate_name", "description": "Name of the candidate"},
            {"key": "candidate_id", "description": "Candidate ID"},
            {"key": "imposter_check_link", "description": "Direct link to complete the imposter declaration"},
        ]),
    },
]


class EmailTemplateService:
    """Manage email templates and send emails via SendGrid."""

    # ── Template CRUD ─────────────────────────────────────────────────

    @staticmethod
    def seed_defaults():
        """Insert default templates if they don't exist, or update if content changed."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            for tpl in DEFAULT_TEMPLATES:
                db.execute(
                    "SELECT id, subject, body_html FROM email_templates WHERE template_key=%s",
                    (tpl["template_key"],),
                )
                existing = db.fetchone()
                if not existing:
                    db.execute(
                        """INSERT INTO email_templates
                           (id, template_key, name, description, subject,
                            body_html, body_text, category, variables, is_active)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1)""",
                        (
                            generate_id(),
                            tpl["template_key"],
                            tpl["name"],
                            tpl["description"],
                            tpl["subject"],
                            tpl["body_html"],
                            tpl.get("body_text", ""),
                            tpl.get("category", "general"),
                            tpl.get("variables", "[]"),
                        ),
                    )
                else:
                    # Update existing default templates if the code version has changed
                    ex = dict(existing)
                    if ex["subject"] != tpl["subject"] or ex["body_html"] != tpl["body_html"]:
                        db.execute(
                            """UPDATE email_templates SET
                               subject=%s, body_html=%s, body_text=%s, variables=%s,
                               description=%s, updated_at=%s
                               WHERE template_key=%s""",
                            (
                                tpl["subject"],
                                tpl["body_html"],
                                tpl.get("body_text", ""),
                                tpl.get("variables", "[]"),
                                tpl["description"],
                                now,
                                tpl["template_key"],
                            ),
                        )
                        logger.info(f"Updated default template: {tpl['template_key']}")

    @staticmethod
    def get_all_templates() -> list:
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_templates ORDER BY category, name"
            )
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_template(template_id: str) -> dict:
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_templates WHERE id=%s", (template_id,)
            )
            row = db.fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_template_by_key(template_key: str) -> dict:
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_templates WHERE template_key=%s", (template_key,)
            )
            row = db.fetchone()
            return dict(row) if row else None

    @staticmethod
    def update_template(
        template_id: str,
        name: str = None,
        description: str = None,
        subject: str = None,
        body_html: str = None,
        body_text: str = None,
        is_active: bool = None,
    ) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_templates WHERE id=%s", (template_id,)
            )
            row = db.fetchone()
            if not row:
                return None
            current = dict(row)

            db.execute(
                """UPDATE email_templates SET
                   name=%s, description=%s, subject=%s, body_html=%s, body_text=%s,
                   is_active=%s, updated_at=%s
                   WHERE id=%s""",
                (
                    name if name is not None else current["name"],
                    description if description is not None else current["description"],
                    subject if subject is not None else current["subject"],
                    body_html if body_html is not None else current["body_html"],
                    body_text if body_text is not None else current["body_text"],
                    (1 if is_active else 0) if is_active is not None else current["is_active"],
                    now,
                    template_id,
                ),
            )
            db.execute(
                "SELECT * FROM email_templates WHERE id=%s", (template_id,)
            )
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def reset_template(template_id: str) -> dict:
        """Reset a template to its default content."""
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_templates WHERE id=%s", (template_id,)
            )
            row = db.fetchone()
            if not row:
                return None
            current = dict(row)
            template_key = current["template_key"]

            # Find the default
            default = next(
                (t for t in DEFAULT_TEMPLATES if t["template_key"] == template_key),
                None,
            )
            if not default:
                return current  # No default to reset to

            now = datetime.now(timezone.utc).isoformat()
            db.execute(
                """UPDATE email_templates SET
                   subject=%s, body_html=%s, body_text=%s, updated_at=%s
                   WHERE id=%s""",
                (
                    default["subject"],
                    default["body_html"],
                    default.get("body_text", ""),
                    now,
                    template_id,
                ),
            )
            db.execute(
                "SELECT * FROM email_templates WHERE id=%s", (template_id,)
            )
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def create_template(
        template_key: str,
        name: str,
        description: str = "",
        subject: str = "",
        body_html: str = "",
        body_text: str = "",
        category: str = "general",
        variables: list = None,
    ) -> dict:
        """Create a new custom email template."""
        # Check for duplicate key
        existing = EmailTemplateService.get_template_by_key(template_key)
        if existing:
            return None  # duplicate key

        template_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        vars_json = json.dumps(variables or [])

        with get_db() as db:
            db.execute(
                """INSERT INTO email_templates
                   (id, template_key, name, description, subject, body_html, body_text,
                    category, variables, is_active, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s)""",
                (
                    template_id, template_key, name, description,
                    subject, body_html, body_text, category,
                    vars_json, now, now,
                ),
            )
            db.execute(
                "SELECT * FROM email_templates WHERE id=%s", (template_id,)
            )
            row = db.fetchone()
            return dict(row)

    @staticmethod
    def delete_template(template_id: str) -> bool:
        """Delete a custom email template. Returns False if template is a default (protected)."""
        with get_db() as db:
            db.execute(
                "SELECT * FROM email_templates WHERE id=%s", (template_id,)
            )
            row = db.fetchone()
            if not row:
                return None  # not found

            tpl = dict(row)
            # Protect default templates from deletion
            is_default = any(
                d["template_key"] == tpl["template_key"] for d in DEFAULT_TEMPLATES
            )
            if is_default:
                return False  # protected

            db.execute("DELETE FROM email_templates WHERE id=%s", (template_id,))
            return True

    # ── Rendering ─────────────────────────────────────────────────────

    @staticmethod
    def render_template(template_key: str, variables: dict) -> dict:
        """Render a template with variable substitution. Returns {subject, body_html, body_text}."""
        tpl = EmailTemplateService.get_template_by_key(template_key)
        if not tpl:
            return None

        subject = tpl["subject"]
        body_html = tpl["body_html"]
        body_text = tpl.get("body_text", "")

        # Replace {{variable}} placeholders
        for key, value in variables.items():
            placeholder = "{{" + key + "}}"
            str_value = str(value) if value is not None else ""
            subject = subject.replace(placeholder, str_value)
            body_html = body_html.replace(placeholder, str_value)
            body_text = body_text.replace(placeholder, str_value)

        return {
            "subject": subject,
            "body_html": body_html,
            "body_text": body_text,
        }

    @staticmethod
    def preview_template(template_id: str) -> dict:
        """Preview a template with sample data."""
        tpl = EmailTemplateService.get_template(template_id)
        if not tpl:
            return None

        # Generate sample variables
        sample_vars = {}
        try:
            var_list = json.loads(tpl.get("variables", "[]"))
            for var in var_list:
                key = var["key"]
                sample_vars[key] = f"[{var.get('description', key)}]"
        except (json.JSONDecodeError, TypeError):
            pass

        rendered = EmailTemplateService.render_template(tpl["template_key"], sample_vars)
        return {
            "template": tpl,
            "sample_variables": sample_vars,
            "rendered": rendered,
        }

    # ── Sending ───────────────────────────────────────────────────────

    @staticmethod
    def send_email(
        template_key: str,
        recipient_email: str,
        recipient_name: str,
        variables: dict,
        attachments: list = None,
    ) -> dict:
        """Render and send an email using SendGrid (or log if no API key).
        attachments: list of dicts with keys: filename, content (base64), type (mime type)
        """
        reload_email_config()  # ensure DB-stored API keys are loaded
        rendered = EmailTemplateService.render_template(template_key, variables)
        if not rendered:
            logger.error(f"Template not found: {template_key}")
            return {"status": "error", "message": "Template not found"}

        log_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()

        # Always log the email
        with get_db() as db:
            db.execute(
                """INSERT INTO email_send_log
                   (id, template_key, recipient_email, recipient_name, subject,
                    body_rendered, status, variables_used, created_at)
                   VALUES (%s, %s, %s, %s, %s, %s, 'queued', %s, %s)""",
                (
                    log_id, template_key, recipient_email, recipient_name,
                    rendered["subject"], rendered["body_html"],
                    json.dumps(variables), now,
                ),
            )

        # Attempt delivery via configured provider
        provider = _detect_provider()
        if provider:
            try:
                send_fn = {
                    "sendgrid": EmailTemplateService._send_via_sendgrid,
                    "mailgun": EmailTemplateService._send_via_mailgun,
                    "resend": EmailTemplateService._send_via_resend,
                }[provider]
                result = send_fn(
                    recipient_email, recipient_name,
                    rendered["subject"], rendered["body_html"], rendered["body_text"],
                    attachments=attachments,
                )
                with get_db() as db:
                    db.execute(
                        """UPDATE email_send_log SET
                           status='sent', provider=%s, provider_message_id=%s, sent_at=%s
                           WHERE id=%s""",
                        (provider, result.get("message_id", ""), now, log_id),
                    )
                logger.info(f"Email sent via {provider} to {recipient_email}: {rendered['subject']}")
                return {"status": "sent", "log_id": log_id, "provider": provider, "message_id": result.get("message_id")}
            except Exception as e:
                error_msg = str(e)
                with get_db() as db:
                    db.execute(
                        "UPDATE email_send_log SET status='failed', provider=%s, error_message=%s WHERE id=%s",
                        (provider, error_msg, log_id),
                    )
                logger.error(f"{provider} delivery failed: {error_msg}")
                return {"status": "failed", "log_id": log_id, "provider": provider, "error": error_msg}
        else:
            # No provider configured — store as logged only
            with get_db() as db:
                db.execute(
                    "UPDATE email_send_log SET status='logged', sent_at=%s WHERE id=%s",
                    (now, log_id),
                )

            # Also store in legacy email_notifications table for backward compatibility
            with get_db() as db:
                db.execute(
                    """INSERT INTO email_notifications
                       (id, recipient_email, recipient_name, subject, body,
                        notification_type, status, created_at)
                       VALUES (%s, %s, %s, %s, %s, %s, 'sent', %s)""",
                    (
                        generate_id(), recipient_email, recipient_name,
                        rendered["subject"], rendered["body_text"] or rendered["body_html"],
                        template_key, now,
                    ),
                )

            logger.info(f"Email logged (no SendGrid key) to {recipient_email}: {rendered['subject']}")
            return {"status": "logged", "log_id": log_id}

    @staticmethod
    def _send_via_sendgrid(
        to_email: str, to_name: str,
        subject: str, html_content: str, text_content: str,
        attachments: list = None,
    ) -> dict:
        """Send email via SendGrid API with optional attachments."""
        import httpx

        payload = {
            "personalizations": [{
                "to": [{"email": to_email, "name": to_name}],
            }],
            "from": {
                "email": _config["email_from_address"],
                "name": _config["email_from_name"],
            },
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content or subject},
                {"type": "text/html", "value": html_content},
            ],
        }

        if attachments:
            payload["attachments"] = [
                {
                    "content": att["content"],
                    "filename": att["filename"],
                    "type": att.get("type", "application/pdf"),
                    "disposition": "attachment",
                }
                for att in attachments
            ]

        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {_config['sendgrid_api_key']}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=30,
        )

        if response.status_code in (200, 201, 202):
            message_id = response.headers.get("X-Message-Id", "")
            return {"message_id": message_id}
        else:
            raise Exception(f"SendGrid API error {response.status_code}: {response.text}")

    @staticmethod
    def _send_via_mailgun(
        to_email: str, to_name: str,
        subject: str, html_content: str, text_content: str,
        attachments: list = None,
    ) -> dict:
        """Send email via Mailgun API."""
        import httpx

        response = httpx.post(
            f"https://api.mailgun.net/v3/{_config['mailgun_domain']}/messages",
            auth=("api", _config["mailgun_api_key"]),
            data={
                "from": f"{_config['email_from_name']} <{_config['email_from_address']}>",
                "to": [f"{to_name} <{to_email}>"],
                "subject": subject,
                "text": text_content or subject,
                "html": html_content,
            },
            timeout=10,
        )

        if response.status_code == 200:
            data = response.json()
            return {"message_id": data.get("id", "")}
        else:
            raise Exception(f"Mailgun API error {response.status_code}: {response.text}")

    @staticmethod
    def _send_via_resend(
        to_email: str, to_name: str,
        subject: str, html_content: str, text_content: str,
        attachments: list = None,
    ) -> dict:
        """Send email via Resend API."""
        import httpx

        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {_config['resend_api_key']}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{_config['email_from_name']} <{_config['email_from_address']}>",
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "text": text_content or subject,
            },
            timeout=10,
        )

        if response.status_code in (200, 201):
            data = response.json()
            return {"message_id": data.get("id", "")}
        else:
            raise Exception(f"Resend API error {response.status_code}: {response.text}")

    # ── Send Log ──────────────────────────────────────────────────────

    @staticmethod
    def get_send_log(limit: int = 50, template_key: str = None) -> list:
        with get_db() as db:
            query = "SELECT * FROM email_send_log"
            params = []
            if template_key:
                query += " WHERE template_key=%s"
                params.append(template_key)
            query += " ORDER BY created_at DESC LIMIT %s"
            params.append(limit)
            db.execute(query, params)
            rows = db.fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_email_stats() -> dict:
        """Get email delivery statistics."""
        reload_email_config()  # ensure DB config is loaded
        with get_db() as db:
            db.execute("SELECT COUNT(*) as cnt FROM email_send_log")
            total = db.fetchone()
            db.execute("SELECT COUNT(*) as cnt FROM email_send_log WHERE status='sent'")
            sent = db.fetchone()
            db.execute("SELECT COUNT(*) as cnt FROM email_send_log WHERE status='logged'")
            logged = db.fetchone()
            db.execute("SELECT COUNT(*) as cnt FROM email_send_log WHERE status='failed'")
            failed = db.fetchone()
            provider = _detect_provider()
            configured = bool(provider)
            return {
                "total": dict(total)["cnt"] if total else 0,
                "sent": dict(sent)["cnt"] if sent else 0,
                "logged": dict(logged)["cnt"] if logged else 0,
                "failed": dict(failed)["cnt"] if failed else 0,
                "provider": provider or None,
                "provider_configured": configured,
                "sendgrid_configured": configured,
            }
