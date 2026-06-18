"""Routes for all vetting checks."""
from fastapi import APIRouter, HTTPException, Depends, Request
from app.utils.auth import get_current_user, verify_agency_owns_candidate
from app.schemas.checks import (
    IdentityCheckRequest, IdentityCheckResponse, IdentitySDKTokenResponse,
    RightToWorkRequest, RightToWorkUKCitizenRequest, RightToWorkResponse,
    DBSCheckRequest, DBSCheckResponse, CandidateDBSSubmission, DBSConsentResponse,
    CVAnalysisRequest, CVAnalysisResponse,
    RegistrationCheckRequest, RegistrationCheckResponse,
    ReferenceRequest, ReferenceResponse, ReferenceSubmission,
    EmploymentHistoryEntry, EmploymentEntryUpdate, EmploymentEntryCreate,
    EmploymentVerificationRequest, EmploymentVerificationResponse,
    ImposterDeclarationRequest, ImposterDeclarationResponse,
)
import json
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id
from app.services.identity_verification import IdentityVerificationService
from app.services.right_to_work import RightToWorkService
from app.services.dbs_checks import DBSCheckService
from app.services.cv_analysis import CVAnalysisService
from app.services.registration_checks import RegistrationCheckService
from app.services.reference_automation import ReferenceAutomationService
from app.services.employment_verification import EmploymentVerificationService
from app.services.compliance_engine import ComplianceEngine

router = APIRouter(prefix="/api/checks", tags=["Checks"])


# ── Identity Verification ──────────────────────────────────────────
@router.post("/identity/sdk-token", response_model=IdentitySDKTokenResponse)
async def create_identity_sdk_token(data: IdentityCheckRequest, current_user: dict = Depends(get_current_user)):
    """Create an Onfido SDK token for the Smart Capture flow.
    In production, this returns a real Onfido SDK token for the frontend."""
    verify_agency_owns_candidate(current_user, data.candidate_id)
    return IdentityVerificationService.create_sdk_token(data.candidate_id)


