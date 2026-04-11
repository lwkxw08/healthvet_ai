"""4.3.1 AI-Powered CV Gap Analysis with LLM (OpenAI + rule-based fallback)."""
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.utils.auth import generate_id


def _get_openai_client():
    """Return an OpenAI client if the API key is configured, else None."""
    from app.routes.email_config import get_openai_api_key
    api_key = get_openai_api_key()
    if not api_key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=api_key)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Rule-based fallback (no LLM needed)
# ---------------------------------------------------------------------------

def _extract_dates_from_text(text: str) -> list[dict]:
    """Extract employment date ranges from CV text using regex."""
    patterns = [
        # "Jan 2020 - Dec 2022", "January 2020 to December 2022"
        r"(\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4})\s*[-–to]+\s*(\b(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|Aug(?:ust)?|Sep(?:tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)\s+\d{4}|[Pp]resent|[Cc]urrent)",
        # "2020-2022", "2019 - 2021"
        r"(\b\d{4})\s*[-–to]+\s*(\d{4}|[Pp]resent|[Cc]urrent)",
        # "MM/YYYY - MM/YYYY"
        r"(\d{1,2}/\d{4})\s*[-–to]+\s*(\d{1,2}/\d{4}|[Pp]resent|[Cc]urrent)",
    ]
    ranges = []
    for pattern in patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            ranges.append({"start": m.group(1).strip(), "end": m.group(2).strip()})
    return ranges


