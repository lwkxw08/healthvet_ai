"""4.3.4 Smart Scheduling for Verification Follow-ups (no LLM needed)."""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Optional

from app.database import get_db
from app.utils.auth import generate_id


def _parse_dt(val: Optional[str]) -> Optional[datetime]:
    if not val:
        return None
    try:
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def analyse_response_patterns(agency_id: Optional[str] = None) -> dict:
    """Analyse historical verification response patterns to optimise follow-up timing."""

    with get_db() as db:
        # ---- Employment verifications ----
        if agency_id:
            emp_rows = db.execute("""
                SELECT ev.*, c.email as candidate_email
                FROM employment_verifications ev
                LEFT JOIN candidates c ON c.id = ev.candidate_id
                LEFT JOIN agency_candidates ac ON ac.candidate_id = ev.candidate_id
                WHERE ac.agency_id = %s AND ev.completed_at IS NOT NULL
                ORDER BY ev.sent_at DESC
            """, (agency_id,)).fetchall()
        else:
            emp_rows = db.execute("""
                SELECT ev.*, c.email as candidate_email
                FROM employment_verifications ev
                LEFT JOIN candidates c ON c.id = ev.candidate_id
                WHERE ev.completed_at IS NOT NULL
                ORDER BY ev.sent_at DESC
            """).fetchall()

        emp_list = [dict(r) for r in emp_rows] if emp_rows else []

        # ---- References ----
        if agency_id:
            ref_rows = db.execute("""
                SELECT r.*, c.email as candidate_email
                FROM references_ r
                LEFT JOIN candidates c ON c.id = r.candidate_id
                LEFT JOIN agency_candidates ac ON ac.candidate_id = r.candidate_id
                WHERE ac.agency_id = %s AND r.status IN ('completed', 'verified')
                ORDER BY r.created_at DESC
            """, (agency_id,)).fetchall()
        else:
            ref_rows = db.execute("""
                SELECT r.*, c.email as candidate_email
                FROM references_ r
                LEFT JOIN candidates c ON c.id = r.candidate_id
                WHERE r.status IN ('completed', 'verified')
                ORDER BY r.created_at DESC
            """).fetchall()

        ref_list = [dict(r) for r in ref_rows] if ref_rows else []

        # ---- Pending verifications (need follow-up) ----
        if agency_id:
            pending_emp = db.execute("""
                SELECT ev.*, c.email as candidate_email, c.first_name, c.last_name
                FROM employment_verifications ev
                LEFT JOIN candidates c ON c.id = ev.candidate_id
                LEFT JOIN agency_candidates ac ON ac.candidate_id = ev.candidate_id
                WHERE ac.agency_id = %s AND ev.status IN ('pending', 'sent')
                ORDER BY ev.sent_at ASC
            """, (agency_id,)).fetchall()
            pending_ref = db.execute("""
                SELECT r.*, c.email as candidate_email, c.first_name, c.last_name
                FROM references_ r
                LEFT JOIN candidates c ON c.id = r.candidate_id
                LEFT JOIN agency_candidates ac ON ac.candidate_id = r.candidate_id
                WHERE ac.agency_id = %s AND r.status IN ('pending', 'sent')
                ORDER BY r.created_at ASC
            """, (agency_id,)).fetchall()
        else:
            pending_emp = db.execute("""
                SELECT ev.*, c.email as candidate_email, c.first_name, c.last_name
                FROM employment_verifications ev
                LEFT JOIN candidates c ON c.id = ev.candidate_id
                WHERE ev.status IN ('pending', 'sent')
                ORDER BY ev.sent_at ASC
            """).fetchall()
            pending_ref = db.execute("""
                SELECT r.*, c.email as candidate_email, c.first_name, c.last_name
                FROM references_ r
                LEFT JOIN candidates c ON c.id = r.candidate_id
                WHERE r.status IN ('pending', 'sent')
                ORDER BY r.created_at ASC
            """).fetchall()

        pending_emp_list = [dict(r) for r in pending_emp] if pending_emp else []
        pending_ref_list = [dict(r) for r in pending_ref] if pending_ref else []

    # ---- Analyse response times ----
    response_times_hours: list[float] = []
    by_day_of_week: dict[int, list[float]] = defaultdict(list)  # 0=Mon, 6=Sun
    by_hour_of_day: dict[int, int] = defaultdict(int)
    by_verifier_domain: dict[str, list[float]] = defaultdict(list)
    by_reminder_count: dict[int, list[float]] = defaultdict(list)

    for ev in emp_list:
        sent_dt = _parse_dt(ev.get("sent_at"))
        comp_dt = _parse_dt(ev.get("completed_at"))
        if sent_dt and comp_dt:
            hours = (comp_dt - sent_dt).total_seconds() / 3600
            if hours > 0:
                response_times_hours.append(hours)
                by_day_of_week[comp_dt.weekday()].append(hours)
                by_hour_of_day[comp_dt.hour] += 1
                # Domain analysis
                verifier_email = ev.get("verifier_email", "")
                if "@" in verifier_email:
                    domain = verifier_email.split("@")[-1].lower()
                    by_verifier_domain[domain].append(hours)
                # Reminder count analysis
                reminders = ev.get("reminder_count", 0) or 0
                by_reminder_count[reminders].append(hours)

    # Reference response times
    ref_response_times: list[float] = []
    for ref in ref_list:
        sent_dt = _parse_dt(ref.get("created_at"))
        comp_dt = _parse_dt(ref.get("completed_at"))
        if sent_dt and comp_dt:
            hours = (comp_dt - sent_dt).total_seconds() / 3600
            if hours > 0:
                ref_response_times.append(hours)

    # ---- Compute statistics ----
    def _stats(hours_list: list[float]) -> dict:
        if not hours_list:
            return {"count": 0, "avg_hours": None, "median_hours": None, "p75_hours": None, "p90_hours": None}
        sorted_h = sorted(hours_list)
        n = len(sorted_h)
        return {
            "count": n,
            "avg_hours": round(sum(sorted_h) / n, 1),
            "median_hours": round(sorted_h[n // 2], 1),
            "p75_hours": round(sorted_h[int(n * 0.75)], 1) if n > 3 else None,
            "p90_hours": round(sorted_h[int(n * 0.90)], 1) if n > 9 else None,
            "min_hours": round(sorted_h[0], 1),
            "max_hours": round(sorted_h[-1], 1),
        }

    emp_stats = _stats(response_times_hours)
    ref_stats = _stats(ref_response_times)

    # Best days to send (sorted by fastest avg response)
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    day_analysis = []
    for dow in range(7):
        times = by_day_of_week.get(dow, [])
        if times:
            day_analysis.append({
                "day": day_names[dow],
                "day_index": dow,
                "responses": len(times),
                "avg_hours": round(sum(times) / len(times), 1),
            })
    day_analysis.sort(key=lambda x: x["avg_hours"])

    # Peak response hours
    peak_hours = sorted(by_hour_of_day.items(), key=lambda x: x[1], reverse=True)[:5]
    peak_hour_analysis = [{"hour": h, "display": f"{h:02d}:00-{h+1:02d}:00", "responses": c} for h, c in peak_hours]

    # Domain performance
    domain_analysis = []
    for domain, times in sorted(by_verifier_domain.items(), key=lambda x: len(x[1]), reverse=True)[:10]:
        domain_analysis.append({
            "domain": domain,
            "verifications": len(times),
            "avg_hours": round(sum(times) / len(times), 1),
            "is_nhs": "nhs" in domain,
        })

    # Reminder effectiveness
    reminder_analysis = []
    for count, times in sorted(by_reminder_count.items()):
        reminder_analysis.append({
            "reminders_sent": count,
            "completions": len(times),
            "avg_hours": round(sum(times) / len(times), 1),
        })

    # ---- Generate smart follow-up schedule for pending items ----
    now = datetime.now(timezone.utc)
    default_first_reminder_hours = 72  # 3 days
    default_second_reminder_hours = 168  # 7 days
    default_escalation_hours = 336  # 14 days

    # Adjust based on data
    if emp_stats["avg_hours"]:
        avg_h = emp_stats["avg_hours"]
        first_reminder_hours = max(48, round(avg_h * 1.2))
        second_reminder_hours = max(96, round(avg_h * 2.0))
        escalation_hours = max(168, round(avg_h * 3.0))
    else:
        first_reminder_hours = default_first_reminder_hours
        second_reminder_hours = default_second_reminder_hours
        escalation_hours = default_escalation_hours

    # Optimal send time (most responses happen at this hour)
    optimal_hour = peak_hours[0][0] if peak_hours else 10  # Default 10am
    optimal_day = day_analysis[0]["day_index"] if day_analysis else 1  # Default Tuesday

    follow_ups: list[dict] = []
    for ev in pending_emp_list:
        sent_dt = _parse_dt(ev.get("sent_at"))
        if not sent_dt:
            continue
        hours_waiting = (now - sent_dt).total_seconds() / 3600
        reminders = ev.get("reminder_count", 0) or 0

        action = "wait"
        urgency = "low"
        next_action_at = None

        if hours_waiting > escalation_hours:
            action = "escalate"
            urgency = "high"
        elif hours_waiting > second_reminder_hours and reminders < 2:
            action = "send_second_reminder"
            urgency = "medium"
            next_action_at = _next_optimal_slot(now, optimal_hour).isoformat()
        elif hours_waiting > first_reminder_hours and reminders < 1:
            action = "send_first_reminder"
            urgency = "medium"
            next_action_at = _next_optimal_slot(now, optimal_hour).isoformat()
        else:
            # Still within expected response window
            expected_by = sent_dt + timedelta(hours=first_reminder_hours)
            next_action_at = expected_by.isoformat()

        follow_ups.append({
            "type": "employment_verification",
            "id": ev.get("id"),
            "candidate_id": ev.get("candidate_id"),
            "candidate_name": f"{ev.get('first_name', '')} {ev.get('last_name', '')}".strip(),
            "verifier_email": ev.get("verifier_email"),
            "employer_name": ev.get("employer_name"),
            "sent_at": ev.get("sent_at"),
            "hours_waiting": round(hours_waiting, 1),
            "reminders_sent": reminders,
            "recommended_action": action,
            "urgency": urgency,
            "next_action_at": next_action_at,
        })

    for ref in pending_ref_list:
        sent_dt = _parse_dt(ref.get("created_at"))
        if not sent_dt:
            continue
        hours_waiting = (now - sent_dt).total_seconds() / 3600
        reminders = ref.get("reminder_count", 0) or 0

        action = "wait"
        urgency = "low"
        next_action_at = None

        if hours_waiting > escalation_hours:
            action = "escalate"
            urgency = "high"
        elif hours_waiting > second_reminder_hours and reminders < 2:
            action = "send_second_reminder"
            urgency = "medium"
            next_action_at = _next_optimal_slot(now, optimal_hour).isoformat()
        elif hours_waiting > first_reminder_hours and reminders < 1:
            action = "send_first_reminder"
            urgency = "medium"
            next_action_at = _next_optimal_slot(now, optimal_hour).isoformat()
        else:
            expected_by = sent_dt + timedelta(hours=first_reminder_hours)
            next_action_at = expected_by.isoformat()

        follow_ups.append({
            "type": "reference",
            "id": ref.get("id"),
            "candidate_id": ref.get("candidate_id"),
            "candidate_name": f"{ref.get('first_name', '')} {ref.get('last_name', '')}".strip(),
            "verifier_email": ref.get("referee_email"),
            "employer_name": ref.get("referee_organisation", ""),
            "sent_at": ref.get("created_at"),
            "hours_waiting": round(hours_waiting, 1),
            "reminders_sent": reminders,
            "recommended_action": action,
            "urgency": urgency,
            "next_action_at": next_action_at,
        })

    # Sort follow-ups by urgency then hours waiting
    urgency_order = {"high": 0, "medium": 1, "low": 2}
    follow_ups.sort(key=lambda x: (urgency_order.get(x["urgency"], 3), -x["hours_waiting"]))

    result = {
        "response_patterns": {
            "employment_verifications": emp_stats,
            "references": ref_stats,
            "best_response_days": day_analysis[:3],
            "peak_response_hours": peak_hour_analysis,
            "domain_performance": domain_analysis[:5],
            "reminder_effectiveness": reminder_analysis,
        },
        "optimal_timing": {
            "first_reminder_hours": first_reminder_hours,
            "second_reminder_hours": second_reminder_hours,
            "escalation_hours": escalation_hours,
            "optimal_send_hour": optimal_hour,
            "optimal_send_day": day_names[optimal_day] if optimal_day < 7 else "Tuesday",
            "data_driven": bool(response_times_hours),
        },
        "follow_ups": follow_ups,
        "summary": {
            "total_pending": len(follow_ups),
            "need_first_reminder": sum(1 for f in follow_ups if f["recommended_action"] == "send_first_reminder"),
            "need_second_reminder": sum(1 for f in follow_ups if f["recommended_action"] == "send_second_reminder"),
            "need_escalation": sum(1 for f in follow_ups if f["recommended_action"] == "escalate"),
            "waiting": sum(1 for f in follow_ups if f["recommended_action"] == "wait"),
        },
    }

    # Store the analysis
    scan_id = generate_id()
    now_str = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS ai_scheduling_analyses (
            id TEXT PRIMARY KEY,
            agency_id TEXT,
            total_pending INTEGER DEFAULT 0,
            need_action INTEGER DEFAULT 0,
            optimal_send_hour INTEGER,
            result_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")
        db.execute(
            "INSERT INTO ai_scheduling_analyses (id, agency_id, total_pending, need_action, optimal_send_hour, result_json, created_at) VALUES (%s,%s,%s,%s,%s,%s,%s)",
            (
                scan_id, agency_id,
                len(follow_ups),
                sum(1 for f in follow_ups if f["recommended_action"] != "wait"),
                optimal_hour,
                json.dumps(result),
                now_str,
            ),
        )

    result["id"] = scan_id
    result["created_at"] = now_str
    return result


def _next_optimal_slot(now: datetime, optimal_hour: int) -> datetime:
    """Find the next occurrence of the optimal send hour (skip weekends)."""
    candidate = now.replace(hour=optimal_hour, minute=0, second=0, microsecond=0)
    if candidate <= now:
        candidate += timedelta(days=1)
    # Skip weekends
    while candidate.weekday() >= 5:  # Saturday=5, Sunday=6
        candidate += timedelta(days=1)
    return candidate
