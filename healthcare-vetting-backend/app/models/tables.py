"""SQLAlchemy ORM models for all HealthVet AI database tables.

Each model mirrors the existing SQLite schema exactly so that the ORM layer
can be adopted incrementally without breaking existing raw-SQL code paths.
"""

from sqlalchemy import (
    Column, String, Text, Float, Integer, ForeignKey, PrimaryKeyConstraint,
)
from app.models.base import Base


# ── Core Entities ────────────────────────────────────────────────────────────

class Candidate(Base):
    __tablename__ = "candidates"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    phone = Column(String)
    date_of_birth = Column(String)
    address_line1 = Column(String)
    address_line2 = Column(String)
    city = Column(String)
    postcode = Column(String)
    country = Column(String, default="GB")
    profession = Column(String)
    registration_number = Column(String)
    registration_body = Column(String)
    status = Column(String, default="pending")
    compliance_score = Column(Float, default=0.0)
    compliance_status = Column(String, default="incomplete")
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(String)
    last_login_at = Column(String)
    created_at = Column(String)
    updated_at = Column(String)


class Agency(Base):
    __tablename__ = "agencies"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    contact_name = Column(String)
    phone = Column(String)
    plan = Column(String, default="standard")
    monthly_fee = Column(Float, default=300.0)
    discount_percent = Column(Float, default=0)
    billing_mode = Column(String, default="manual_invoicing")
    stripe_customer_id = Column(String)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(String)
    last_login_at = Column(String)
    created_at = Column(String)


class AgencyCandidate(Base):
    __tablename__ = "agency_candidates"
    __table_args__ = (PrimaryKeyConstraint("agency_id", "candidate_id"),)

    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    assigned_at = Column(String)
    employment_status = Column(String, default="vetting")
    employment_status_updated_at = Column(String)
    annual_monitoring = Column(Integer, default=0)
    vetting_cost_accepted = Column(Float, default=0)
    monitoring_cost_accepted = Column(Float, default=0)


class AgencyInvite(Base):
    __tablename__ = "agency_invites"

    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    candidate_email = Column(String, nullable=False)
    invite_code = Column(String, unique=True, nullable=False)
    status = Column(String, default="pending")
    candidate_id = Column(String, ForeignKey("candidates.id"))
    include_monitoring = Column(Integer, default=0)
    vetting_cost = Column(Float, default=0)
    monitoring_cost = Column(Float, default=0)
    created_at = Column(String)
    accepted_at = Column(String)


# ── Check Tables ─────────────────────────────────────────────────────────────

class IdentityCheck(Base):
    __tablename__ = "identity_checks"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    provider = Column(String, default="onfido")
    status = Column(String, default="pending")
    document_type = Column(String)
    document_authenticity = Column(String)
    facial_match_score = Column(Float)
    liveness_check = Column(String)
    address_verified = Column(Integer, default=0)
    result = Column(String)
    details = Column(Text)
    started_at = Column(String)
    completed_at = Column(String)


class RightToWorkCheck(Base):
    __tablename__ = "right_to_work_checks"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    share_code = Column(String)
    verification_method = Column(String, default="share_code")
    nationality = Column(String)
    document_type = Column(String)
    document_reference = Column(String)
    ni_number = Column(String)
    status = Column(String, default="pending")
    visa_type = Column(String)
    visa_expiry = Column(String)
    work_restrictions = Column(String)
    verified = Column(Integer, default=0)
    result = Column(String)
    details = Column(Text)
    checked_at = Column(String)
    next_check_at = Column(String)


class DBSCheck(Base):
    __tablename__ = "dbs_checks"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    provider = Column(String, default="ucheck")
    check_type = Column(String, default="enhanced")
    status = Column(String, default="pending")
    application_ref = Column(String)
    certificate_number = Column(String)
    issue_date = Column(String)
    result = Column(String)
    details = Column(Text)
    update_service_registered = Column(Integer, default=0)
    next_renewal = Column(String)
    submitted_at = Column(String)
    completed_at = Column(String)


class CVAnalysis(Base):
    __tablename__ = "cv_analyses"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    cv_text = Column(Text)
    cv_file_name = Column(String)
    gap_analysis = Column(Text)
    overlap_detection = Column(Text)
    qualification_flags = Column(Text)
    fraud_risk_score = Column(Float, default=0.0)
    inconsistencies = Column(Text)
    ai_summary = Column(Text)
    employment_entries = Column(Text)
    status = Column(String, default="pending")
    analysed_at = Column(String)


