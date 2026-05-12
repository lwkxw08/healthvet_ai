"""
Public Verification Portal API
No authentication required — verifiers access this via the code in their email.
Endpoints:
  POST /api/verify/lookup   — accept a verification code, return form type + pre-filled data
  POST /api/verify/submit   — accept a code + responses, update the verification record
  GET  /api/verify/status/{code} — check if a code is valid without revealing data
"""
import json
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Optional
from app.database import get_db
from app.utils.auth import generate_id
from app.services.compliance_engine import ComplianceEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/verify", tags=["Verification Portal"])


# ── Request / Response Models ────────────────────────────────────────────────

class CodeLookupRequest(BaseModel):
    code: str = Field(..., description="Verification code e.g. HV-7X9K-2M4P")


class EmploymentSubmission(BaseModel):
    code: str
    job_title_confirmed: bool
    dates_confirmed: bool
    reason_for_leaving_confirmed: Optional[str] = None
    additional_comments: Optional[str] = None
    responder_name: Optional[str] = None
    responder_job_title: Optional[str] = None


class ReferenceSubmission(BaseModel):
    code: str
    # Ratings & would_rehire suppressed pre-launch — made optional, reinstate as required post go-live
    performance_rating: Optional[int] = Field(None, ge=1, le=5, description="1-5 rating")
    conduct_rating: Optional[int] = Field(None, ge=1, le=5)
    reliability_rating: Optional[int] = Field(None, ge=1, le=5)
    would_rehire: Optional[bool] = None
    relationship_to_candidate: Optional[str] = None
    known_since: Optional[str] = None
    strengths: Optional[str] = None
    # areas_for_improvement suppressed pre-launch — reinstate post go-live
    areas_for_improvement: Optional[str] = None
    additional_comments: Optional[str] = None
    responder_name: Optional[str] = None
    responder_job_title: Optional[str] = None


# ── Helper: find verification record by code ─────────────────────────────────

def _lookup_by_code(code: str) -> tuple:
    """Return (record_dict, record_type) or (None, None) if not found.
    record_type is 'employment' or 'reference'.
    """
    normalized = code.strip().upper()
    with get_db() as db:
        # Try employment_verifications first
        db.execute(
            "SELECT * FROM employment_verifications WHERE verification_code=%s",
            (normalized,),
        )
        row = db.fetchone()
        if row:
            return dict(row), "employment"

        # Try references_
        db.execute(
            "SELECT * FROM references_ WHERE verification_code=%s",
            (normalized,),
        )
        row = db.fetchone()
        if row:
            return dict(row), "reference"

    return None, None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/status/{code}")
async def check_code_status(code: str):
    """Quick check if a code is valid. Returns type and status without sensitive data."""
    record, record_type = _lookup_by_code(code)
    if not record:
        raise HTTPException(status_code=404, detail="Verification code not found")

    return {
        "valid": True,
        "type": record_type,
        "status": record.get("status", "unknown"),
        "already_completed": record.get("status") in ("verified", "completed", "disputed", "flagged"),
    }


@router.post("/lookup")
async def lookup_verification(body: CodeLookupRequest):
    """Look up a verification code and return the form data for the verifier to fill in."""
    record, record_type = _lookup_by_code(body.code)
    if not record:
        raise HTTPException(status_code=404, detail="Verification code not found. Please check the code and try again.")

    # Check if already completed
    completed_statuses = ("verified", "completed", "disputed", "flagged")
    if record.get("status") in completed_statuses:
        return {
            "type": record_type,
            "status": record["status"],
            "already_completed": True,
            "completed_at": record.get("completed_at"),
            "message": "This verification has already been completed. Thank you for your response.",
        }

    # Check expiry (30 days from sent_at)
    sent_at = record.get("sent_at")
    if sent_at:
        try:
            sent_dt = datetime.fromisoformat(sent_at)
            if sent_dt.tzinfo is None:
                sent_dt = sent_dt.replace(tzinfo=timezone.utc)
            days_elapsed = (datetime.now(timezone.utc) - sent_dt).days
            if days_elapsed > 30:
                return {
                    "type": record_type,
                    "status": "expired",
                    "already_completed": False,
                    "message": "This verification code has expired. Please contact the agency to request a new one.",
                }
        except (ValueError, TypeError):
            pass

    # Return form data based on type
    if record_type == "employment":
        # Get candidate name
        candidate_name = _get_candidate_name(record.get("candidate_id"))
        return {
            "type": "employment",
            "status": record["status"],
            "already_completed": False,
            "form_data": {
                "candidate_name": candidate_name,
                "employer_name": record.get("employer_name", ""),
                "verifier_name": record.get("verifier_name", ""),
                "job_title": _get_employment_job_title(record.get("employment_id")),
                "start_date": _get_employment_dates(record.get("employment_id"), "start_date"),
                "end_date": _get_employment_dates(record.get("employment_id"), "end_date"),
            },
        }
    else:
        # Reference
        candidate_name = _get_candidate_name(record.get("candidate_id"))
        return {
            "type": "reference",
            "status": record["status"],
            "already_completed": False,
            "form_data": {
                "candidate_name": candidate_name,
                "referee_name": record.get("referee_name", ""),
                "referee_organisation": record.get("referee_organisation", ""),
            },
        }


