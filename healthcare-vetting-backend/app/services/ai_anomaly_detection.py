"""4.3.3 Anomaly Detection in Verification Patterns (no LLM needed)."""
import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from app.database import get_db
from app.utils.auth import generate_id


def detect_anomalies(agency_id: Optional[str] = None) -> dict:
    """Scan all verifications for anomalous patterns. Returns flagged items."""
    anomalies: list[dict] = []
    stats = {
        "total_verifications_scanned": 0,
        "total_references_scanned": 0,
        "anomalies_found": 0,
    }

    with get_db() as db:
        # ---- Employment verifications ----
        if agency_id:
            db.execute("""
                SELECT ev.*, c.email as candidate_email, c.first_name, c.last_name
                FROM employment_verifications ev
                LEFT JOIN candidates c ON c.id = ev.candidate_id
                LEFT JOIN agency_candidates ac ON ac.candidate_id = ev.candidate_id
                WHERE ac.agency_id = %s
                ORDER BY ev.sent_at DESC
            """, (agency_id,))
            emp_rows = db.fetchall()
        else:
            db.execute("""
                SELECT ev.*, c.email as candidate_email, c.first_name, c.last_name
                FROM employment_verifications ev
                LEFT JOIN candidates c ON c.id = ev.candidate_id
                ORDER BY ev.sent_at DESC
            """)
            emp_rows = db.fetchall()

        emp_list = [dict(r) for r in emp_rows] if emp_rows else []
        stats["total_verifications_scanned"] = len(emp_list)

        # ---- References ----
        if agency_id:
            db.execute("""
                SELECT r.*, c.email as candidate_email, c.first_name, c.last_name
                FROM references_ r
                LEFT JOIN candidates c ON c.id = r.candidate_id
                LEFT JOIN agency_candidates ac ON ac.candidate_id = r.candidate_id
                WHERE ac.agency_id = %s
                ORDER BY r.created_at DESC
            """, (agency_id,))
            ref_rows = db.fetchall()
        else:
            db.execute("""
                SELECT r.*, c.email as candidate_email, c.first_name, c.last_name
                FROM references_ r
                LEFT JOIN candidates c ON c.id = r.candidate_id
                ORDER BY r.created_at DESC
            """)
            ref_rows = db.fetchall()

        ref_list = [dict(r) for r in ref_rows] if ref_rows else []
        stats["total_references_scanned"] = len(ref_list)

        # ---- Anomaly 1: Rapid responses (< 60 seconds) ----
        for ev in emp_list:
            sent = ev.get("sent_at")
            completed = ev.get("completed_at")
            if sent and completed:
                try:
                    sent_dt = datetime.fromisoformat(sent.replace("Z", "+00:00"))
                    comp_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                    diff_secs = (comp_dt - sent_dt).total_seconds()
                    if 0 < diff_secs < 60:
                        anomalies.append({
                            "type": "rapid_response",
                            "severity": "high",
                            "entity_type": "employment_verification",
                            "entity_id": ev.get("id"),
                            "candidate_id": ev.get("candidate_id"),
                            "candidate_name": f"{ev.get('first_name', '')} {ev.get('last_name', '')}".strip(),
                            "detail": f"Verification completed in {int(diff_secs)}s after being sent. Normal response time is hours/days.",
                            "value": int(diff_secs),
                        })
                except (ValueError, TypeError):
                    pass

        # ---- Anomaly 2: Same IP across different verifiers ----
        ip_to_verifications: dict[str, list[dict]] = defaultdict(list)
        for ev in emp_list:
            ip = ev.get("ip_address")
            if ip and ip not in ("", "unknown"):
                ip_to_verifications[ip].append(ev)

        for ip, items in ip_to_verifications.items():
            if len(items) >= 2:
                # Different verifier emails from same IP
                verifier_emails = set(item.get("verifier_email", "").lower() for item in items if item.get("verifier_email"))
                if len(verifier_emails) >= 2:
                    anomalies.append({
                        "type": "same_ip_multiple_verifiers",
                        "severity": "high",
                        "entity_type": "employment_verification",
                        "entity_ids": [item.get("id") for item in items],
                        "detail": f"IP address {ip} used by {len(verifier_emails)} different verifiers: {', '.join(verifier_emails)}. Could indicate candidate submitting own verifications.",
                        "ip_address": ip,
                        "verifier_emails": list(verifier_emails),
                    })

        # ---- Anomaly 3: Verifier email domain mismatch ----
        for ev in emp_list:
            verifier_email = ev.get("verifier_email", "")
            employer_name = ev.get("employer_name", "").lower()
            if verifier_email and employer_name:
                domain = verifier_email.split("@")[-1].lower() if "@" in verifier_email else ""
                # Flag if using free email (gmail, hotmail, yahoo, outlook) for employer verification
                free_domains = {"gmail.com", "hotmail.com", "yahoo.com", "outlook.com", "live.com", "aol.com", "icloud.com", "mail.com", "protonmail.com"}
                if domain in free_domains:
                    anomalies.append({
                        "type": "free_email_verifier",
                        "severity": "medium",
                        "entity_type": "employment_verification",
                        "entity_id": ev.get("id"),
                        "candidate_id": ev.get("candidate_id"),
                        "candidate_name": f"{ev.get('first_name', '')} {ev.get('last_name', '')}".strip(),
                        "detail": f"Verifier for '{employer_name}' is using personal email ({verifier_email}) instead of employer domain.",
                        "verifier_email": verifier_email,
                        "employer_name": employer_name,
                    })

        # ---- Anomaly 4: Similar language across different verifications ----
        comment_texts: list[tuple[str, dict]] = []
        for ev in emp_list:
            for field in ("additional_comments", "reason_for_leaving_confirmed"):
                val = ev.get(field, "")
                if val and len(str(val)) > 20:
                    comment_texts.append((str(val).lower().strip(), ev))

        # Simple Jaccard similarity for duplicate detection
        for i in range(len(comment_texts)):
            for j in range(i + 1, len(comment_texts)):
                text_a, ev_a = comment_texts[i]
                text_b, ev_b = comment_texts[j]
                if ev_a.get("candidate_id") == ev_b.get("candidate_id"):
                    continue  # Same candidate, not suspicious
                words_a = set(text_a.split())
                words_b = set(text_b.split())
                if not words_a or not words_b:
                    continue
                intersection = words_a & words_b
                union = words_a | words_b
                similarity = len(intersection) / len(union) if union else 0
                if similarity > 0.7 and len(words_a) > 5:
                    anomalies.append({
                        "type": "similar_language",
                        "severity": "medium",
                        "entity_type": "employment_verification",
                        "entity_ids": [ev_a.get("id"), ev_b.get("id")],
                        "detail": f"Very similar language ({int(similarity*100)}% overlap) in responses from different verifiers for different candidates.",
                        "similarity": round(similarity, 3),
                    })

        # ---- Anomaly 5: Unusual time-of-day responses ----
        for ev in emp_list:
            completed = ev.get("completed_at")
            if completed:
                try:
                    comp_dt = datetime.fromisoformat(completed.replace("Z", "+00:00"))
                    hour = comp_dt.hour
                    if 0 <= hour < 5:  # Midnight to 5am
                        anomalies.append({
                            "type": "unusual_response_time",
                            "severity": "low",
                            "entity_type": "employment_verification",
                            "entity_id": ev.get("id"),
                            "candidate_id": ev.get("candidate_id"),
                            "candidate_name": f"{ev.get('first_name', '')} {ev.get('last_name', '')}".strip(),
                            "detail": f"Verification completed at {comp_dt.strftime('%H:%M')} UTC. Unusual for a workplace verifier.",
                            "hour": hour,
                        })
                except (ValueError, TypeError):
                    pass

        # ---- Anomaly 6: Same verifier across multiple candidates ----
        verifier_to_candidates: dict[str, set[str]] = defaultdict(set)
        for ev in emp_list:
            verifier_email = ev.get("verifier_email", "").lower()
            candidate_id = ev.get("candidate_id", "")
            if verifier_email and candidate_id:
                verifier_to_candidates[verifier_email].add(candidate_id)

        for verifier, candidates in verifier_to_candidates.items():
            if len(candidates) >= 3:
                anomalies.append({
                    "type": "prolific_verifier",
                    "severity": "low",
                    "entity_type": "employment_verification",
                    "detail": f"Verifier {verifier} has verified {len(candidates)} different candidates. May be legitimate for large employers.",
                    "verifier_email": verifier,
                    "candidate_count": len(candidates),
                })

        # ---- Anomaly 7: Reference sentiment vs employment verification consistency ----
        # Check if same candidate has very different sentiments across references
        candidate_ref_sentiments: dict[str, list[float]] = defaultdict(list)
        for ref in ref_list:
            sentiment = ref.get("sentiment_score")
            candidate_id = ref.get("candidate_id")
            if sentiment is not None and candidate_id:
                try:
                    candidate_ref_sentiments[candidate_id].append(float(sentiment))
                except (ValueError, TypeError):
                    pass

        for cid, scores in candidate_ref_sentiments.items():
            if len(scores) >= 2:
                score_range = max(scores) - min(scores)
                if score_range > 0.5:
                    anomalies.append({
                        "type": "inconsistent_reference_sentiments",
                        "severity": "medium",
                        "entity_type": "reference",
                        "candidate_id": cid,
                        "detail": f"Large sentiment variation across references (range: {score_range:.2f}). Scores: {[round(s, 2) for s in scores]}",
                        "score_range": round(score_range, 3),
                        "scores": [round(s, 2) for s in scores],
                    })

    # Deduplicate by type+entity
    seen = set()
    unique_anomalies = []
    for a in anomalies:
        key = f"{a['type']}:{a.get('entity_id', '')}:{a.get('entity_ids', '')}"
        if key not in seen:
            seen.add(key)
            unique_anomalies.append(a)

    stats["anomalies_found"] = len(unique_anomalies)

    # Group by severity
    by_severity = {"high": [], "medium": [], "low": []}
    for a in unique_anomalies:
        by_severity.get(a.get("severity", "low"), by_severity["low"]).append(a)

    # Store the scan result
    scan_id = generate_id()
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS ai_anomaly_scans (
            id TEXT PRIMARY KEY,
            agency_id TEXT,
            total_scanned INTEGER DEFAULT 0,
            anomalies_found INTEGER DEFAULT 0,
            high_severity INTEGER DEFAULT 0,
            medium_severity INTEGER DEFAULT 0,
            low_severity INTEGER DEFAULT 0,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute(
            "INSERT INTO ai_anomaly_scans (id, agency_id, total_scanned, anomalies_found, high_severity, medium_severity, low_severity, result_json, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                scan_id, agency_id,
                stats["total_verifications_scanned"] + stats["total_references_scanned"],
                stats["anomalies_found"],
                len(by_severity["high"]),
                len(by_severity["medium"]),
                len(by_severity["low"]),
                json.dumps({"anomalies": unique_anomalies, "stats": stats}),
                now,
            ),
        )

    return {
        "id": scan_id,
        "created_at": now,
        "stats": stats,
        "by_severity": {k: len(v) for k, v in by_severity.items()},
        "anomalies": unique_anomalies,
    }


def get_anomaly_history(agency_id: Optional[str] = None, limit: int = 20) -> list[dict]:
    """Get historical anomaly scan results."""
    with get_db() as db:
        try:
            if agency_id:
                db.execute(
                    "SELECT id, agency_id, total_scanned, anomalies_found, high_severity, medium_severity, low_severity, created_at FROM ai_anomaly_scans WHERE agency_id=%s ORDER BY created_at DESC LIMIT %s",
                    (agency_id, limit),
                )
                rows = db.fetchall()
            else:
                db.execute(
                    "SELECT id, agency_id, total_scanned, anomalies_found, high_severity, medium_severity, low_severity, created_at FROM ai_anomaly_scans ORDER BY created_at DESC LIMIT %s",
                    (limit,),
                )
                rows = db.fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []
