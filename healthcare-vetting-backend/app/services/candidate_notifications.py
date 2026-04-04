"""2.3 Candidate Pre-Notification Service: notify candidates before sending verification requests to referees."""
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id


# Default delay before sending the verification request to the referee (hours)
DEFAULT_DELAY_HOURS = 24


def create_pre_notification(
    candidate_id: str,
    verification_type: str,
    verifier_name: str,
    verifier_email: str,
    verifier_organisation: str | None = None,
    verification_request_id: str | None = None,
) -> dict:
    """Create a pre-notification record and queue an email to the candidate."""
    now = datetime.now(timezone.utc).isoformat()
    notif_id = generate_id()

    with get_db() as db:
        # Look up candidate email
        candidate = db.execute("SELECT email, first_name, last_name FROM candidates WHERE id=?", (candidate_id,)).fetchone()
        if not candidate:
            return {"error": "Candidate not found"}
        candidate = dict(candidate)

        db.execute(
            """INSERT INTO candidate_pre_notifications
               (id, candidate_id, verification_type, verifier_name, verifier_email,
                verifier_organisation, status, sent_at, verification_request_id, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (notif_id, candidate_id, verification_type, verifier_name, verifier_email,
             verifier_organisation, "pending", now, verification_request_id, now),
        )

    return {
        "notification_id": notif_id,
        "candidate_email": candidate["email"],
        "candidate_name": f"{candidate.get('first_name', '')} {candidate.get('last_name', '')}".strip(),
        "verification_type": verification_type,
        "verifier_name": verifier_name,
        "verifier_email": verifier_email,
        "status": "pending",
        "created_at": now,
    }


def get_pending_notifications(candidate_id: str) -> list[dict]:
    """Get all pending pre-notifications for a candidate."""
    with get_db() as db:
        rows = db.execute(
            "SELECT * FROM candidate_pre_notifications WHERE candidate_id=? AND status='pending' ORDER BY created_at DESC",
            (candidate_id,),
        ).fetchall()
        return [dict(r) for r in rows]


def confirm_notification(notification_id: str, candidate_id: str) -> dict | None:
    """Candidate confirms a pre-notification — the verification request can now proceed."""
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        notif = db.execute(
            "SELECT * FROM candidate_pre_notifications WHERE id=? AND candidate_id=?",
            (notification_id, candidate_id),
        ).fetchone()
        if not notif:
            return None
        db.execute(
            "UPDATE candidate_pre_notifications SET status='confirmed', candidate_confirmed_at=? WHERE id=?",
            (now, notification_id),
        )
        return {**dict(notif), "status": "confirmed", "candidate_confirmed_at": now}


def update_verifier_details(
    notification_id: str, candidate_id: str,
    verifier_name: str | None = None,
    verifier_email: str | None = None,
    verifier_organisation: str | None = None,
) -> dict | None:
    """Candidate updates verifier contact details before the request is sent."""
    with get_db() as db:
        notif = db.execute(
            "SELECT * FROM candidate_pre_notifications WHERE id=? AND candidate_id=? AND status='pending'",
            (notification_id, candidate_id),
        ).fetchone()
        if not notif:
            return None
        updates = []
        params = []
        if verifier_name:
            updates.append("verifier_name=?")
            params.append(verifier_name)
        if verifier_email:
            updates.append("verifier_email=?")
            params.append(verifier_email)
        if verifier_organisation:
            updates.append("verifier_organisation=?")
            params.append(verifier_organisation)
        if updates:
            params.append(notification_id)
            db.execute(f"UPDATE candidate_pre_notifications SET {', '.join(updates)} WHERE id=?", params)
        return dict(db.execute("SELECT * FROM candidate_pre_notifications WHERE id=?", (notification_id,)).fetchone())


def get_ready_notifications(delay_hours: int = DEFAULT_DELAY_HOURS) -> list[dict]:
    """Get notifications that are either confirmed or have passed the delay window.
    These are ready for the verification request to be sent to the referee."""
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=delay_hours)).isoformat()
    with get_db() as db:
        rows = db.execute(
            """SELECT * FROM candidate_pre_notifications
               WHERE (status='confirmed')
                  OR (status='pending' AND sent_at < ?)
               ORDER BY created_at ASC""",
            (cutoff,),
        ).fetchall()
        return [dict(r) for r in rows]


def mark_notification_sent(notification_id: str) -> None:
    """Mark a notification as having had its verification request sent."""
    with get_db() as db:
        db.execute(
            "UPDATE candidate_pre_notifications SET status='sent' WHERE id=?",
            (notification_id,),
        )
