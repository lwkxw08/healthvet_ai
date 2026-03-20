from pydantic import BaseModel
from typing import Optional, List


class IdentityCheckRequest(BaseModel):
    candidate_id: str
    document_type: str = "passport"
    document_file_name: Optional[str] = None  # Original filename of uploaded document
    selfie_file_name: Optional[str] = None  # Original filename of uploaded selfie
    first_name: Optional[str] = None  # For cross-referencing with document
    last_name: Optional[str] = None
    date_of_birth: Optional[str] = None


class IdentitySDKTokenResponse(BaseModel):
    """Mirrors Onfido's SDK token response. In production, this would contain a real SDK token."""
    sdk_token: str
    applicant_id: str
    workflow_run_id: str


class IdentityCheckResponse(BaseModel):
    id: str
    candidate_id: str
    provider: str = "onfido"
    status: str
    document_type: Optional[str] = None
    document_file_name: Optional[str] = None
    selfie_file_name: Optional[str] = None
    document_authenticity: Optional[str] = None
    facial_match_score: Optional[float] = None
    liveness_check: Optional[str] = None
    address_verified: bool = False
    result: Optional[str] = None
    details: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


class RightToWorkRequest(BaseModel):
    candidate_id: str
    share_code: str


class RightToWorkUKCitizenRequest(BaseModel):
    candidate_id: str
    document_type: str  # "uk_passport", "irish_passport", "birth_certificate", "adoption_certificate", "naturalisation_certificate"
    document_reference: Optional[str] = None  # passport number or certificate ref
    ni_number: Optional[str] = None  # required when document_type is birth/adoption/naturalisation certificate
    nationality: str = "british"  # "british" or "irish"


class RightToWorkResponse(BaseModel):
    id: str
    candidate_id: str
    share_code: Optional[str] = None
    verification_method: Optional[str] = None
    nationality: Optional[str] = None
    document_type: Optional[str] = None
    document_reference: Optional[str] = None
    ni_number: Optional[str] = None
    status: str
    visa_type: Optional[str] = None
    visa_expiry: Optional[str] = None
    work_restrictions: Optional[str] = None
    verified: bool = False
    result: Optional[str] = None
    details: Optional[str] = None
    checked_at: Optional[str] = None
    next_check_at: Optional[str] = None


class DBSCheckRequest(BaseModel):
    candidate_id: str
    check_type: str = "enhanced"


class DBSCheckResponse(BaseModel):
    id: str
    candidate_id: str
    provider: str = "ucheck"
    check_type: str = "enhanced"
    status: str
    application_ref: Optional[str] = None
    certificate_number: Optional[str] = None
    issue_date: Optional[str] = None
    result: Optional[str] = None
    details: Optional[str] = None
    update_service_registered: bool = False
    next_renewal: Optional[str] = None
    submitted_at: Optional[str] = None
    completed_at: Optional[str] = None


class CVAnalysisRequest(BaseModel):
    candidate_id: str
    cv_text: str
    cv_file_name: Optional[str] = None  # Original filename if uploaded


class CVAnalysisResponse(BaseModel):
    id: str
    candidate_id: str
    cv_file_name: Optional[str] = None
    gap_analysis: Optional[str] = None
    overlap_detection: Optional[str] = None
    qualification_flags: Optional[str] = None
    fraud_risk_score: float = 0.0
    inconsistencies: Optional[str] = None
    ai_summary: Optional[str] = None
    employment_entries: Optional[str] = None
    status: str
    analysed_at: Optional[str] = None


class RegistrationCheckRequest(BaseModel):
    candidate_id: str
    body: str
    registration_number: str


class RegistrationCheckResponse(BaseModel):
    id: str
    candidate_id: str
    body: str
    registration_number: Optional[str] = None
    status: str
    is_active: Optional[bool] = None
    sanctions: Optional[str] = None
    conditions: Optional[str] = None
    last_checked: Optional[str] = None
    next_check: Optional[str] = None
    result: Optional[str] = None


class ReferenceRequest(BaseModel):
    candidate_id: str
    referee_name: str
    referee_email: str
    referee_phone: Optional[str] = None
    referee_organisation: Optional[str] = None
    referee_job_title: Optional[str] = None
    relationship: Optional[str] = None


