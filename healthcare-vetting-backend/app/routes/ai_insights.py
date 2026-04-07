"""4.3 AI-Powered Features: CV gap analysis, reference sentiment, anomaly detection, smart scheduling."""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Optional

from app.utils.auth import get_current_user

router = APIRouter(prefix="/api/ai", tags=["AI Insights"])


# --------------- Request schemas ---------------

class CvAnalysisRequest(BaseModel):
    candidate_id: str
    cv_text: str
    cv_analysis_id: Optional[str] = None


class ReferenceAnalysisRequest(BaseModel):
    reference_id: str
    reference_data: dict


# --------------- CV Gap Analysis ---------------

@router.post("/cv-gap-analysis")
async def run_cv_gap_analysis(body: CvAnalysisRequest, current_user: dict = Depends(get_current_user)):
    """Run AI-powered CV gap analysis for a candidate."""
    if current_user.get("type") not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Admin or agency access required")
    from app.services.ai_cv_analysis import analyse_cv
    result = analyse_cv(body.candidate_id, body.cv_text, body.cv_analysis_id)
    return result


@router.get("/cv-gap-analysis/{candidate_id}")
async def get_cv_gap_analyses(candidate_id: str, current_user: dict = Depends(get_current_user)):
    """Get all AI CV gap analyses for a candidate."""
    if current_user.get("type") not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Admin or agency access required")
    from app.services.ai_cv_analysis import get_cv_analyses
    return {"analyses": get_cv_analyses(candidate_id)}


# --------------- Reference Sentiment Analysis ---------------

@router.post("/reference-sentiment")
async def run_reference_sentiment(body: ReferenceAnalysisRequest, current_user: dict = Depends(get_current_user)):
    """Run AI-powered reference sentiment analysis."""
    if current_user.get("type") not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Admin or agency access required")
    from app.services.ai_reference_sentiment import analyse_reference
    result = analyse_reference(body.reference_id, body.reference_data)
    return result


@router.get("/reference-sentiment")
async def get_reference_sentiments(
    candidate_id: Optional[str] = None,
    reference_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get AI reference sentiment analyses."""
    if current_user.get("type") not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Admin or agency access required")
    from app.services.ai_reference_sentiment import get_reference_analyses
    return {"analyses": get_reference_analyses(candidate_id=candidate_id, reference_id=reference_id)}


# --------------- Anomaly Detection ---------------

@router.post("/anomaly-scan")
async def run_anomaly_scan(
    request: Request,
    agency_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Run anomaly detection scan across verifications."""
    if current_user.get("type") not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Admin or agency access required")
    # Agency users can only scan their own data
    if current_user.get("type") == "agency":
        agency_id = current_user.get("sub")
    from app.services.ai_anomaly_detection import detect_anomalies
    result = detect_anomalies(agency_id=agency_id)
    return result


@router.get("/anomaly-history")
async def get_anomaly_scan_history(
    agency_id: Optional[str] = None,
    limit: int = 20,
    current_user: dict = Depends(get_current_user),
):
    """Get historical anomaly scan results."""
    if current_user.get("type") not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Admin or agency access required")
    if current_user.get("type") == "agency":
        agency_id = current_user.get("sub")
    from app.services.ai_anomaly_detection import get_anomaly_history
    return {"scans": get_anomaly_history(agency_id=agency_id, limit=limit)}


# --------------- Smart Scheduling ---------------

@router.get("/smart-scheduling")
async def get_smart_schedule(
    agency_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get smart follow-up scheduling recommendations based on historical patterns."""
    if current_user.get("type") not in ("admin", "agency"):
        raise HTTPException(status_code=403, detail="Admin or agency access required")
    if current_user.get("type") == "agency":
        agency_id = current_user.get("sub")
    from app.services.ai_smart_scheduling import analyse_response_patterns
    result = analyse_response_patterns(agency_id=agency_id)
    return result


# --------------- AI Config / Status ---------------

@router.get("/status")
async def ai_status(current_user: dict = Depends(get_current_user)):
    """Check AI feature availability (which providers are configured)."""
    from app.routes.email_config import get_openai_api_key
    openai_key = get_openai_api_key()
    return {
        "openai_configured": bool(openai_key),
        "openai_model": "gpt-4o-mini" if openai_key else None,
        "features": {
            "cv_gap_analysis": {"available": True, "method": "openai" if openai_key else "rule_based"},
            "reference_sentiment": {"available": True, "method": "openai" if openai_key else "rule_based"},
            "anomaly_detection": {"available": True, "method": "statistical"},
            "smart_scheduling": {"available": True, "method": "statistical"},
        },
    }
