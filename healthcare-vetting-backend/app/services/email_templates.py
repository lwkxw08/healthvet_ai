"""
Email Template Management Service
Stores, retrieves, and renders email templates with variable substitution.
Supports multiple email providers: SendGrid, Mailgun, and Resend.
"""
import json
import logging
import os
import re
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)

# ── Email Provider Configuration ───────────────────────────────────────────
# Set EMAIL_PROVIDER to choose: "sendgrid", "mailgun", or "resend"
# Falls back to auto-detect based on which API key is present.
EMAIL_PROVIDER = os.environ.get("EMAIL_PROVIDER", "").lower()

# SendGrid
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")

# Mailgun
MAILGUN_API_KEY = os.environ.get("MAILGUN_API_KEY", "")
MAILGUN_DOMAIN = os.environ.get("MAILGUN_DOMAIN", "")  # e.g. mg.healthvet.ai

# Resend
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")

# Shared sender config
FROM_EMAIL = os.environ.get("EMAIL_FROM_ADDRESS", os.environ.get("SENDGRID_FROM_EMAIL", "noreply@healthvet.ai"))
FROM_NAME = os.environ.get("EMAIL_FROM_NAME", os.environ.get("SENDGRID_FROM_NAME", "HealthVet AI"))


def _detect_provider() -> str:
    """Auto-detect which provider to use based on available API keys."""
    if EMAIL_PROVIDER in ("sendgrid", "mailgun", "resend"):
        return EMAIL_PROVIDER
    if SENDGRID_API_KEY:
        return "sendgrid"
    if MAILGUN_API_KEY and MAILGUN_DOMAIN:
        return "mailgun"
    if RESEND_API_KEY:
        return "resend"
    return ""


def _provider_configured() -> bool:
    return bool(_detect_provider())


# ── Default Templates ────────────────────────────────────────────────────────