class RegistrationCheck(Base):
    __tablename__ = "registration_checks"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    body = Column(String, nullable=False)
    registration_number = Column(String)
    status = Column(String, default="pending")
    is_active = Column(Integer)
    sanctions = Column(Text)
    conditions = Column(Text)
    last_checked = Column(String)
    next_check = Column(String)
    result = Column(String)


class Reference(Base):
    __tablename__ = "references_"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    referee_name = Column(String, nullable=False)
    referee_email = Column(String, nullable=False)
    referee_phone = Column(String)
    referee_organisation = Column(String)
    referee_job_title = Column(String)
    relationship = Column(String)
    token = Column(String, unique=True)
    status = Column(String, default="pending")
    responses = Column(Text)
    sentiment_score = Column(Float)
    fraud_flags = Column(Text)
    ip_address = Column(String)
    domain_verified = Column(Integer, default=0)
    reminder_count = Column(Integer, default=0)
    sent_at = Column(String)
    completed_at = Column(String)


# ── Compliance & Audit ───────────────────────────────────────────────────────

class ComplianceRecord(Base):
    __tablename__ = "compliance_records"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    overall_status = Column(String, default="incomplete")
    score = Column(Float, default=0.0)
    identity_verified = Column(Integer, default=0)
    right_to_work_valid = Column(Integer, default=0)
    dbs_valid = Column(Integer, default=0)
    registration_active = Column(Integer, default=0)
    references_verified = Column(Integer, default=0)
    cv_validated = Column(Integer, default=0)
    employment_verified = Column(Integer, default=0)
    training_compliant = Column(Integer, default=0)
    flags = Column(Text)
    audit_log = Column(Text)
    last_evaluated = Column(String)
    cqc_ready = Column(Integer, default=0)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(String, nullable=False)
    action = Column(String, nullable=False)
    actor = Column(String)
    details = Column(Text)
    created_at = Column(String)


class ConsentLog(Base):
    __tablename__ = "consent_logs"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    submission_id = Column(String)
    consent_type = Column(String, nullable=False)
    consent_given = Column(Integer, nullable=False)
    ip_address = Column(String)
    user_agent = Column(String)
    privacy_policy_version = Column(String)
    terms_version = Column(String)
    timestamp = Column(String, nullable=False)


# ── Billing & Subscriptions ──────────────────────────────────────────────────

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    candidate_id = Column(String)
    candidate_email = Column(String)
    check_type = Column(String)
    description = Column(Text)
    cost_amount = Column(Float, default=0.0)
    sell_amount = Column(Float, default=0.0)
    adjusted_amount = Column(Float)
    adjustment_notes = Column(Text)
    status = Column(String, default="pending")
    payment_method = Column(String, default="manual")
    stripe_session_id = Column(String)
    stripe_payment_intent_id = Column(String)
    due_date = Column(String)
    reminder_sent_at = Column(String)
    reminder_count = Column(Integer, default=0)
    created_at = Column(String)
    paid_at = Column(String)


class PricingSetting(Base):
    __tablename__ = "pricing_settings"

    id = Column(String, primary_key=True)
    check_type = Column(String, unique=True, nullable=False)
    label = Column(String, nullable=False)
    cost_price = Column(Float, default=0.0)
    sell_price = Column(Float, default=0.0)
    updated_at = Column(String)


class SubscriptionTierConfig(Base):
    __tablename__ = "subscription_tier_config"

    id = Column(String, primary_key=True)
    tier_key = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    monthly_price = Column(Float, default=0)
    per_worker_price = Column(Float, default=0)
    max_workers = Column(Integer, default=0)
    monthly_checks = Column(Integer, default=0)
    overage_rate = Column(Float, default=0)
    allow_rollover = Column(Integer, default=0)
    monitoring_included = Column(Integer, default=0)
    monitoring_cap = Column(Integer, default=0)
    monitoring_addon_rate = Column(Float, default=0)
    features = Column(Text, default="[]")
    is_active = Column(Integer, default=1)
    updated_at = Column(String)