@router.post("/submit/employment")
async def submit_employment_verification(body: EmploymentSubmission, request: Request):
    """Submit an employment verification response via the portal."""
    record, record_type = _lookup_by_code(body.code)
    if not record:
        raise HTTPException(status_code=404, detail="Verification code not found")
    if record_type != "employment":
        raise HTTPException(status_code=400, detail="This code is for a reference request, not employment verification")

    completed_statuses = ("verified", "completed", "disputed", "flagged")
    if record.get("status") in completed_statuses:
        raise HTTPException(status_code=400, detail="This verification has already been completed")

    now = datetime.now(timezone.utc).isoformat()
    ip_address = request.client.host if request.client else None

    # Determine status
    fraud_flags = []
    if record.get("sent_at"):
        try:
            sent_dt = datetime.fromisoformat(record["sent_at"])
            if sent_dt.tzinfo is None:
                sent_dt = sent_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - sent_dt).total_seconds()
            if elapsed < 60:
                fraud_flags.append({
                    "type": "suspicious_timing",
                    "detail": f"Verification completed in {elapsed:.0f} seconds — unusually fast",
                })
        except (ValueError, TypeError):
            pass

    status = "verified" if (body.job_title_confirmed and body.dates_confirmed) else "disputed"
    if fraud_flags:
        status = "flagged"

    with get_db() as db:
        db.execute(
            """UPDATE employment_verifications SET
               status=%s, job_title_confirmed=%s, dates_confirmed=%s,
               reason_for_leaving_confirmed=%s, additional_comments=%s,
               fraud_flags=%s, ip_address=%s, completed_at=%s
               WHERE verification_code=%s""",
            (
                status,
                1 if body.job_title_confirmed else 0,
                1 if body.dates_confirmed else 0,
                body.reason_for_leaving_confirmed,
                body.additional_comments,
                json.dumps(fraud_flags) if fraud_flags else None,
                ip_address,
                now,
                body.code.strip().upper(),
            ),
        )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'employment_verification', %s, 'portal_submitted', 'verifier', %s, %s)""",
            (
                generate_id(), record["id"],
                json.dumps({
                    "ip": ip_address,
                    "job_title_confirmed": body.job_title_confirmed,
                    "dates_confirmed": body.dates_confirmed,
                    "responder_name": body.responder_name,
                }),
                now,
            ),
        )

        # Create fraud alert if flagged
        if fraud_flags:
            db.execute(
                """INSERT INTO monitoring_alerts
                   (id, candidate_id, alert_type, severity, message, details, created_at)
                   VALUES (%s, %s, 'employment_verification_fraud', 'high', %s, %s, %s)""",
                (
                    generate_id(), record["candidate_id"],
                    "Employment verification fraud flags detected via portal",
                    json.dumps(fraud_flags),
                    now,
                ),
            )

    # Re-evaluate compliance now that employment verification is complete (outside DB context to avoid SQLite lock)
    try:
        ComplianceEngine.evaluate_candidate(record["candidate_id"])
    except Exception as e:
        logger.warning(f"Failed to re-evaluate compliance after employment verification: {e}")

    return {
        "success": True,
        "status": status,
        "message": "Thank you for verifying this employment record. Your response has been recorded.",
    }


@router.post("/submit/reference")
async def submit_reference_verification(body: ReferenceSubmission, request: Request):
    """Submit a reference response via the portal."""
    record, record_type = _lookup_by_code(body.code)
    if not record:
        raise HTTPException(status_code=404, detail="Verification code not found")
    if record_type != "reference":
        raise HTTPException(status_code=400, detail="This code is for an employment verification, not a reference request")

    completed_statuses = ("verified", "completed", "disputed", "flagged")
    if record.get("status") in completed_statuses:
        raise HTTPException(status_code=400, detail="This reference has already been submitted")

    now = datetime.now(timezone.utc).isoformat()
    ip_address = request.client.host if request.client else None

    responses = {
        "performance_rating": body.performance_rating,
        "conduct_rating": body.conduct_rating,
        "reliability_rating": body.reliability_rating,
        "would_rehire": body.would_rehire,
        "relationship_to_candidate": body.relationship_to_candidate,
        "known_since": body.known_since,
        "strengths": body.strengths,
        "areas_for_improvement": body.areas_for_improvement,
        "additional_comments": body.additional_comments,
        "responder_name": body.responder_name,
        "responder_job_title": body.responder_job_title,
    }

    # Sentiment analysis
    sentiment = _simple_sentiment(responses)

    # Fraud detection
    fraud_flags = []
    if record.get("sent_at"):
        try:
            sent_dt = datetime.fromisoformat(record["sent_at"])
            if sent_dt.tzinfo is None:
                sent_dt = sent_dt.replace(tzinfo=timezone.utc)
            elapsed = (datetime.now(timezone.utc) - sent_dt).total_seconds()
            if elapsed < 60:
                fraud_flags.append({
                    "type": "suspicious_timing",
                    "detail": f"Reference completed in {elapsed:.0f} seconds — unusually fast",
                })
        except (ValueError, TypeError):
            pass

    if body.additional_comments and len(body.additional_comments) < 10:
        fraud_flags.append({
            "type": "generic_response",
            "detail": "Response appears generic/minimal",
        })

    status = "completed"
    if fraud_flags:
        status = "flagged"

    with get_db() as db:
        db.execute(
            """UPDATE references_ SET
               status=%s, responses=%s, sentiment_score=%s,
               fraud_flags=%s, ip_address=%s, completed_at=%s
               WHERE verification_code=%s""",
            (
                status,
                json.dumps(responses),
                sentiment,
                json.dumps(fraud_flags) if fraud_flags else None,
                ip_address,
                now,
                body.code.strip().upper(),
            ),
        )

        # Audit log
        db.execute(
            """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
               VALUES (%s, 'reference', %s, 'portal_submitted', 'referee', %s, %s)""",
            (
                generate_id(), record["id"],
                json.dumps({
                    "ip": ip_address,
                    "sentiment": sentiment,
                    "responder_name": body.responder_name,
                }),
                now,
            ),
        )

        # Create fraud alert if flagged
        if fraud_flags:
            db.execute(
                """INSERT INTO monitoring_alerts
                   (id, candidate_id, alert_type, severity, message, details, created_at)
                   VALUES (%s, %s, 'reference_fraud', 'high', %s, %s, %s)""",
                (
                    generate_id(), record["candidate_id"],
                    f"Reference fraud flags detected via portal for {record.get('referee_name', 'unknown')}",
                    json.dumps(fraud_flags),
                    now,
                ),
            )

    # Re-evaluate compliance now that reference is complete (outside DB context to avoid SQLite lock)
    try:
        ComplianceEngine.evaluate_candidate(record["candidate_id"])
    except Exception as e:
        logger.warning(f"Failed to re-evaluate compliance after reference submission: {e}")

    # Run AI-powered reference sentiment analysis (OpenAI if key configured, else rule-based)
    try:
        from app.services.ai_reference_sentiment import analyse_reference
        ref_data = {**responses, "candidate_id": record.get("candidate_id", "")}
        analyse_reference(record["id"], ref_data)
        logger.info("AI reference sentiment analysis completed for reference %s", record["id"])
    except Exception as e:
        logger.warning("AI reference sentiment analysis failed for reference %s: %s", record["id"], e)

    return {
        "success": True,
        "status": status,
        "message": "Thank you for providing this reference. Your response has been recorded securely.",
    }


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_candidate_name(candidate_id: str) -> str:
    if not candidate_id:
        return "Unknown"
    try:
        with get_db() as db:
            db.execute(
                "SELECT first_name, last_name FROM candidates WHERE id=%s",
                (candidate_id,),
            )
            row = db.fetchone()
            if row:
                return f"{row['first_name']} {row['last_name']}"
    except Exception:
        pass
    return "Unknown"


def _get_employment_job_title(employment_id: str) -> str:
    if not employment_id:
        return ""
    try:
        with get_db() as db:
            db.execute(
                "SELECT job_title FROM employment_history WHERE id=%s",
                (employment_id,),
            )
            row = db.fetchone()
            if row:
                return row["job_title"]
    except Exception:
        pass
    return ""


def _get_employment_dates(employment_id: str, field: str) -> str:
    if not employment_id:
        return ""
    try:
        with get_db() as db:
            db.execute(
                f"SELECT {field} FROM employment_history WHERE id=%s",
                (employment_id,),
            )
            row = db.fetchone()
            if row:
                return row[field] or ""
    except Exception:
        pass
    return ""


def _simple_sentiment(responses: dict) -> float:
    """Simple sentiment scoring from reference responses. Returns 0.0-1.0."""
    score = 0.5
    # Ratings may be None when suppressed pre-launch — default to neutral (3)
    perf = responses.get("performance_rating") or 3
    cond = responses.get("conduct_rating") or 3
    reli = responses.get("reliability_rating") or 3
    avg_rating = (perf + cond + reli) / 3.0

    # Map 1-5 average to score adjustment
    score += (avg_rating - 3) * 0.15

    if responses.get("would_rehire"):
        score += 0.15

    # Text analysis
    text = json.dumps(responses).lower()
    positive_signals = ["excellent", "outstanding", "highly recommend", "exceptional", "strong", "reliable"]
    negative_signals = ["concern", "poor", "unreliable", "issues", "not recommend", "weak"]
    for signal in positive_signals:
        if signal in text:
            score += 0.05
    for signal in negative_signals:
        if signal in text:
            score -= 0.1

    return min(max(round(score, 2), 0.0), 1.0)
