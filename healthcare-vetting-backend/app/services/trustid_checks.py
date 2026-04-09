"""
TrustID Check Service — Dual-Mode (Manual + API) for Identity, DBS, and Right to Work checks.

Manual mode: Admin submits checks via TrustID portal, records results in HealthVet.
API mode: (Future) Automated submission via TrustID REST API with webhook callbacks.

The submission_mode per check type is stored in the trustid_config table and can be
toggled independently by the admin (e.g. identity on API while DBS is still manual).
"""
import json
import logging
from datetime import datetime, timezone
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


# Default config for each TrustID check type
DEFAULT_CONFIG = {
    "identity_verification": {"label": "Identity Verification", "submission_mode": "manual"},
    "dbs_check": {"label": "DBS Check", "submission_mode": "manual"},
    "right_to_work": {"label": "Right to Work", "submission_mode": "manual"},
}


class TrustIDService:
    """Manages TrustID check submissions in both manual and API modes."""

    # ── Configuration ─────────────────────────────────────────────────

    @staticmethod
    def get_config() -> dict:
        """Return the current TrustID configuration for all check types."""
        with get_db() as db:
            rows = db.execute("SELECT * FROM trustid_config ORDER BY check_type").fetchall()
            if not rows:
                return DEFAULT_CONFIG
            config = {}
            for r in rows:
                d = dict(r)
                config[d["check_type"]] = d
            # Fill in any missing check types with defaults
            for ct, defaults in DEFAULT_CONFIG.items():
                if ct not in config:
                    config[ct] = {**defaults, "check_type": ct, "api_key": None, "api_secret": None, "environment": "production"}
            return config

    @staticmethod
    def update_config(check_type: str, submission_mode: str | None = None,
                      api_key: str | None = None, api_secret: str | None = None,
                      environment: str | None = None) -> dict:
        """Update the TrustID configuration for a specific check type."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            existing = db.execute(
                "SELECT * FROM trustid_config WHERE check_type=?", (check_type,)
            ).fetchone()

            if existing:
                updates = []
                params = []
                if submission_mode is not None:
                    updates.append("submission_mode=?")
                    params.append(submission_mode)
                if api_key is not None:
                    updates.append("api_key=?")
                    params.append(api_key)
                if api_secret is not None:
                    updates.append("api_secret=?")
                    params.append(api_secret)
                if environment is not None:
                    updates.append("environment=?")
                    params.append(environment)
                updates.append("updated_at=?")
                params.append(now)
                params.append(check_type)
                db.execute(
                    f"UPDATE trustid_config SET {', '.join(updates)} WHERE check_type=?",
                    params,
                )
            else:
                label = DEFAULT_CONFIG.get(check_type, {}).get("label", check_type.replace("_", " ").title())
                db.execute(
                    """INSERT INTO trustid_config
                       (id, check_type, label, submission_mode, api_key, api_secret, environment, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (generate_id(), check_type, label,
                     submission_mode or "manual", api_key, api_secret,
                     environment or "production", now),
                )

            row = db.execute("SELECT * FROM trustid_config WHERE check_type=?", (check_type,)).fetchone()
            return dict(row) if row else {}

    @staticmethod
    def get_submission_mode(check_type: str) -> str:
        """Return 'manual' or 'api' for a given check type."""
        with get_db() as db:
            row = db.execute(
                "SELECT submission_mode FROM trustid_config WHERE check_type=?", (check_type,)
            ).fetchone()
            if row:
                return dict(row)["submission_mode"]
            return DEFAULT_CONFIG.get(check_type, {}).get("submission_mode", "manual")

    # ── Check Submission (shared by both modes) ───────────────────────

    @staticmethod
    def create_check(
        candidate_id: str,
        check_type: str,
        submitted_by: str,
        candidate_name: str | None = None,
        candidate_email: str | None = None,
        candidate_dob: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Create a new TrustID check record. Status starts as 'pending_admin'
        in manual mode or 'submitted' in API mode."""
        check_id = generate_id()
        now = datetime.now(timezone.utc).isoformat()
        mode = TrustIDService.get_submission_mode(check_type)
        status = "pending_admin" if mode == "manual" else "submitted"

        with get_db() as db:
            db.execute(
                """INSERT INTO trustid_checks
                   (id, candidate_id, check_type, submission_mode, status,
                    candidate_name, candidate_email, candidate_dob,
                    submitted_by, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (check_id, candidate_id, check_type, mode, status,
                 candidate_name, candidate_email, candidate_dob,
                 submitted_by, notes, now, now),
            )

            # Audit log
            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'trustid_check', ?, 'created', ?, ?, ?)""",
                (generate_id(), check_id, submitted_by,
                 json.dumps({"check_type": check_type, "mode": mode, "candidate_id": candidate_id}),
                 now),
            )

            # Create admin notifications for manual tasks requiring attention
            if status == "pending_admin":
                pretty_type = check_type.replace("_", " ").title()
                display_name = candidate_name or "Unknown"
                # Notify all active admin users
                admin_rows = db.execute("SELECT id FROM admin_users WHERE is_active=1").fetchall()
                for admin_row in admin_rows:
                    db.execute(
                        """INSERT INTO in_app_notifications
                           (id, user_id, user_type, title, message, category, severity, is_read, created_at)
                           VALUES (?, ?, 'admin', ?, ?, 'trustid_task', 'warning', 0, ?)""",
                        (generate_id(), dict(admin_row)["id"],
                         f"TrustID Task: {pretty_type}",
                         f"{display_name} requires manual {pretty_type} via TrustID portal. Please action ASAP.",
                         now),
                    )

            row = db.execute("SELECT * FROM trustid_checks WHERE id=?", (check_id,)).fetchone()
            return dict(row)

    @staticmethod
    def submit_all_checks(
        candidate_id: str,
        submitted_by: str,
        candidate_name: str | None = None,
        candidate_email: str | None = None,
        candidate_dob: str | None = None,
    ) -> list:
        """Create TrustID checks for all three check types at once.
        Called when candidate completes their submission."""
        results = []
        for check_type in ["identity_verification", "dbs_check", "right_to_work"]:
            result = TrustIDService.create_check(
                candidate_id=candidate_id,
                check_type=check_type,
                submitted_by=submitted_by,
                candidate_name=candidate_name,
                candidate_email=candidate_email,
                candidate_dob=candidate_dob,
            )
            results.append(result)
        return results

    # ── Admin Task Queue ──────────────────────────────────────────────

    @staticmethod
    def get_pending_tasks(status: str | None = None) -> list:
        """Get all TrustID checks pending admin action."""
        with get_db() as db:
            if status:
                rows = db.execute(
                    """SELECT tc.*, c.first_name, c.last_name, c.email as candidate_email_lookup
                       FROM trustid_checks tc
                       LEFT JOIN candidates c ON tc.candidate_id = c.id
                       WHERE tc.status = ?
                       ORDER BY tc.created_at ASC""",
                    (status,),
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT tc.*, c.first_name, c.last_name, c.email as candidate_email_lookup
                       FROM trustid_checks tc
                       LEFT JOIN candidates c ON tc.candidate_id = c.id
                       WHERE tc.status IN ('pending_admin', 'submitted_to_trustid', 'awaiting_candidate')
                       ORDER BY tc.created_at ASC""",
                ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_checks_for_candidate(candidate_id: str) -> list:
        """Get all TrustID checks for a specific candidate."""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM trustid_checks WHERE candidate_id=? ORDER BY created_at DESC",
                (candidate_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def admin_mark_submitted(check_id: str, admin_user: str,
                             trustid_reference: str | None = None,
                             notes: str | None = None) -> dict:
        """Admin marks a check as submitted to TrustID portal.
        Status transitions: pending_admin → submitted_to_trustid → awaiting_candidate."""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            row = db.execute("SELECT * FROM trustid_checks WHERE id=?", (check_id,)).fetchone()
            if not row:
                return {}
            check = dict(row)

            new_status = "awaiting_candidate"
            db.execute(
                """UPDATE trustid_checks SET
                   status=?, trustid_reference=?, admin_notes=?,
                   admin_submitted_by=?, admin_submitted_at=?, updated_at=?
                   WHERE id=?""",
                (new_status, trustid_reference, notes, admin_user, now, now, check_id),
            )

            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'trustid_check', ?, 'admin_submitted', ?, ?, ?)""",
                (generate_id(), check_id, admin_user,
                 json.dumps({"trustid_reference": trustid_reference, "previous_status": check["status"]}),
                 now),
            )

            updated = db.execute("SELECT * FROM trustid_checks WHERE id=?", (check_id,)).fetchone()
            return dict(updated)

    @staticmethod
    def admin_record_result(check_id: str, admin_user: str,
                            result: str, trustid_reference: str | None = None,
                            report_document_id: str | None = None,
                            completed_date: str | None = None,
                            notes: str | None = None) -> dict:
        """Admin records the final result from TrustID.
        result: 'pass', 'fail', 'inconclusive', 'intervention_required'"""
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            row = db.execute("SELECT * FROM trustid_checks WHERE id=?", (check_id,)).fetchone()
            if not row:
                return {}
            check = dict(row)

            db.execute(
                """UPDATE trustid_checks SET
                   status='completed', result=?, trustid_reference=COALESCE(?, trustid_reference),
                   report_document_id=?, completed_at=?, admin_notes=?,
                   admin_completed_by=?, updated_at=?
                   WHERE id=?""",
                (result, trustid_reference, report_document_id,
                 completed_date or now, notes, admin_user, now, check_id),
            )

            db.execute(
                """INSERT INTO audit_logs (id, entity_type, entity_id, action, actor, details, created_at)
                   VALUES (?, 'trustid_check', ?, 'result_recorded', ?, ?, ?)""",
                (generate_id(), check_id, admin_user,
                 json.dumps({
                     "result": result,
                     "check_type": check["check_type"],
                     "candidate_id": check["candidate_id"],
                     "trustid_reference": trustid_reference,
                 }),
                 now),
            )

            # When result is 'pass', insert into the legacy check tables
            # so the compliance engine can recognise the result
            candidate_id = check["candidate_id"]
            check_type = check["check_type"]
            if result == "pass":
                TrustIDService._sync_to_legacy_check_table(
                    db, candidate_id, check_type, now, trustid_reference, notes,
                )

            updated = db.execute("SELECT * FROM trustid_checks WHERE id=?", (check_id,)).fetchone()
            result_dict = dict(updated)

        # Re-evaluate compliance outside the DB context to avoid locking
        try:
            from app.services.compliance_engine import ComplianceEngine
            ComplianceEngine.evaluate_candidate(candidate_id)
        except Exception as e:
            logger.warning(f"Compliance re-evaluation failed after TrustID result: {e}")

        return result_dict

    @staticmethod
    def _sync_to_legacy_check_table(
        db, candidate_id: str, check_type: str, now: str,
        trustid_reference: str | None = None, notes: str | None = None,
    ) -> None:
        """Insert a record into the legacy check table (identity_checks,
        right_to_work_checks, dbs_checks) so the compliance engine can
        find the passed result."""
        if check_type == "identity_verification":
            db.execute(
                """INSERT INTO identity_checks
                   (id, candidate_id, provider, status, result, details, started_at, completed_at)
                   VALUES (?, ?, 'trustid', 'completed', 'clear', ?, ?, ?)""",
                (generate_id(), candidate_id,
                 json.dumps({"source": "trustid_manual", "reference": trustid_reference, "notes": notes}),
                 now, now),
            )
        elif check_type == "right_to_work":
            db.execute(
                """INSERT INTO right_to_work_checks
                   (id, candidate_id, verification_method, status, verified, result, details, checked_at)
                   VALUES (?, ?, 'trustid', 'completed', 1, 'clear', ?, ?)""",
                (generate_id(), candidate_id,
                 json.dumps({"source": "trustid_manual", "reference": trustid_reference, "notes": notes}),
                 now),
            )
        elif check_type == "dbs_check":
            db.execute(
                """INSERT INTO dbs_checks
                   (id, candidate_id, provider, status, result, details, submitted_at, completed_at)
                   VALUES (?, ?, 'trustid', 'completed', 'clear', ?, ?, ?)""",
                (generate_id(), candidate_id,
                 json.dumps({"source": "trustid_manual", "reference": trustid_reference, "notes": notes}),
                 now, now),
            )

    @staticmethod
    def get_task_summary() -> dict:
        """Get summary counts for the admin dashboard."""
        with get_db() as db:
            counts = {}
            for status in ["pending_admin", "awaiting_candidate", "submitted_to_trustid", "completed"]:
                row = db.execute(
                    "SELECT COUNT(*) as cnt FROM trustid_checks WHERE status=?", (status,)
                ).fetchone()
                counts[status] = dict(row)["cnt"]
            # Overdue = pending_admin for more than 24 hours
            row = db.execute(
                """SELECT COUNT(*) as cnt FROM trustid_checks
                   WHERE status='pending_admin'
                   AND created_at < datetime('now', '-24 hours')"""
            ).fetchone()
            counts["overdue"] = dict(row)["cnt"]
            return counts
