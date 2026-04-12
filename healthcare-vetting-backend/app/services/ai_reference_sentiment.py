"""4.3.2 AI-Powered Reference Sentiment Analysis (OpenAI + rule-based fallback)."""
import json
import os
import re
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.utils.auth import generate_id


def _get_openai_client():
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
# Rule-based fallback
# ---------------------------------------------------------------------------

_POSITIVE_WORDS = {
    "excellent", "outstanding", "exceptional", "dedicated", "reliable", "punctual",
    "compassionate", "thorough", "professional", "diligent", "hardworking", "skilled",
    "competent", "trustworthy", "proactive", "enthusiastic", "capable", "committed",
    "organised", "efficient", "caring", "attentive", "exemplary", "superb", "fantastic",
}

_NEGATIVE_WORDS = {
    "poor", "unreliable", "late", "absent", "lazy", "careless", "negligent", "rude",
    "unprofessional", "incompetent", "dishonest", "disruptive", "aggressive",
    "underperforming", "inadequate", "problematic", "difficult", "complaints",
    "disciplinary", "terminated", "dismissed", "fired", "concern", "concerning",
}

_EVASIVE_PHRASES = [
    "no comment", "prefer not to say", "unable to comment", "cannot comment",
    "i'd rather not", "not in a position to", "declined to answer", "n/a",
    "no further comment", "i can confirm dates only", "company policy prevents",
]

_RED_FLAG_PHRASES = [
    "would not rehire", "not recommend", "wouldn't recommend", "do not recommend",
    "left under", "circumstances surrounding", "mutual agreement to leave",
    "performance concerns", "investigation", "suspended", "formal warning",
    "capability proceedings", "fitness to practise",
]

_GENERIC_PHRASES = [
    "good employee", "no issues", "fine worker", "satisfactory performance",
    "nothing to report", "adequate", "met expectations",
]


def _rule_based_sentiment(reference_data: dict) -> dict:
    """Analyse reference text using word-matching and pattern detection."""
    text_fields = []
    for key in ("strengths", "improvements", "additional_comments", "comments",
                "reason_for_leaving", "additional_context"):
        val = reference_data.get(key, "")
        if val:
            text_fields.append(str(val))
    combined_text = " ".join(text_fields).lower()

    # Count positive/negative words
    pos_count = sum(1 for w in _POSITIVE_WORDS if w in combined_text)
    neg_count = sum(1 for w in _NEGATIVE_WORDS if w in combined_text)

    # Detect evasive language
    evasive = [p for p in _EVASIVE_PHRASES if p in combined_text]

    # Detect red flags
    red_flags = [p for p in _RED_FLAG_PHRASES if p in combined_text]

    # Detect generic/low-effort responses
    generic = [p for p in _GENERIC_PHRASES if p in combined_text]

    # Ratings analysis
    ratings = {}
    for key in ("performance_rating", "conduct_rating", "reliability_rating"):
        val = reference_data.get(key)
        if val is not None:
            try:
                ratings[key] = float(val)
            except (ValueError, TypeError):
                pass

    avg_rating = sum(ratings.values()) / len(ratings) if ratings else None

    # Would rehire signal
    would_rehire = reference_data.get("would_rehire")

    # Calculate sentiment score (0.0 - 1.0)
    score = 0.5  # neutral baseline
    if avg_rating is not None:
        score = avg_rating / 5.0  # normalise 1-5 to 0.0-1.0
    else:
        # Text-based scoring
        total_words = pos_count + neg_count
        if total_words > 0:
            score = pos_count / total_words

    # Adjust for signals
    if would_rehire is False or str(would_rehire).lower() == "false":
        score = max(0.0, score - 0.2)
    if red_flags:
        score = max(0.0, score - 0.15 * len(red_flags))
    if evasive:
        score = max(0.0, score - 0.1)

    # Rating vs text consistency check
    inconsistencies = []
    if avg_rating and avg_rating >= 4.0 and neg_count > pos_count:
        inconsistencies.append("High ratings but predominantly negative text — possible reluctant reference.")
    if avg_rating and avg_rating <= 2.5 and pos_count > neg_count:
        inconsistencies.append("Low ratings but positive text — may indicate mixed feelings or rating error.")
    if would_rehire is False and avg_rating and avg_rating >= 4.0:
        inconsistencies.append("Would not rehire despite high ratings — significant red flag.")

    # Determine overall assessment
    if score >= 0.75:
        assessment = "positive"
    elif score >= 0.5:
        assessment = "neutral"
    elif score >= 0.3:
        assessment = "concerning"
    else:
        assessment = "negative"

    if red_flags:
        assessment = "concerning" if assessment == "neutral" else assessment

    concerns = []
    if evasive:
        concerns.append({"type": "evasive_language", "detail": f"Detected evasive phrases: {', '.join(evasive)}", "severity": "medium"})
    if red_flags:
        concerns.append({"type": "red_flag_language", "detail": f"Red flag phrases detected: {', '.join(red_flags)}", "severity": "high"})
    if generic:
        concerns.append({"type": "generic_response", "detail": f"Generic/low-effort phrases: {', '.join(generic)}", "severity": "low"})
    if inconsistencies:
        for inc in inconsistencies:
            concerns.append({"type": "inconsistency", "detail": inc, "severity": "high"})

    return {
        "method": "rule_based",
        "sentiment_score": round(score, 3),
        "assessment": assessment,
        "positive_indicators": pos_count,
        "negative_indicators": neg_count,
        "evasive_language": evasive,
        "red_flags": red_flags,
        "generic_phrases": generic,
        "inconsistencies": inconsistencies,
        "concerns": concerns,
        "ratings_analysis": {
            "individual_ratings": ratings,
            "average_rating": round(avg_rating, 2) if avg_rating else None,
            "would_rehire": would_rehire,
        },
        "word_count": len(combined_text.split()),
        "recommendations": _build_ref_recommendations(evasive, red_flags, generic, inconsistencies, score),
    }


