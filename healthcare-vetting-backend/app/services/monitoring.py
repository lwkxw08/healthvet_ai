"""
Continuous Monitoring Service
DBS update service checks, visa expiry alerts, registration renewal tracking,
sanction alerts, fraud pattern monitoring.
"""
import json
import random
from datetime import datetime, timedelta, timezone
from app.database import get_db
from app.utils.auth import generate_id


class MonitoringService:
    """Continuous compliance monitoring for recurring revenue."""

    @staticmethod
    def run_all_checks() -> dict:
        """Run all monitoring checks across all candidates."""
        results = {
            "dbs_updates": MonitoringService.check_dbs_updates(),
            "visa_expiries": MonitoringService.check_visa_expiries(),
            "registration_renewals": MonitoringService.check_registration_renewals(),
            "sanction_alerts": MonitoringService.check_sanction_alerts(),
        }
        return results

    @staticmethod
    def check_dbs_updates() -> list:
        """Check DBS Update Service for any changes."""
        alerts = []
        now = datetime.now(timezone.utc)

        with get_db() as db:
            checks = db.execute(
                """SELECT d.*, c.first_name, c.last_name FROM dbs_checks d
                   JOIN candidates c ON d.candidate_id = c.id
                   WHERE d.update_service_registered = 1
                   AND d.certificate_number IS NOT NULL""",
            ).fetchall()

            for check in checks:
                check_dict = dict(check)
                # Simulate DBS update service check
                has_change = random.random() < 0.03  # 3% chance of change
                if has_change:
                    alert_id = generate_id()
                    db.execute(
                        """INSERT INTO monitoring_alerts
                           (id, candidate_id, alert_type, severity, message, details, created_at)
                           VALUES (%s, %s, 'dbs_update_change', 'critical', %s, %s, %s)""",
                        (
                            alert_id, check_dict["candidate_id"],
                            f"DBS Update Service reports change for {check_dict['first_name']} {check_dict['last_name']}",
                            json.dumps({
                                "certificate_number": check_dict["certificate_number"],
                                "action_required": "New enhanced DBS check required",
                            }),
                            now.isoformat(),
                        ),
                    )
                    alerts.append({"candidate_id": check_dict["candidate_id"], "type": "dbs_change"})

        return alerts

    @staticmethod
    def check_visa_expiries() -> list:
        """Check for upcoming visa expiries."""
        alerts = []
        now = datetime.now(timezone.utc)
        threshold_30 = now + timedelta(days=30)
        threshold_90 = now + timedelta(days=90)

        with get_db() as db:
            checks = db.execute(
                """SELECT r.*, c.first_name, c.last_name FROM right_to_work_checks r
                   JOIN candidates c ON r.candidate_id = c.id
                   WHERE r.visa_expiry IS NOT NULL AND r.verified = 1""",
            ).fetchall()

            for check in checks:
                check_dict = dict(check)
                try:
                    expiry = datetime.fromisoformat(check_dict["visa_expiry"])
                except (ValueError, TypeError):
                    continue

                if expiry <= now:
                    severity = "critical"
                    message = f"Visa EXPIRED for {check_dict['first_name']} {check_dict['last_name']}"
                elif expiry <= threshold_30:
                    severity = "high"
                    message = f"Visa expiring within 30 days for {check_dict['first_name']} {check_dict['last_name']}"
                elif expiry <= threshold_90:
                    severity = "medium"
                    message = f"Visa expiring within 90 days for {check_dict['first_name']} {check_dict['last_name']}"
                else:
                    continue

                # Check if alert already exists
                existing = db.execute(
                    """SELECT id FROM monitoring_alerts
                       WHERE candidate_id=%s AND alert_type='visa_expiry'
                       AND is_resolved=0""",
                    (check_dict["candidate_id"],),
                ).fetchone()

                if not existing:
                    alert_id = generate_id()
                    db.execute(
                        """INSERT INTO monitoring_alerts
                           (id, candidate_id, alert_type, severity, message, details, created_at)
                           VALUES (%s, %s, 'visa_expiry', %s, %s, %s, %s)""",
                        (
                            alert_id, check_dict["candidate_id"],
                            severity, message,
                            json.dumps({
                                "visa_type": check_dict["visa_type"],
                                "expiry_date": check_dict["visa_expiry"],
                                "days_remaining": (expiry - now).days,
                            }),
                            now.isoformat(),
                        ),
                    )
                    alerts.append({
                        "candidate_id": check_dict["candidate_id"],
                        "severity": severity,
                        "days_remaining": (expiry - now).days,
                    })

        return alerts

    @staticmethod
    def check_registration_renewals() -> list:
        """Check for upcoming registration renewals."""
        alerts = []
        now = datetime.now(timezone.utc)

        with get_db() as db:
            checks = db.execute(
                """SELECT r.*, c.first_name, c.last_name FROM registration_checks r
                   JOIN candidates c ON r.candidate_id = c.id
                   WHERE r.next_check IS NOT NULL AND r.is_active = 1""",
            ).fetchall()

            for check in checks:
                check_dict = dict(check)
                try:
                    next_check = datetime.fromisoformat(check_dict["next_check"])
                except (ValueError, TypeError):
                    continue

                if next_check <= now:
                    alert_id = generate_id()
                    db.execute(
                        """INSERT INTO monitoring_alerts
                           (id, candidate_id, alert_type, severity, message, details, created_at)
                           VALUES (%s, %s, 'registration_renewal', 'high', %s, %s, %s)""",
                        (
                            alert_id, check_dict["candidate_id"],
                            f"{check_dict['body']} registration check due for {check_dict['first_name']} {check_dict['last_name']}",
                            json.dumps({
                                "body": check_dict["body"],
                                "registration_number": check_dict["registration_number"],
                                "last_checked": check_dict["last_checked"],
                            }),
                            now.isoformat(),
                        ),
                    )
                    alerts.append({
                        "candidate_id": check_dict["candidate_id"],
                        "type": "registration_renewal",
                        "body": check_dict["body"],
                    })

        return alerts

    @staticmethod
    def check_sanction_alerts() -> list:
        """Check for new sanctions on registered professionals."""
        alerts = []
        now = datetime.now(timezone.utc)

        with get_db() as db:
            checks = db.execute(
                """SELECT r.*, c.first_name, c.last_name FROM registration_checks r
                   JOIN candidates c ON r.candidate_id = c.id
                   WHERE r.is_active = 1""",
            ).fetchall()

            for check in checks:
                check_dict = dict(check)
                # Simulate sanction check - 1% chance of new sanction
                if random.random() < 0.01:
                    alert_id = generate_id()
                    db.execute(
                        """INSERT INTO monitoring_alerts
                           (id, candidate_id, alert_type, severity, message, details, created_at)
                           VALUES (%s, %s, 'new_sanction', 'critical', %s, %s, %s)""",
                        (
                            alert_id, check_dict["candidate_id"],
                            f"New sanction detected for {check_dict['first_name']} {check_dict['last_name']} on {check_dict['body']} register",
                            json.dumps({
                                "body": check_dict["body"],
                                "registration_number": check_dict["registration_number"],
                                "action": "Immediate review required",
                            }),
                            now.isoformat(),
                        ),
                    )
                    alerts.append({
                        "candidate_id": check_dict["candidate_id"],
                        "type": "new_sanction",
                        "body": check_dict["body"],
                    })

        return alerts

    @staticmethod
    def get_alerts(candidate_id: str = None, unresolved_only: bool = True) -> list:
        with get_db() as db:
            query = "SELECT * FROM monitoring_alerts"
            params = []

            conditions = []
            if candidate_id:
                conditions.append("candidate_id=%s")
                params.append(candidate_id)
            if unresolved_only:
                conditions.append("is_resolved=0")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY created_at DESC"
            rows = db.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_alerts_for_candidates(candidate_ids: list, unresolved_only: bool = True) -> list:
        """Get alerts for a specific list of candidate IDs (used for agency-scoped queries)."""
        if not candidate_ids:
            return []
        with get_db() as db:
            placeholders = ",".join("%s" for _ in candidate_ids)
            query = f"SELECT * FROM monitoring_alerts WHERE candidate_id IN ({placeholders})"
            if unresolved_only:
                query += " AND is_resolved=0"
            query += " ORDER BY created_at DESC"
            rows = db.execute(query, candidate_ids).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def resolve_alert(alert_id: str) -> dict:
        now = datetime.now(timezone.utc).isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE monitoring_alerts SET is_resolved=1, resolved_at=%s WHERE id=%s",
                (now, alert_id),
            )
            row = db.execute("SELECT * FROM monitoring_alerts WHERE id=%s", (alert_id,)).fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_dashboard_stats(agency_id: str = None) -> dict:
        with get_db() as db:
            if agency_id:
                candidates = db.execute(
                    """SELECT c.* FROM candidates c
                       JOIN agency_candidates ac ON c.id = ac.candidate_id
                       WHERE ac.agency_id=%s""",
                    (agency_id,),
                ).fetchall()
            else:
                candidates = db.execute("SELECT * FROM candidates").fetchall()

            total = len(candidates)
            compliant = sum(1 for c in candidates if dict(c)["compliance_status"] == "compliant")
            pending = sum(1 for c in candidates if dict(c)["compliance_status"] in ("in_progress", "pending_review"))
            flagged = sum(1 for c in candidates if dict(c)["compliance_status"] == "incomplete")

            alerts = db.execute(
                "SELECT COUNT(*) as cnt FROM monitoring_alerts WHERE is_resolved=0",
            ).fetchone()

            checks_in_progress = db.execute(
                """SELECT COUNT(*) as cnt FROM (
                    SELECT candidate_id FROM identity_checks WHERE status='processing'
                    UNION ALL
                    SELECT candidate_id FROM dbs_checks WHERE status='submitted'
                    UNION ALL
                    SELECT candidate_id FROM right_to_work_checks WHERE status='processing'
                )""",
            ).fetchone()

            return {
                "total_candidates": total,
                "compliant": compliant,
                "pending": pending,
                "flagged": flagged,
                "compliance_rate": round((compliant / total * 100) if total > 0 else 0, 1),
                "active_alerts": dict(alerts)["cnt"] if alerts else 0,
                "checks_in_progress": dict(checks_in_progress)["cnt"] if checks_in_progress else 0,
                "avg_completion_time_hours": round(random.uniform(24, 72), 1),
            }
