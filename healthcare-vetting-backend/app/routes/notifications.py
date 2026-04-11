"""In-App Notification Centre — activity feed for expiry warnings, completions, payments."""
import json
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends
from app.database import get_db
from app.utils.auth import get_current_user, generate_id

router = APIRouter(prefix="/api/notifications", tags=["Notifications"])


@router.get("")
async def get_notifications(
    limit: int = 50,
    offset: int = 0,
    unread_only: bool = False,
    category: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """Get notifications for the current user."""
    user_id = current_user["sub"]
    user_type = current_user["type"]

    with get_db() as db:
        query = "SELECT * FROM in_app_notifications WHERE user_id=%s AND user_type=%s"
        params = [user_id, user_type]

        if unread_only:
            query += " AND is_read=0"
        if category:
            query += " AND category=%s"
            params.append(category)

        query += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        rows = db.execute(query, params).fetchall()

        # Get unread count
        unread_count = db.execute(
            "SELECT COUNT(*) as cnt FROM in_app_notifications WHERE user_id=%s AND user_type=%s AND is_read=0",
            (user_id, user_type),
        ).fetchone()

        return {
            "notifications": [dict(r) for r in rows],
            "unread_count": dict(unread_count)["cnt"] if unread_count else 0,
            "total": len(rows),
        }


@router.get("/unread-count")
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    """Get just the unread notification count (for badge display)."""
    user_id = current_user["sub"]
    user_type = current_user["type"]

    with get_db() as db:
        row = db.execute(
            "SELECT COUNT(*) as cnt FROM in_app_notifications WHERE user_id=%s AND user_type=%s AND is_read=0",
            (user_id, user_type),
        ).fetchone()
        return {"unread_count": dict(row)["cnt"] if row else 0}


@router.post("/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Mark a single notification as read."""
    user_id = current_user["sub"]
    user_type = current_user["type"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM in_app_notifications WHERE id=%s AND user_id=%s AND user_type=%s",
            (notification_id, user_id, user_type),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found")

        db.execute(
            "UPDATE in_app_notifications SET is_read=1, read_at=%s WHERE id=%s",
            (now, notification_id),
        )
        return {"status": "read"}


@router.post("/mark-all-read")
async def mark_all_read(current_user: dict = Depends(get_current_user)):
    """Mark all notifications as read."""
    user_id = current_user["sub"]
    user_type = current_user["type"]
    now = datetime.now(timezone.utc).isoformat()

    with get_db() as db:
        db.execute(
            "UPDATE in_app_notifications SET is_read=1, read_at=%s WHERE user_id=%s AND user_type=%s AND is_read=0",
            (now, user_id, user_type),
        )
        return {"status": "all_read"}


@router.delete("/{notification_id}")
async def delete_notification(notification_id: str, current_user: dict = Depends(get_current_user)):
    """Delete a notification."""
    user_id = current_user["sub"]
    user_type = current_user["type"]

    with get_db() as db:
        row = db.execute(
            "SELECT * FROM in_app_notifications WHERE id=%s AND user_id=%s AND user_type=%s",
            (notification_id, user_id, user_type),
        ).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Notification not found")

        db.execute("DELETE FROM in_app_notifications WHERE id=%s", (notification_id,))
        return {"status": "deleted"}


# ── Notification Creation Utility ─────────────────────────────────

def create_notification(
    user_id: str,
    user_type: str,
    title: str,
    message: str,
    category: str = "general",
    severity: str = "info",
    link: Optional[str] = None,
    metadata: Optional[dict] = None,
):
    """Create a notification for a user. Called from other services/routes."""
    now = datetime.now(timezone.utc).isoformat()
    notif_id = generate_id()

    with get_db() as db:
        db.execute(
            """INSERT INTO in_app_notifications
               (id, user_id, user_type, title, message, category, severity, link, metadata, is_read, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 0, %s)""",
            (notif_id, user_id, user_type, title, message, category, severity,
             link, json.dumps(metadata) if metadata else None, now),
        )

    return notif_id


# ── Seed notifications on demand (for demo/testing) ──────────────

@router.post("/seed")
async def seed_notifications(current_user: dict = Depends(get_current_user)):
    """Generate sample notifications for the current user based on actual system state."""
    user_id = current_user["sub"]
    user_type = current_user["type"]
    now = datetime.now(timezone.utc).isoformat()
    created = 0

    with get_db() as db:
        if user_type == "agency":
            # Check for expiring candidates
            candidates = db.execute(
                """SELECT c.id, c.first_name, c.last_name
                   FROM candidates c
                   JOIN agency_candidates ac ON c.id = ac.candidate_id
                   WHERE ac.agency_id=%s""",
                (user_id,),
            ).fetchall()

            for cand in candidates:
                cd = dict(cand)
                cand_name = f"{cd['first_name']} {cd['last_name']}"

                # Check DBS expiry
                dbs = db.execute(
                    "SELECT next_renewal FROM dbs_checks WHERE candidate_id=%s ORDER BY submitted_at DESC LIMIT 1",
                    (cd["id"],),
                ).fetchone()
                if dbs and dict(dbs).get("next_renewal"):
                    try:
                        renewal = datetime.fromisoformat(dict(dbs)["next_renewal"])
                        if renewal.tzinfo is None:
                            renewal = renewal.replace(tzinfo=timezone.utc)
                        days = (renewal - datetime.now(timezone.utc)).days
                        if 0 < days < 60:
                            create_notification(
                                user_id, user_type,
                                f"DBS Renewal Due — {cand_name}",
                                f"DBS certificate for {cand_name} expires in {days} days. Schedule renewal now.",
                                category="expiry_warning", severity="warning",
                            )
                            created += 1
                    except (ValueError, TypeError):
                        pass

                # Check compliance status
                comp = db.execute(
                    "SELECT overall_status, score FROM compliance_records WHERE candidate_id=%s ORDER BY last_evaluated DESC LIMIT 1",
                    (cd["id"],),
                ).fetchone()
                if comp:
                    cd2 = dict(comp)
                    if cd2["overall_status"] == "compliant":
                        create_notification(
                            user_id, user_type,
                            f"Vetting Complete — {cand_name}",
                            f"{cand_name} has passed all compliance checks with a score of {cd2['score']}%.",
                            category="completion", severity="success",
                        )
                        created += 1
                    elif cd2["overall_status"] in ("incomplete", "flagged"):
                        create_notification(
                            user_id, user_type,
                            f"Action Required — {cand_name}",
                            f"{cand_name} has outstanding compliance checks. Current score: {cd2['score']}%.",
                            category="action_required", severity="warning",
                        )
                        created += 1

            # Payment notifications
            pending_invoices = db.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(COALESCE(adjusted_amount, sell_amount)), 0) as total FROM invoices WHERE agency_id=%s AND status='pending'",
                (user_id,),
            ).fetchone()
            if pending_invoices:
                pi = dict(pending_invoices)
                if pi["cnt"] > 0:
                    create_notification(
                        user_id, user_type,
                        f"Outstanding Invoices ({pi['cnt']})",
                        f"You have {pi['cnt']} pending invoice(s) totalling £{pi['total']:.2f}.",
                        category="payment", severity="info",
                    )
                    created += 1

        elif user_type == "candidate":
            # Check own compliance
            comp = db.execute(
                "SELECT overall_status, score, flags FROM compliance_records WHERE candidate_id=%s ORDER BY last_evaluated DESC LIMIT 1",
                (user_id,),
            ).fetchone()
            if comp:
                cd = dict(comp)
                if cd["overall_status"] == "compliant":
                    create_notification(
                        user_id, user_type,
                        "Vetting Complete",
                        f"All your compliance checks are complete. Score: {cd['score']}%.",
                        category="completion", severity="success",
                    )
                    created += 1
                else:
                    create_notification(
                        user_id, user_type,
                        "Action Required",
                        "You have outstanding vetting checks. Please log in to complete your profile.",
                        category="action_required", severity="warning",
                    )
                    created += 1

        elif user_type == "admin":
            # System overview notifications
            pending_inv = db.execute(
                "SELECT COUNT(*) as cnt FROM invoices WHERE status='pending'"
            ).fetchone()
            if pending_inv and dict(pending_inv)["cnt"] > 0:
                create_notification(
                    user_id, user_type,
                    f"Pending Invoices ({dict(pending_inv)['cnt']})",
                    f"There are {dict(pending_inv)['cnt']} pending invoices across all agencies.",
                    category="payment", severity="info",
                )
                created += 1

            flagged = db.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE compliance_status IN ('flagged', 'incomplete')"
            ).fetchone()
            if flagged and dict(flagged)["cnt"] > 0:
                create_notification(
                    user_id, user_type,
                    f"Candidates Requiring Attention ({dict(flagged)['cnt']})",
                    f"{dict(flagged)['cnt']} candidates have incomplete or flagged compliance status.",
                    category="action_required", severity="warning",
                )
                created += 1

    return {"status": "seeded", "notifications_created": created}