def _build_ref_recommendations(evasive, red_flags, generic, inconsistencies, score):
    recs = []
    if red_flags:
        recs.append("Investigate red flag language — consider requesting a follow-up call with the referee.")
    if evasive:
        recs.append("Referee used evasive language. Contact directly by phone for clarification.")
    if inconsistencies:
        recs.append("Inconsistency detected between ratings and text. Flag for manual review.")
    if generic:
        recs.append("Response appears generic/low-effort. Consider requesting a more detailed reference.")
    if score < 0.3:
        recs.append("Overall negative sentiment. Recommend additional reference check from a different referee.")
    if not recs:
        recs.append("Reference appears consistent and positive. No additional action required.")
    return recs


# ---------------------------------------------------------------------------
# LLM-powered analysis
# ---------------------------------------------------------------------------

_REF_ANALYSIS_PROMPT = """You are an expert HR compliance analyst specialising in reference analysis for UK healthcare staffing. Analyse this reference response and provide a detailed sentiment analysis.

Focus on:
1. Overall sentiment and tone
2. Evasive or deliberately vague language
3. Hidden red flags (negative sentiments disguised in neutral/positive language)
4. Consistency between numerical ratings and written comments
5. Whether the referee appears genuinely supportive or giving a reluctant reference
6. Healthcare-specific concerns (patient safety, clinical competence, safeguarding)

REFERENCE DATA:
---
{reference_json}
---

Respond ONLY with valid JSON:
{{
  "sentiment_score": 0.0-1.0,
  "assessment": "positive|neutral|concerning|negative",
  "tone_analysis": "genuinely_supportive|politely_neutral|reluctant|evasive|negative",
  "key_themes": ["..."],
  "concerns": [
    {{"type": "...", "detail": "...", "severity": "high|medium|low"}}
  ],
  "strengths_noted": ["..."],
  "areas_of_concern": ["..."],
  "consistency_check": {{
    "ratings_vs_text": "consistent|inconsistent",
    "detail": "..."
  }},
  "healthcare_specific": {{
    "patient_safety_indicators": "positive|neutral|concerning|not_mentioned",
    "clinical_competence": "positive|neutral|concerning|not_mentioned",
    "safeguarding_awareness": "positive|neutral|concerning|not_mentioned"
  }},
  "summary": "2-3 sentence executive summary",
  "recommendations": ["..."]
}}"""


def _llm_reference_analysis(reference_data: dict) -> Optional[dict]:
    """Run reference sentiment analysis via OpenAI."""
    client = _get_openai_client()
    if not client:
        return None
    try:
        ref_json = json.dumps(reference_data, indent=2, default=str)
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a healthcare reference analysis expert. Always respond with valid JSON only."},
                {"role": "user", "content": _REF_ANALYSIS_PROMPT.format(reference_json=ref_json[:6000])},
            ],
            temperature=0.2,
            max_tokens=1500,
        )
        content = response.choices[0].message.content or ""
        content = re.sub(r"^```(?:json)?\s*", "", content.strip())
        content = re.sub(r"\s*```$", "", content.strip())
        return json.loads(content)
    except Exception as e:
        return {"error": str(e), "method": "llm_failed"}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyse_reference(reference_id: str, reference_data: dict) -> dict:
    """Run reference sentiment analysis — tries LLM first, falls back to rule-based."""
    llm_result = _llm_reference_analysis(reference_data)

    if llm_result and "error" not in llm_result:
        result = llm_result
        result["method"] = "openai_gpt4o_mini"
    else:
        result = _rule_based_sentiment(reference_data)
        if llm_result and "error" in llm_result:
            result["llm_error"] = llm_result["error"]

    # Store the analysis
    analysis_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    candidate_id = reference_data.get("candidate_id", "")

    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS ai_reference_analyses (
            id TEXT PRIMARY KEY,
            reference_id TEXT NOT NULL,
            candidate_id TEXT,
            method TEXT NOT NULL,
            sentiment_score REAL,
            assessment TEXT,
            concerns_count INTEGER DEFAULT 0,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute(
            "INSERT INTO ai_reference_analyses (id, reference_id, candidate_id, method, sentiment_score, assessment, concerns_count, result_json, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                analysis_id, reference_id, candidate_id,
                result.get("method", "unknown"),
                result.get("sentiment_score", 0),
                result.get("assessment", "unknown"),
                len(result.get("concerns", [])),
                json.dumps(result),
                now,
            ),
        )

    return {"id": analysis_id, "reference_id": reference_id, "created_at": now, **result}


def get_reference_analyses(candidate_id: Optional[str] = None, reference_id: Optional[str] = None) -> list[dict]:
    """Get AI reference analyses filtered by candidate or reference."""
    with get_db() as db:
        try:
            if reference_id:
                rows = db.execute(
                    "SELECT * FROM ai_reference_analyses WHERE reference_id=%s ORDER BY created_at DESC",
                    (reference_id,),
                )
                rows = db.fetchall()
            elif candidate_id:
                rows = db.execute(
                    "SELECT * FROM ai_reference_analyses WHERE candidate_id=%s ORDER BY created_at DESC",
                    (candidate_id,),
                )
                rows = db.fetchall()
            else:
                db.execute("SELECT * FROM ai_reference_analyses ORDER BY created_at DESC LIMIT 50")
                rows = db.fetchall()
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