def _parse_date_approx(date_str: str) -> Optional[datetime]:
    """Best-effort parse of a date string into a datetime."""
    date_str = date_str.strip()
    if date_str.lower() in ("present", "current"):
        return datetime.now(timezone.utc)
    for fmt in ("%B %Y", "%b %Y", "%m/%Y", "%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None


def _rule_based_gap_analysis(cv_text: str) -> dict:
    """Analyse CV text for gaps using regex date extraction."""
    date_ranges = _extract_dates_from_text(cv_text)
    parsed = []
    for dr in date_ranges:
        start = _parse_date_approx(dr["start"])
        end = _parse_date_approx(dr["end"])
        if start and end:
            parsed.append({"start": start, "end": end, "raw_start": dr["start"], "raw_end": dr["end"]})

    # Sort by start date
    parsed.sort(key=lambda x: x["start"])

    gaps = []
    overlaps = []
    for i in range(len(parsed) - 1):
        curr_end = parsed[i]["end"]
        next_start = parsed[i + 1]["start"]
        diff_days = (next_start - curr_end).days
        if diff_days > 90:  # Gap > 3 months
            gaps.append({
                "from": parsed[i]["raw_end"],
                "to": parsed[i + 1]["raw_start"],
                "gap_months": round(diff_days / 30),
                "severity": "high" if diff_days > 365 else ("medium" if diff_days > 180 else "low"),
            })
        elif diff_days < -30:  # Overlap > 1 month
            overlaps.append({
                "period_1_end": parsed[i]["raw_end"],
                "period_2_start": parsed[i + 1]["raw_start"],
                "overlap_months": round(abs(diff_days) / 30),
            })

    # Check for vague descriptions
    vague_indicators = ["various duties", "general responsibilities", "etc.", "and more", "various roles"]
    vague_flags = []
    for indicator in vague_indicators:
        if indicator.lower() in cv_text.lower():
            vague_flags.append(indicator)

    # Short tenure detection (< 6 months)
    short_tenures = []
    for p in parsed:
        tenure_days = (p["end"] - p["start"]).days
        if 0 < tenure_days < 180:
            short_tenures.append({
                "period": f"{p['raw_start']} - {p['raw_end']}",
                "tenure_months": round(tenure_days / 30),
            })

    risk_flags = []
    if gaps:
        risk_flags.append({"type": "employment_gaps", "count": len(gaps), "severity": "high" if any(g["severity"] == "high" for g in gaps) else "medium"})
    if overlaps:
        risk_flags.append({"type": "overlapping_dates", "count": len(overlaps), "severity": "medium"})
    if vague_flags:
        risk_flags.append({"type": "vague_descriptions", "indicators": vague_flags, "severity": "low"})
    if len(short_tenures) >= 3:
        risk_flags.append({"type": "frequent_job_changes", "count": len(short_tenures), "severity": "medium"})

    overall_risk = "low"
    if any(f.get("severity") == "high" for f in risk_flags):
        overall_risk = "high"
    elif any(f.get("severity") == "medium" for f in risk_flags):
        overall_risk = "medium"

    return {
        "method": "rule_based",
        "employment_periods_detected": len(parsed),
        "gaps": gaps,
        "overlaps": overlaps,
        "short_tenures": short_tenures,
        "vague_descriptions": vague_flags,
        "risk_flags": risk_flags,
        "overall_risk": overall_risk,
        "recommendations": _build_recommendations(gaps, overlaps, short_tenures, vague_flags),
    }


def _build_recommendations(gaps: list, overlaps: list, short_tenures: list, vague_flags: list) -> list[str]:
    recs = []
    if gaps:
        recs.append(f"Request explanation for {len(gaps)} employment gap(s) totalling approximately {sum(g['gap_months'] for g in gaps)} months.")
    if overlaps:
        recs.append(f"Clarify {len(overlaps)} overlapping employment period(s) — may indicate dual employment or date errors.")
    if len(short_tenures) >= 3:
        recs.append(f"Pattern of short tenures detected ({len(short_tenures)} roles under 6 months). Consider discussing career stability.")
    if vague_flags:
        recs.append("CV contains vague descriptions. Request specific duties and achievements for key roles.")
    if not recs:
        recs.append("No significant concerns detected. CV employment history appears consistent.")
    return recs


# ---------------------------------------------------------------------------
# LLM-powered analysis (OpenAI)
# ---------------------------------------------------------------------------

_CV_ANALYSIS_PROMPT = """You are an expert HR compliance analyst for healthcare staffing in the UK. Analyse this CV text and provide a structured gap analysis.

Focus on:
1. Employment gaps (periods >3 months without stated employment)
2. Role progression (does the career path make sense for healthcare%s)
3. Qualification mismatches (certifications that don't align with roles claimed)
4. Date inconsistencies (overlapping employment, impossible timelines)
5. Red flags for healthcare compliance (expired registrations mentioned, disciplinary hints)
6. Vague or suspicious descriptions

CV TEXT:
---
{cv_text}
---

Respond ONLY with valid JSON in this exact structure:
{{
  "employment_periods": [
    {{"role": "...", "employer": "...", "start": "...", "end": "...", "tenure_months": N}}
  ],
  "gaps": [
    {{"from": "...", "to": "...", "gap_months": N, "severity": "high|medium|low", "possible_explanation": "..."}}
  ],
  "overlaps": [
    {{"period_1": "...", "period_2": "...", "overlap_months": N}}
  ],
  "role_progression": {{
    "assessment": "logical|concerning|unclear",
    "notes": "..."
  }},
  "qualification_concerns": [
    {{"concern": "...", "severity": "high|medium|low"}}
  ],
  "red_flags": [
    {{"type": "...", "detail": "...", "severity": "high|medium|low"}}
  ],
  "overall_risk": "low|medium|high",
  "summary": "2-3 sentence executive summary",
  "recommendations": ["..."]
}}"""


def _llm_cv_analysis(cv_text: str) -> Optional[dict]:
    """Run CV gap analysis via OpenAI."""
    client = _get_openai_client()
    if not client:
        return None
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a healthcare compliance CV analyst. Always respond with valid JSON only."},
                {"role": "user", "content": _CV_ANALYSIS_PROMPT.format(cv_text=cv_text[:8000])},
            ],
            temperature=0.2,
            max_tokens=2000,
        )
        content = response.choices[0].message.content or ""
        # Strip markdown code fences if present
        content = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content.strip())
        return json.loads(content)
    except Exception as e:
        return {"error": str(e), "method": "llm_failed"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_cv(candidate_id: str, cv_text: str, cv_analysis_id: Optional[str] = None) -> dict:
    """Run CV gap analysis — tries LLM first, falls back to rule-based."""
    # Try LLM first
    llm_result = _llm_cv_analysis(cv_text)

    if llm_result and "error" not in llm_result:
        result = llm_result
        result["method"] = "openai_gpt4o_mini"
    else:
        result = _rule_based_gap_analysis(cv_text)
        if llm_result and "error" in llm_result:
            result["llm_error"] = llm_result["error"]

    # Store the analysis
    analysis_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS ai_cv_gap_analyses (
            id TEXT PRIMARY KEY,
            candidate_id TEXT NOT NULL,
            cv_analysis_id TEXT,
            method TEXT NOT NULL,
            overall_risk TEXT,
            gaps_count INTEGER DEFAULT 0,
            overlaps_count INTEGER DEFAULT 0,
            red_flags_count INTEGER DEFAULT 0,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (candidate_id) REFERENCES candidates(id)
        )""")
        db.execute(
            "INSERT INTO ai_cv_gap_analyses (id, candidate_id, cv_analysis_id, method, overall_risk, gaps_count, overlaps_count, red_flags_count, result_json, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                analysis_id, candidate_id, cv_analysis_id,
                result.get("method", "unknown"),
                result.get("overall_risk", "unknown"),
                len(result.get("gaps", [])),
                len(result.get("overlaps", [])),
                len(result.get("red_flags", result.get("risk_flags", []))),
                json.dumps(result),
                now,
            ),
        )

    return {"id": analysis_id, "candidate_id": candidate_id, "created_at": now, **result}


def get_cv_analyses(candidate_id: str) -> list[dict]:
    """Get all AI CV gap analyses for a candidate."""
    with get_db() as db:
        try:
            rows = db.execute(
                "SELECT * FROM ai_cv_gap_analyses WHERE candidate_id=%s ORDER BY created_at DESC",
                (candidate_id,),
            ).fetchall()
            results = []
            for r in rows:
                d = dict(r)
                try:
                    d["result"] = json.loads(d.pop("result_json", "{}"))
                except Exception:
                    d["result"] = {}
                results.append(d)
            return results
        except Exception:
            return []