@router.post("/identity", response_model=IdentityCheckResponse)
async def initiate_identity_check(data: IdentityCheckRequest, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    result = IdentityVerificationService.initiate_check(
        candidate_id=data.candidate_id,
        document_type=data.document_type,
        document_file_name=data.document_file_name,
        selfie_file_name=data.selfie_file_name,
        first_name=data.first_name,
        last_name=data.last_name,
        date_of_birth=data.date_of_birth,
    )
    # Auto-evaluate compliance after check
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return result


@router.get("/identity/{candidate_id}", response_model=list[IdentityCheckResponse])
async def get_identity_checks(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return IdentityVerificationService.get_checks_for_candidate(candidate_id)


# ── Right to Work ──────────────────────────────────────────────────
@router.post("/right-to-work", response_model=RightToWorkResponse)
async def verify_right_to_work(data: RightToWorkRequest, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    result = RightToWorkService.verify_share_code(data.candidate_id, data.share_code)
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return result


@router.post("/right-to-work/uk-citizen", response_model=RightToWorkResponse)
async def verify_right_to_work_uk_citizen(data: RightToWorkUKCitizenRequest, current_user: dict = Depends(get_current_user)):
    """Verify right to work for British/Irish citizens using accepted documents.
    No Home Office share code needed."""
    verify_agency_owns_candidate(current_user, data.candidate_id)
    try:
        result = RightToWorkService.verify_uk_citizen(
            candidate_id=data.candidate_id,
            document_type=data.document_type,
            nationality=data.nationality,
            document_reference=data.document_reference,
            ni_number=data.ni_number,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return result


@router.get("/right-to-work/{candidate_id}", response_model=list[RightToWorkResponse])
async def get_right_to_work_checks(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return RightToWorkService.get_checks_for_candidate(candidate_id)


# ── DBS Checks ─────────────────────────────────────────────────────
@router.post("/dbs", response_model=DBSCheckResponse)
async def submit_dbs_check(data: DBSCheckRequest, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    result = DBSCheckService.submit_check(data.candidate_id, data.check_type)
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return result


@router.get("/dbs/{candidate_id}", response_model=list[DBSCheckResponse])
async def get_dbs_checks(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return DBSCheckService.get_checks_for_candidate(candidate_id)


@router.post("/dbs/update-service")
async def check_dbs_update_service(candidate_id: str, certificate_number: str, current_user: dict = Depends(get_current_user)):
    return DBSCheckService.check_update_service(candidate_id, certificate_number)


# ── Candidate-Supplied DBS ─────────────────────────────────────────
DBS_CONSENT_TEXT = (
    "I hereby authorise {agency_name} and Viper AI Ltd to access, verify, and process "
    "my Disclosure and Barring Service (DBS) certificate information for the purposes of "
    "pre-employment vetting and compliance checks. I confirm that the DBS certificate "
    "details I have provided are accurate and relate to a genuine DBS certificate issued "
    "to me. I understand that {agency_name} and Viper AI Ltd will use this information "
    "solely for the purpose of verifying my suitability for the role applied for, in "
    "accordance with the Data Protection Act 2018, UK GDPR, and the DBS Code of Practice. "
    "I consent to checks being made against the DBS Update Service where applicable."
)


@router.post("/dbs/candidate-supplied", response_model=DBSCheckResponse)
async def submit_candidate_supplied_dbs(
    data: CandidateDBSSubmission,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Submit a candidate-supplied DBS certificate for validation."""
    if current_user["type"] != "candidate":
        raise HTTPException(status_code=403, detail="Only candidates can submit their own DBS")
    if not data.consent_given:
        raise HTTPException(status_code=400, detail="You must provide authority for the agency and Viper AI to verify your DBS")

    candidate_id = current_user["sub"]
    now = datetime.now(timezone.utc).isoformat()
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("User-Agent", "")
    check_id = generate_id()

    # Validate certificate number format (12 digits)
    cert_clean = data.certificate_number.strip()
    if not cert_clean.isdigit() or len(cert_clean) != 12:
        raise HTTPException(status_code=400, detail="DBS certificate number must be exactly 12 digits")

    with get_db() as db:
        # Get agency info for consent text
        db.execute(
            """SELECT a.id, a.company_name FROM agencies a
               JOIN agency_candidates ac ON a.id = ac.agency_id
               WHERE ac.candidate_id = %s LIMIT 1""",
            (candidate_id,),
        )
        agency_row = db.fetchone()
        agency_id = dict(agency_row)["id"] if agency_row else None
        agency_name = dict(agency_row)["company_name"] if agency_row else "the agency"

        # Record DBS consent
        consent_id = generate_id()
        consent_text = DBS_CONSENT_TEXT.format(agency_name=agency_name)
        db.execute(
            """INSERT INTO dbs_consent_records
               (id, candidate_id, agency_id, dbs_check_id, consent_given,
                consent_text, consent_timestamp, consent_ip_address, consent_user_agent)
               VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s)""",
            (consent_id, candidate_id, agency_id, check_id,
             consent_text, now, ip_address, user_agent),
        )

        # Also record in consent_logs for GDPR audit trail
        db.execute(
            """INSERT INTO consent_logs
               (id, candidate_id, consent_type, consent_given, ip_address, user_agent, timestamp)
               VALUES (%s, %s, 'dbs_verification_authority', 1, %s, %s, %s)""",
            (generate_id(), candidate_id, ip_address, user_agent, now),
        )

        # Run validation on the candidate-supplied certificate
        validation = DBSCheckService.validate_candidate_dbs(
            cert_clean, data.issue_date, data.dbs_type, data.update_service_ref
        )

        # Insert the DBS check record
        db.execute(
            """INSERT INTO dbs_checks
               (id, candidate_id, provider, check_type, status, certificate_number,
                issue_date, result, details, submitted_at, completed_at,
                dbs_mode, candidate_certificate_number, candidate_issue_date,
                candidate_dbs_type, candidate_workforce, update_service_ref,
                validation_status, validation_details, validated_at)
               VALUES (%s, %s, 'candidate_supplied', %s, %s, %s, %s, %s, %s, %s, %s,
                       'candidate_supplied', %s, %s, %s, %s, %s, %s, %s, %s)""",
            (check_id, candidate_id, data.dbs_type, validation["status"],
             cert_clean, data.issue_date, validation["result"],
             json.dumps(validation["details"]), now,
             now if validation["status"] == "completed" else None,
             cert_clean, data.issue_date, data.dbs_type,
             data.workforce, data.update_service_ref,
             validation["validation_status"],
             json.dumps(validation["validation_details"]),
             now),
        )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'dbs_check', %s, 'candidate_supplied_dbs', %s, %s, %s)""",
            (generate_id(), check_id, candidate_id,
             json.dumps({
                 "dbs_mode": "candidate_supplied",
                 "certificate_number": cert_clean,
                 "dbs_type": data.dbs_type,
                 "consent_id": consent_id,
                 "ip_address": ip_address,
             }), now),
        )

        db.execute("SELECT * FROM dbs_checks WHERE id=%s", (check_id,))
        row = db.fetchone()

    # Re-evaluate compliance
    ComplianceEngine.evaluate_candidate(candidate_id)

    return dict(row)


@router.get("/dbs/consent/{candidate_id}", response_model=list[DBSConsentResponse])
async def get_dbs_consent_records(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get DBS consent/authority records for a candidate."""
    user_type = current_user.get("type")
    if user_type == "candidate" and current_user["sub"] != candidate_id:
        raise HTTPException(status_code=403, detail="You can only view your own consent records")
    if user_type not in ("candidate", "agency", "admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    with get_db() as db:
        db.execute(
            "SELECT * FROM dbs_consent_records WHERE candidate_id=%s ORDER BY consent_timestamp DESC",
            (candidate_id,),
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]


@router.get("/dbs/mode/{candidate_id}")
async def get_dbs_mode(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get the DBS mode for a candidate based on their agency's template config."""
    with get_db() as db:
        db.execute(
            """SELECT itc.config FROM industry_template_checks itc
               JOIN agencies a ON a.industry_template_id = itc.template_id
               JOIN agency_candidates ac ON ac.agency_id = a.id
               WHERE ac.candidate_id = %s AND itc.check_key LIKE 'dbs%%'
               AND itc.is_enabled = 1
               ORDER BY itc.sort_order ASC LIMIT 1""",
            (candidate_id,),
        )
        row = db.fetchone()
        if row:
            try:
                cfg = json.loads(dict(row).get("config") or "{}")
                return {"dbs_mode": cfg.get("dbs_mode", "viper_managed")}
            except (json.JSONDecodeError, TypeError):
                pass
        return {"dbs_mode": "viper_managed"}


# ── CV Analysis ────────────────────────────────────────────────────
@router.post("/cv-analysis", response_model=CVAnalysisResponse)
async def analyse_cv(data: CVAnalysisRequest, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    result = CVAnalysisService.analyse_cv(data.candidate_id, data.cv_text, data.cv_file_name)
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return result


@router.get("/cv-analysis/{candidate_id}", response_model=list[CVAnalysisResponse])
async def get_cv_analyses(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return CVAnalysisService.get_analyses_for_candidate(candidate_id)


# ── Registration Checks ───────────────────────────────────────────
@router.post("/registration", response_model=RegistrationCheckResponse)
async def check_registration(data: RegistrationCheckRequest, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    result = RegistrationCheckService.check_registration(data.candidate_id, data.body, data.registration_number)
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return result


@router.get("/registration/{candidate_id}", response_model=list[RegistrationCheckResponse])
async def get_registration_checks(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return RegistrationCheckService.get_checks_for_candidate(candidate_id)


# ── References ─────────────────────────────────────────────────────
@router.post("/references", response_model=ReferenceResponse)
async def create_reference_request(data: ReferenceRequest, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    result = ReferenceAutomationService.create_reference_request(
        candidate_id=data.candidate_id,
        referee_name=data.referee_name,
        referee_email=data.referee_email,
        referee_phone=data.referee_phone,
        referee_organisation=data.referee_organisation,
        referee_job_title=data.referee_job_title,
        relationship=data.relationship,
    )
    return result


@router.get("/references/{candidate_id}", response_model=list[ReferenceResponse])
async def get_references(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return ReferenceAutomationService.get_references_for_candidate(candidate_id)


@router.post("/references/submit")
async def submit_reference(data: ReferenceSubmission, request: Request):
    """Public endpoint for referees to submit their reference."""
    ip_address = request.client.host if request.client else None
    responses = {
        "job_title_confirmed": data.job_title_confirmed,
        "dates_confirmed": data.dates_confirmed,
        "performance_rating": data.performance_rating,
        "would_rehire": data.would_rehire,
        "concerns": data.concerns,
        "additional_comments": data.additional_comments,
    }
    result = ReferenceAutomationService.submit_reference(data.token, responses, ip_address)
    if not result:
        raise HTTPException(status_code=404, detail="Invalid reference token")

    # Evaluate compliance after reference
    ComplianceEngine.evaluate_candidate(result["candidate_id"])
    return result


@router.post("/references/{ref_id}/remind")
async def send_reminder(ref_id: str, current_user: dict = Depends(get_current_user)):
    result = ReferenceAutomationService.send_reminder(ref_id)
    if not result:
        raise HTTPException(status_code=404, detail="Reference not found")
    return result


# ── Employment History & Verification ────────────────────────────
@router.get("/employment/{candidate_id}", response_model=list[EmploymentHistoryEntry])
async def get_employment_history(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return EmploymentVerificationService.get_employment_history(candidate_id)


@router.post("/employment", response_model=EmploymentHistoryEntry)
async def add_employment_entry(data: EmploymentEntryCreate, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    return EmploymentVerificationService.add_employment_entry(
        candidate_id=data.candidate_id,
        employer_name=data.employer_name,
        job_title=data.job_title,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
        reason_for_leaving=data.reason_for_leaving,
        duties=data.duties,
        verifier_name=data.verifier_name,
        verifier_email=data.verifier_email,
        verifier_job_title=data.verifier_job_title,
    )


@router.put("/employment/{entry_id}", response_model=EmploymentHistoryEntry)
async def update_employment_entry(entry_id: str, data: EmploymentEntryUpdate, current_user: dict = Depends(get_current_user)):
    result = EmploymentVerificationService.update_employment_entry(
        entry_id=entry_id,
        employer_name=data.employer_name,
        job_title=data.job_title,
        start_date=data.start_date,
        end_date=data.end_date,
        is_current=data.is_current,
        reason_for_leaving=data.reason_for_leaving,
        duties=data.duties,
        verifier_name=data.verifier_name,
        verifier_email=data.verifier_email,
        verifier_job_title=data.verifier_job_title,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Employment entry not found")
    return result


@router.delete("/employment/{entry_id}")
async def delete_employment_entry(entry_id: str, current_user: dict = Depends(get_current_user)):
    if not EmploymentVerificationService.delete_employment_entry(entry_id):
        raise HTTPException(status_code=404, detail="Employment entry not found")
    return {"status": "deleted"}


@router.post("/employment/verify", response_model=EmploymentVerificationResponse)
async def send_employment_verification(
    data: EmploymentVerificationRequest,
    current_user: dict = Depends(get_current_user),
):
    verify_agency_owns_candidate(current_user, data.candidate_id)
    result = EmploymentVerificationService.send_verification_request(
        candidate_id=data.candidate_id,
        employment_id=data.employment_id,
        verifier_name=data.verifier_name,
        verifier_email=data.verifier_email,
        verifier_job_title=data.verifier_job_title,
    )
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return result


@router.get("/employment-verifications/{candidate_id}", response_model=list[EmploymentVerificationResponse])
async def get_employment_verifications(candidate_id: str, current_user: dict = Depends(get_current_user)):
    verify_agency_owns_candidate(current_user, candidate_id)
    return EmploymentVerificationService.get_verifications_for_candidate(candidate_id)


@router.post("/employment-verifications/{ver_id}/remind")
async def send_employment_verification_reminder(ver_id: str, current_user: dict = Depends(get_current_user)):
    result = EmploymentVerificationService.send_reminder(ver_id)
    if not result:
        raise HTTPException(status_code=404, detail="Employment verification not found")
    return result


# ── Imposter Check Declarations ──────────────────────────────────
@router.post("/imposter-declaration", response_model=ImposterDeclarationResponse)
async def submit_imposter_declaration(
    data: ImposterDeclarationRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """Agency submits a signed imposter check declaration for a candidate.
    This is required before RTW can be marked as compliant.
    The declaration is timestamped, non-editable, and logged in the audit trail."""
    if current_user.get("type") != "agency":
        raise HTTPException(status_code=403, detail="Only agency users can submit imposter declarations")

    verify_agency_owns_candidate(current_user, data.candidate_id)

    # JWT only contains sub (user_id) and type — look up agency details from DB
    agency_id = current_user["sub"]
    ip_address = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc).isoformat()
    declaration_id = generate_id()
    docs_json = json.dumps(data.documents_verified) if data.documents_verified else None

    with get_db() as db:
        # Look up agency email from the database
        db.execute("SELECT email FROM agencies WHERE id=%s", (agency_id,))
        agency_row = db.fetchone()
        agency_email = dict(agency_row)["email"] if agency_row else "unknown"

        # Check if declaration already exists (non-editable - only one allowed)
        db.execute(
            "SELECT id FROM imposter_declarations WHERE candidate_id=%s AND agency_id=%s",
            (data.candidate_id, agency_id),
        )
        existing = db.fetchone()
        if existing:
            raise HTTPException(
                status_code=409,
                detail="Imposter declaration already submitted for this candidate. Declarations are non-editable."
            )

        db.execute(
            """INSERT INTO imposter_declarations
               (id, candidate_id, agency_id, declared_by_user_id, declared_by_email,
                declaration_text, documents_verified, ip_address, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                declaration_id, data.candidate_id, agency_id,
                agency_id, agency_email,
                data.declaration_text, docs_json, ip_address, now,
            ),
        )

        # Immutable audit log entry
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'imposter_declaration', %s, 'submitted', %s, %s, %s)""",
            (
                generate_id(), data.candidate_id, agency_email,
                json.dumps({
                    "declaration_id": declaration_id,
                    "declared_by_user_id": agency_id,
                    "declared_by_email": agency_email,
                    "agency_id": agency_id,
                    "ip_address": ip_address,
                    "documents_verified": data.documents_verified,
                    "declaration_text": data.declaration_text,
                }),
                now,
            ),
        )

        db.execute("SELECT * FROM imposter_declarations WHERE id=%s", (declaration_id,))
        row = db.fetchone()

    # Re-evaluate compliance now that declaration is in place
    ComplianceEngine.evaluate_candidate(data.candidate_id)
    return dict(row)


@router.get("/imposter-declaration/{candidate_id}", response_model=list[ImposterDeclarationResponse])
async def get_imposter_declarations(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get imposter declarations for a candidate."""
    verify_agency_owns_candidate(current_user, candidate_id)
    with get_db() as db:
        db.execute(
            "SELECT * FROM imposter_declarations WHERE candidate_id=%s ORDER BY created_at DESC",
            (candidate_id,),
        )
        rows = db.fetchall()
        return [dict(r) for r in rows]