class AgencySubscription(Base):
    __tablename__ = "agency_subscriptions"

    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    tier = Column(String, nullable=False)
    billing_method = Column(String, default="stripe")
    monthly_amount = Column(Float, default=0.0)
    per_worker_amount = Column(Float, default=0.0)
    max_workers = Column(Integer, default=50)
    monthly_checks = Column(Integer, default=0)
    checks_used = Column(Integer, default=0)
    credits_total = Column(Float, default=0)
    credits_used = Column(Float, default=0)
    rollover_credits = Column(Float, default=0)
    allow_rollover = Column(Integer, default=0)
    overage_rate = Column(Float, default=0)
    stripe_payment_method_id = Column(String)
    stripe_subscription_id = Column(String)
    status = Column(String, default="active")
    current_period_start = Column(String)
    current_period_end = Column(String)
    next_billing_date = Column(String)
    cancelled_at = Column(String)
    created_at = Column(String)


class PartialCreditRate(Base):
    __tablename__ = "partial_credit_rates"

    id = Column(String, primary_key=True)
    check_type = Column(String, unique=True, nullable=False)
    label = Column(String, nullable=False)
    credit_value = Column(Float, default=1.0)
    third_party_cost = Column(Float, default=0)
    updated_at = Column(String)


class CreditTransaction(Base):
    __tablename__ = "credit_transactions"

    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    candidate_id = Column(String)
    order_id = Column(String)
    check_type = Column(String, nullable=False)
    credits_consumed = Column(Float, default=0)
    credit_balance_after = Column(Float, default=0)
    unit_cost = Column(Float, default=0)
    charge_amount = Column(Float, default=0)
    is_overage = Column(Integer, default=0)
    is_rollover = Column(Integer, default=0)
    description = Column(Text)
    created_at = Column(String)


# ── Employment ───────────────────────────────────────────────────────────────

class EmploymentHistory(Base):
    __tablename__ = "employment_history"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    cv_analysis_id = Column(String)
    employer_name = Column(String, nullable=False)
    job_title = Column(String, nullable=False)
    start_date = Column(String)
    end_date = Column(String)
    is_current = Column(Integer, default=0)
    reason_for_leaving = Column(Text)
    duties = Column(Text)
    verifier_name = Column(String)
    verifier_email = Column(String)
    verifier_job_title = Column(String)
    source = Column(String, default="cv_extracted")
    created_at = Column(String)


class EmploymentVerification(Base):
    __tablename__ = "employment_verifications"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    employment_id = Column(String, ForeignKey("employment_history.id"), nullable=False)
    verifier_name = Column(String, nullable=False)
    verifier_email = Column(String, nullable=False)
    verifier_job_title = Column(String)
    employer_name = Column(String)
    token = Column(String, unique=True)
    status = Column(String, default="pending")
    job_title_confirmed = Column(Integer)
    dates_confirmed = Column(Integer)
    reason_for_leaving_confirmed = Column(String)
    additional_comments = Column(Text)
    fraud_flags = Column(Text)
    ip_address = Column(String)
    domain_verified = Column(Integer, default=0)
    reminder_count = Column(Integer, default=0)
    sent_at = Column(String)
    completed_at = Column(String)


# ── Imposter Check ───────────────────────────────────────────────────────────

class ImposterDeclaration(Base):
    __tablename__ = "imposter_declarations"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    declared_by_user_id = Column(String, nullable=False)
    declared_by_email = Column(String, nullable=False)
    declaration_text = Column(Text, nullable=False)
    documents_verified = Column(Text)
    ip_address = Column(String)
    created_at = Column(String, nullable=False)


# ── Submissions & Misc ───────────────────────────────────────────────────────

class CandidateSubmission(Base):
    __tablename__ = "candidate_submissions"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    submission_type = Column(String, default="full")
    sections_requested = Column(Text)
    status = Column(String, default="draft")
    consent_given = Column(Integer, default=0)
    consent_timestamp = Column(String)
    consent_ip_address = Column(String)
    privacy_policy_version = Column(String, default="1.0")
    terms_version = Column(String, default="1.0")
    submitted_at = Column(String)
    processing_started_at = Column(String)
    processing_completed_at = Column(String)
    created_at = Column(String)


class CandidateDraftData(Base):
    __tablename__ = "candidate_draft_data"

    id = Column(String, primary_key=True)
    submission_id = Column(String, ForeignKey("candidate_submissions.id"), nullable=False)
    candidate_id = Column(String, nullable=False)
    section = Column(String, nullable=False)
    data = Column(Text, nullable=False)
    completed = Column(Integer, default=0)
    updated_at = Column(String)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True)
    source = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(Text)
    status = Column(String, default="received")
    processed_at = Column(String)
    created_at = Column(String)