DEFAULT_TEMPLATES = [
    {
        "template_key": "employment_verification_request",
        "name": "Employment Verification Request",
        "description": "Sent to a previous employer to verify a candidate's employment history.",
        "category": "verification",
        "subject": "Employment Verification Request — {{candidate_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Employment Verification Request</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{verifier_name}},</p>
    <p>We are conducting a pre-employment compliance check on behalf of <strong>{{agency_name}}</strong> and would appreciate your assistance in verifying the following employment details for <strong>{{candidate_name}}</strong>.</p>
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px 0; color: #64748b; width: 40%;">Candidate:</td><td style="padding: 8px 0; font-weight: 600;">{{candidate_name}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Employer:</td><td style="padding: 8px 0; font-weight: 600;">{{employer_name}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Job Title:</td><td style="padding: 8px 0; font-weight: 600;">{{job_title}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Period:</td><td style="padding: 8px 0; font-weight: 600;">{{start_date}} — {{end_date}}</td></tr>
        </table>
    </div>
    <p>Please click the button below to confirm or dispute these details. This should take approximately 2 minutes.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{verification_link}}" style="background: #3b82f6; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Verify Employment</a>
    </div>
    <p style="color: #64748b; font-size: 13px;">If the button doesn't work, copy and paste this link into your browser:<br>{{verification_link}}</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This is an automated request from HealthVet AI, a healthcare compliance platform. If you believe you received this in error, please disregard this email. This link will expire in 14 days.</p>
</div>
</div>""",
        "body_text": """Employment Verification Request

Dear {{verifier_name}},

We are conducting a pre-employment compliance check on behalf of {{agency_name}} and would appreciate your assistance in verifying the following employment details for {{candidate_name}}.

Candidate: {{candidate_name}}
Employer: {{employer_name}}
Job Title: {{job_title}}
Period: {{start_date}} — {{end_date}}

Please visit the following link to confirm or dispute these details:
{{verification_link}}

This should take approximately 2 minutes. The link will expire in 14 days.

Best regards,
HealthVet AI Compliance Team""",
        "variables": json.dumps([
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "verifier_name", "description": "Name of the employer/verifier"},
            {"key": "agency_name", "description": "Name of the hiring agency"},
            {"key": "employer_name", "description": "Name of the employer organisation"},
            {"key": "job_title", "description": "Job title to verify"},
            {"key": "start_date", "description": "Employment start date"},
            {"key": "end_date", "description": "Employment end date"},
            {"key": "verification_link", "description": "Unique link for the verifier to submit their response"},
        ]),
    },
    {
        "template_key": "reference_request",
        "name": "Reference Request",
        "description": "Sent to a referee to request a professional reference for a candidate.",
        "category": "verification",
        "subject": "Reference Request — {{candidate_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Professional Reference Request</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{referee_name}},</p>
    <p><strong>{{candidate_name}}</strong> has listed you as a professional referee as part of their compliance vetting with <strong>{{agency_name}}</strong>.</p>
    <p>We would be grateful if you could take a few minutes to complete a structured reference form covering their professional conduct, competency, and suitability for healthcare roles.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{reference_link}}" style="background: #3b82f6; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Submit Reference</a>
    </div>
    <p style="color: #64748b; font-size: 13px;">If the button doesn't work, copy and paste this link into your browser:<br>{{reference_link}}</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This is an automated request from HealthVet AI. Your response will be treated in confidence. This link will expire in 14 days.</p>
</div>
</div>""",
        "body_text": """Reference Request

Dear {{referee_name}},

{{candidate_name}} has listed you as a professional referee as part of their compliance vetting with {{agency_name}}.

We would be grateful if you could take a few minutes to complete a structured reference form covering their professional conduct, competency, and suitability for healthcare roles.

Please visit the following link to submit your reference:
{{reference_link}}

Your response will be treated in confidence. This link will expire in 14 days.

Best regards,
HealthVet AI Compliance Team""",
        "variables": json.dumps([
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "referee_name", "description": "Name of the referee"},
            {"key": "agency_name", "description": "Name of the hiring agency"},
            {"key": "reference_link", "description": "Unique link for the referee to submit their reference"},
        ]),
    },
    {
        "template_key": "verification_reminder",
        "name": "Verification / Reference Reminder",
        "description": "Follow-up reminder sent when a verification or reference request has not been completed.",
        "category": "verification",
        "subject": "Reminder: {{request_type}} for {{candidate_name}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Friendly Reminder</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{recipient_name}},</p>
    <p>This is a friendly reminder regarding a pending <strong>{{request_type}}</strong> for <strong>{{candidate_name}}</strong> that was sent on {{original_sent_date}}.</p>
    <p>We understand you may be busy, but your response is important for the candidate's compliance process. This is reminder {{reminder_number}} of 3.</p>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{action_link}}" style="background: #f59e0b; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Complete Now</a>
    </div>
    <p style="color: #64748b; font-size: 13px;">If the button doesn't work, copy and paste this link into your browser:<br>{{action_link}}</p>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">If you have already responded, please disregard this reminder.</p>
</div>
</div>""",
        "body_text": """Reminder: {{request_type}} for {{candidate_name}}

Dear {{recipient_name}},

This is a friendly reminder regarding a pending {{request_type}} for {{candidate_name}} that was sent on {{original_sent_date}}.

We understand you may be busy, but your response is important for the candidate's compliance process. This is reminder {{reminder_number}} of 3.

Please visit the following link to complete your response:
{{action_link}}

If you have already responded, please disregard this reminder.

Best regards,
HealthVet AI Compliance Team""",
        "variables": json.dumps([
            {"key": "recipient_name", "description": "Name of the verifier or referee"},
            {"key": "request_type", "description": "Type of request (e.g., Employment Verification, Reference)"},
            {"key": "candidate_name", "description": "Full name of the candidate"},
            {"key": "original_sent_date", "description": "Date the original request was sent"},
            {"key": "reminder_number", "description": "Which reminder this is (1, 2, or 3)"},
            {"key": "action_link", "description": "Link to complete the verification or reference"},
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
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
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
    <p style="color: #64748b; font-size: 12px;">This is an automated compliance alert from HealthVet AI.</p>
</div>
</div>""",
        "body_text": """Credential Expiry Alert

Dear {{agency_name}},

The following credentials for your candidates are expiring soon:

{{expiry_items_text}}

Please log in to your dashboard to take appropriate action.

Dashboard: {{dashboard_link}}

Best regards,
HealthVet AI Compliance Team""",
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
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
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
    <p style="color: #64748b; font-size: 12px;">This is an automated compliance alert from HealthVet AI.</p>
</div>
</div>""",
        "body_text": """Credential Expiry Warning

Dear {{candidate_name}},

Your {{credential_type}} is due to expire on {{expiry_date}} ({{days_left}} days from now).

Action Required: Please renew this credential to maintain your compliance status.

Log in to your portal: {{portal_link}}

Best regards,
HealthVet AI Compliance Team""",
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
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
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
    <p style="color: #64748b; font-size: 12px;">This is an automated monitoring alert from HealthVet AI.</p>
</div>
</div>""",
        "body_text": """Compliance Monitoring Alert

Dear {{agency_name}},

Our automated monitoring has detected {{alert_count}} new issue(s):

{{alert_items_text}}

Please log in to your dashboard to review these alerts.
Dashboard: {{dashboard_link}}

Best regards,
HealthVet AI Compliance Team""",
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
        "name": "Invoice Notification",
        "description": "Sent to an agency when a new invoice is generated.",
        "category": "billing",
        "subject": "New Invoice #{{invoice_ref}} — {{amount}}",
        "body_html": """<div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
<div style="background: #1e293b; padding: 20px; border-radius: 8px 8px 0 0; text-align: center;">
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
    <p style="color: #94a3b8; margin: 5px 0 0; font-size: 14px;">Invoice Notification</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{agency_name}},</p>
    <p>A new invoice has been generated for your account:</p>
    <div style="background: white; border: 1px solid #e2e8f0; border-radius: 6px; padding: 15px; margin: 20px 0;">
        <table style="width: 100%; border-collapse: collapse;">
            <tr><td style="padding: 8px 0; color: #64748b; width: 40%;">Invoice Reference:</td><td style="padding: 8px 0; font-weight: 600;">#{{invoice_ref}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Amount Due:</td><td style="padding: 8px 0; font-weight: 600; font-size: 18px; color: #1e293b;">{{amount}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Description:</td><td style="padding: 8px 0;">{{description}}</td></tr>
            <tr><td style="padding: 8px 0; color: #64748b;">Date:</td><td style="padding: 8px 0;">{{invoice_date}}</td></tr>
        </table>
    </div>
    <div style="text-align: center; margin: 25px 0;">
        <a href="{{payment_link}}" style="background: #22c55e; color: white; padding: 12px 30px; border-radius: 6px; text-decoration: none; font-weight: 600; display: inline-block;">Pay Now</a>
    </div>
    <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;">
    <p style="color: #64748b; font-size: 12px;">This is an automated invoice from HealthVet AI.</p>
</div>
</div>""",
        "body_text": """Invoice Notification

Dear {{agency_name}},

A new invoice has been generated:

Invoice Reference: #{{invoice_ref}}
Amount Due: {{amount}}
Description: {{description}}
Date: {{invoice_date}}

Please log in to your dashboard to view and pay this invoice:
{{payment_link}}

Best regards,
HealthVet AI Billing Team""",
        "variables": json.dumps([
            {"key": "agency_name", "description": "Name of the agency"},
            {"key": "invoice_ref", "description": "Invoice reference number"},
            {"key": "amount", "description": "Invoice amount (e.g., \u00a3150.00)"},
            {"key": "description", "description": "Invoice description"},
            {"key": "invoice_date", "description": "Date of the invoice"},
            {"key": "payment_link", "description": "Link to pay the invoice"},
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
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
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
    <p style="color: #64748b; font-size: 12px;">This is an automated payment reminder from HealthVet AI.</p>
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
HealthVet AI Billing Team""",
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
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
    <p style="color: #22c55e; margin: 5px 0 0; font-size: 14px;">Compliance Vetting Invitation</p>
</div>
<div style="background: #f8fafc; padding: 30px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
    <p>Dear {{candidate_name}},</p>
    <p><strong>{{agency_name}}</strong> has invited you to complete your pre-employment compliance vetting through HealthVet AI.</p>
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
    <p style="color: #64748b; font-size: 12px;">This invitation was sent by {{agency_name}} via HealthVet AI. If you were not expecting this, please disregard.</p>
</div>
</div>""",
        "body_text": """Compliance Vetting Invitation

Dear {{candidate_name}},

{{agency_name}} has invited you to complete your pre-employment compliance vetting through HealthVet AI.

Please visit the following link to start your vetting:
{{invite_link}}

What you'll need:
- A valid photo ID (passport or driving licence)
- Your National Insurance number
- DBS certificate number (if you have one)
- Details of 2 professional referees
- Your CV or work history

Best regards,
HealthVet AI""",
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
    <h1 style="color: #60a5fa; margin: 0; font-size: 24px;">HealthVet AI</h1>
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
    <p style="color: #64748b; font-size: 12px;">Thank you for choosing HealthVet AI.</p>
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
HealthVet AI Team""",
        "variables": json.dumps([
            {"key": "agency_name", "description": "Name of the agency"},
            {"key": "plan_name", "description": "Credit pack/plan name"},
            {"key": "credits", "description": "Number of credits purchased"},
            {"key": "amount", "description": "Amount paid"},
            {"key": "expiry_date", "description": "Credit expiry date"},
            {"key": "dashboard_link", "description": "Link to the agency dashboard"},
        ]),
    },
]


class EmailTemplateService:
    """Manage email templates and send emails via SendGrid."""

    # ── Template CRUD ─────────────────────────────────────────────────

    @staticmethod
    def seed_defaults():
        """Insert default templates if they don't exist."""
        with get_db() as db:
            for tpl in DEFAULT_TEMPLATES:
                existing = db.execute(
                    "SELECT id FROM email_templates WHERE template_key=?",
                    (tpl["template_key"],),
                ).fetchone()
                if not existing:
                    db.execute(
                        """INSERT INTO email_templates
                           (id, template_key, name, description, subject,
                            body_html, body_text, category, variables, is_active)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1)""",
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

    @staticmethod
    def get_all_templates() -> list:
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM email_templates ORDER BY category, name"
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_template(template_id: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM email_templates WHERE id=?", (template_id,)
            ).fetchone()
            return dict(row) if row else None

    @staticmethod
    def get_template_by_key(template_key: str) -> dict:
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM email_templates WHERE template_key=?", (template_key,)
            ).fetchone()
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
            row = db.execute(
                "SELECT * FROM email_templates WHERE id=?", (template_id,)
            ).fetchone()
            if not row:
                return None
            current = dict(row)

            db.execute(
                """UPDATE email_templates SET
                   name=?, description=?, subject=?, body_html=?, body_text=?,
                   is_active=?, updated_at=?
                   WHERE id=?""",
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
            row = db.execute(
                "SELECT * FROM email_templates WHERE id=?", (template_id,)
            ).fetchone()
            return dict(row)

    @staticmethod
    def reset_template(template_id: str) -> dict:
        """Reset a template to its default content."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM email_templates WHERE id=?", (template_id,)
            ).fetchone()
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
                   subject=?, body_html=?, body_text=?, updated_at=?
                   WHERE id=?""",
                (
                    default["subject"],
                    default["body_html"],
                    default.get("body_text", ""),
                    now,
                    template_id,
                ),
            )
            row = db.execute(
                "SELECT * FROM email_templates WHERE id=?", (template_id,)
            ).fetchone()
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
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)""",
                (
                    template_id, template_key, name, description,
                    subject, body_html, body_text, category,
                    vars_json, now, now,
                ),
            )
            row = db.execute(
                "SELECT * FROM email_templates WHERE id=?", (template_id,)
            ).fetchone()
            return dict(row)

    @staticmethod
    def delete_template(template_id: str) -> bool:
        """Delete a custom email template. Returns False if template is a default (protected)."""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM email_templates WHERE id=?", (template_id,)
            ).fetchone()
            if not row:
                return None  # not found

            tpl = dict(row)
            # Protect default templates from deletion
            is_default = any(
                d["template_key"] == tpl["template_key"] for d in DEFAULT_TEMPLATES
            )
            if is_default:
                return False  # protected

            db.execute("DELETE FROM email_templates WHERE id=?", (template_id,))
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
    ) -> dict:
        """Render and send an email using SendGrid (or log if no API key)."""
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
                   VALUES (?, ?, ?, ?, ?, ?, 'queued', ?, ?)""",
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
                )
                with get_db() as db:
                    db.execute(
                        """UPDATE email_send_log SET
                           status='sent', provider=?, provider_message_id=?, sent_at=?
                           WHERE id=?""",
                        (provider, result.get("message_id", ""), now, log_id),
                    )
                logger.info(f"Email sent via {provider} to {recipient_email}: {rendered['subject']}")
                return {"status": "sent", "log_id": log_id, "provider": provider, "message_id": result.get("message_id")}
            except Exception as e:
                error_msg = str(e)
                with get_db() as db:
                    db.execute(
                        "UPDATE email_send_log SET status='failed', provider=?, error_message=? WHERE id=?",
                        (provider, error_msg, log_id),
                    )
                logger.error(f"{provider} delivery failed: {error_msg}")
                return {"status": "failed", "log_id": log_id, "provider": provider, "error": error_msg}
        else:
            # No provider configured — store as logged only
            with get_db() as db:
                db.execute(
                    "UPDATE email_send_log SET status='logged', sent_at=? WHERE id=?",
                    (now, log_id),
                )

            # Also store in legacy email_notifications table for backward compatibility
            with get_db() as db:
                db.execute(
                    """INSERT INTO email_notifications
                       (id, recipient_email, recipient_name, subject, body,
                        notification_type, status, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, 'sent', ?)""",
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
    ) -> dict:
        """Send email via SendGrid API."""
        import httpx

        response = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={
                "Authorization": f"Bearer {SENDGRID_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "personalizations": [{
                    "to": [{"email": to_email, "name": to_name}],
                }],
                "from": {
                    "email": FROM_EMAIL,
                    "name": FROM_NAME,
                },
                "subject": subject,
                "content": [
                    {"type": "text/plain", "value": text_content or subject},
                    {"type": "text/html", "value": html_content},
                ],
            },
            timeout=10,
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
    ) -> dict:
        """Send email via Mailgun API."""
        import httpx

        response = httpx.post(
            f"https://api.mailgun.net/v3/{MAILGUN_DOMAIN}/messages",
            auth=("api", MAILGUN_API_KEY),
            data={
                "from": f"{FROM_NAME} <{FROM_EMAIL}>",
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
    ) -> dict:
        """Send email via Resend API."""
        import httpx

        response = httpx.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": f"{FROM_NAME} <{FROM_EMAIL}>",
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
                query += " WHERE template_key=?"
                params.append(template_key)
            query += " ORDER BY created_at DESC LIMIT ?"
            params.append(limit)
            rows = db.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_email_stats() -> dict:
        """Get email delivery statistics."""
        with get_db() as db:
            total = db.execute("SELECT COUNT(*) as cnt FROM email_send_log").fetchone()
            sent = db.execute("SELECT COUNT(*) as cnt FROM email_send_log WHERE status='sent'").fetchone()
            logged = db.execute("SELECT COUNT(*) as cnt FROM email_send_log WHERE status='logged'").fetchone()
            failed = db.execute("SELECT COUNT(*) as cnt FROM email_send_log WHERE status='failed'").fetchone()
            return {
                "total": dict(total)["cnt"] if total else 0,
                "sent": dict(sent)["cnt"] if sent else 0,
                "logged": dict(logged)["cnt"] if logged else 0,
                "failed": dict(failed)["cnt"] if failed else 0,
                "provider": _detect_provider() or None,
                "provider_configured": _provider_configured(),
            }