class ReferenceResponse(BaseModel):
    id: str
    candidate_id: str
    referee_name: str
    referee_email: str
    referee_phone: Optional[str] = None
    referee_organisation: Optional[str] = None
    referee_job_title: Optional[str] = None
    relationship: Optional[str] = None
    token: Optional[str] = None
    status: str
    responses: Optional[str] = None
    sentiment_score: Optional[float] = None
    fraud_flags: Optional[str] = None
    domain_verified: bool = False
    reminder_count: int = 0
    sent_at: Optional[str] = None
    completed_at: Optional[str] = None


class ReferenceSubmission(BaseModel):
    token: str
    job_title_confirmed: bool = True
    dates_confirmed: bool = True
    performance_rating: int = 5
    would_rehire: bool = True
    concerns: Optional[str] = None
    additional_comments: Optional[str] = None


class ComplianceResponse(BaseModel):
    id: str
    candidate_id: str
    overall_status: str
    score: float
    identity_verified: bool
    right_to_work_valid: bool
    dbs_valid: bool
    registration_active: bool
    references_verified: bool
    cv_validated: bool
    employment_verified: bool = False
    flags: Optional[str] = None
    audit_log: Optional[str] = None
    last_evaluated: Optional[str] = None
    cqc_ready: bool = False


class MonitoringAlertResponse(BaseModel):
    id: str
    candidate_id: str
    alert_type: str
    severity: str
    message: str
    details: Optional[str] = None
    is_read: bool = False
    is_resolved: bool = False
    created_at: Optional[str] = None
    resolved_at: Optional[str] = None


class WebhookEvent(BaseModel):
    source: str
    event_type: str
    payload: Optional[str] = None


# ── Employment History & Verification ────────────────────────────

class EmploymentHistoryEntry(BaseModel):
    id: str
    candidate_id: str
    cv_analysis_id: Optional[str] = None
    employer_name: str
    job_title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    reason_for_leaving: Optional[str] = None
    duties: Optional[str] = None
    verifier_name: Optional[str] = None
    verifier_email: Optional[str] = None
    verifier_job_title: Optional[str] = None
    source: str = "cv_extracted"
    created_at: Optional[str] = None


class EmploymentEntryUpdate(BaseModel):
    employer_name: Optional[str] = None
    job_title: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: Optional[bool] = None
    reason_for_leaving: Optional[str] = None
    duties: Optional[str] = None
    verifier_name: Optional[str] = None
    verifier_email: Optional[str] = None
    verifier_job_title: Optional[str] = None


class EmploymentEntryCreate(BaseModel):
    candidate_id: str
    employer_name: str
    job_title: str
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    is_current: bool = False
    reason_for_leaving: Optional[str] = None
    duties: Optional[str] = None
    verifier_name: Optional[str] = None
    verifier_email: Optional[str] = None
    verifier_job_title: Optional[str] = None


class EmploymentVerificationRequest(BaseModel):
    candidate_id: str
    employment_id: str
    verifier_name: str
    verifier_email: str
    verifier_job_title: Optional[str] = None


class EmploymentVerificationResponse(BaseModel):
    id: str
    candidate_id: str
    employment_id: str
    verifier_name: str
    verifier_email: str
    verifier_job_title: Optional[str] = None
    employer_name: Optional[str] = None
    token: Optional[str] = None
    status: str
    job_title_confirmed: Optional[bool] = None
    dates_confirmed: Optional[bool] = None
    reason_for_leaving_confirmed: Optional[str] = None
    additional_comments: Optional[str] = None
    fraud_flags: Optional[str] = None
    domain_verified: bool = False
    reminder_count: int = 0
    sent_at: Optional[str] = None
    completed_at: Optional[str] = None


class DashboardStats(BaseModel):
    total_candidates: int = 0
    compliant: int = 0
    pending: int = 0
    flagged: int = 0
    compliance_rate: float = 0.0
    active_alerts: int = 0
    checks_in_progress: int = 0
    avg_completion_time_hours: float = 0.0