class MonitoringAlert(Base):
    __tablename__ = "monitoring_alerts"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    alert_type = Column(String, nullable=False)
    severity = Column(String, default="medium")
    message = Column(String, nullable=False)
    details = Column(Text)
    is_read = Column(Integer, default=0)
    is_resolved = Column(Integer, default=0)
    created_at = Column(String)
    resolved_at = Column(String)


class EmailNotification(Base):
    __tablename__ = "email_notifications"

    id = Column(String, primary_key=True)
    recipient_email = Column(String, nullable=False)
    recipient_name = Column(String)
    subject = Column(String, nullable=False)
    body = Column(Text)
    notification_type = Column(String)
    related_id = Column(String)
    status = Column(String, default="pending")
    created_at = Column(String)


class TrainingCertificate(Base):
    __tablename__ = "training_certificates"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    certificate_name = Column(String, nullable=False)
    category = Column(String, default="mandatory")
    provider = Column(String)
    issue_date = Column(String)
    expiry_date = Column(String)
    certificate_ref = Column(String)
    file_name = Column(String)
    status = Column(String, default="valid")
    created_at = Column(String)
    updated_at = Column(String)


class FraudFlag(Base):
    __tablename__ = "fraud_flags"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"))
    flag_type = Column(String, nullable=False)
    severity = Column(String, default="medium")
    message = Column(String, nullable=False)
    details = Column(Text)
    is_resolved = Column(Integer, default=0)
    resolved_by = Column(String)
    resolved_at = Column(String)
    created_at = Column(String)


class AlertSetting(Base):
    __tablename__ = "alert_settings"

    id = Column(String, primary_key=True)
    setting_key = Column(String, unique=True, nullable=False)
    setting_value = Column(Integer, nullable=False)
    updated_at = Column(String)


class RevetRequest(Base):
    __tablename__ = "revet_requests"

    id = Column(String, primary_key=True)
    agency_id = Column(String, ForeignKey("agencies.id"), nullable=False)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    sections = Column(Text, nullable=False)
    token = Column(String, unique=True, nullable=False)
    status = Column(String, default="pending")
    submission_id = Column(String)
    created_at = Column(String)
    completed_at = Column(String)


# ── Session Management ───────────────────────────────────────────────────────

class ActiveSession(Base):
    """Tracks active user sessions for concurrent session limiting."""
    __tablename__ = "active_sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    user_type = Column(String, nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    ip_address = Column(String)
    user_agent = Column(String)
    created_at = Column(String, nullable=False)
    last_active_at = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)


# ── 1.4 Auth & Security Hardening ─────────────────────────────────────────

class AdminUser(Base):
    __tablename__ = "admin_users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    display_name = Column(String, nullable=False)
    role = Column(String, default="admin")
    is_active = Column(Integer, default=1)
    failed_login_attempts = Column(Integer, default=0)
    locked_until = Column(String)
    last_login_at = Column(String)
    created_at = Column(String)
    updated_at = Column(String)


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False)
    user_type = Column(String, nullable=False)
    ip_address = Column(String)
    success = Column(Integer, nullable=False)
    created_at = Column(String)


class PasswordResetToken(Base):
    __tablename__ = "password_reset_tokens"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False)
    user_type = Column(String, nullable=False)
    token_hash = Column(String, unique=True, nullable=False)
    expires_at = Column(String, nullable=False)
    used_at = Column(String)
    created_at = Column(String)


class TokenBlacklist(Base):
    __tablename__ = "token_blacklist"

    id = Column(String, primary_key=True)
    token_jti = Column(String, unique=True, nullable=False)
    user_id = Column(String, nullable=False)
    expires_at = Column(String, nullable=False)
    revoked_at = Column(String)


# ── 2.3 Candidate Pre-Notification ────────────────────────────────────────

class CandidatePreNotification(Base):
    __tablename__ = "candidate_pre_notifications"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    verification_type = Column(String, nullable=False)
    verifier_name = Column(String, nullable=False)
    verifier_email = Column(String, nullable=False)
    verifier_organisation = Column(String)
    status = Column(String, default="pending")
    sent_at = Column(String)
    candidate_confirmed_at = Column(String)
    verification_request_id = Column(String)
    created_at = Column(String)


class CandidateDocument(Base):
    __tablename__ = "candidate_documents"

    id = Column(String, primary_key=True)
    candidate_id = Column(String, ForeignKey("candidates.id"), nullable=False)
    document_type = Column(String, nullable=False)
    file_name = Column(String, nullable=False)
    file_path = Column(String, nullable=False)
    file_size = Column(Integer)
    description = Column(Text)
    uploaded_at = Column(String)
