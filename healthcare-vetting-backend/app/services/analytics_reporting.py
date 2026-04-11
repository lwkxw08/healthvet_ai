"""
3.2 Reporting & Analytics Dashboard

Agency-level compliance KPI dashboard, time-to-clear metrics,
verification response rate analytics, expiry forecasting,
and exportable report generation.
"""
import json
import logging
from datetime import datetime, timezone, timedelta
from app.database import get_db
from app.utils.auth import generate_id

logger = logging.getLogger(__name__)


class AnalyticsReportingService:
    """Comprehensive analytics and reporting for agencies and admin."""

    @staticmethod
    def get_agency_kpis(agency_id: str) -> dict:
        """Get compliance KPI dashboard for a specific agency."""
        with get_db() as db:
            # Total candidates
            total = db.execute(
                "SELECT COUNT(*) AS cnt FROM agency_candidates WHERE agency_id=%s",
                (agency_id,),
            ).fetchone()["cnt"]

            # Compliance status breakdown
            compliant = db.execute(
                """SELECT COUNT(DISTINCT ac.candidate_id) FROM agency_candidates ac
                   JOIN compliance_records cr ON ac.candidate_id = cr.candidate_id
                   WHERE ac.agency_id=%s AND cr.overall_status='compliant'""",
                (agency_id,),
            ).fetchone()["cnt"]

            non_compliant = db.execute(
                """SELECT COUNT(DISTINCT ac.candidate_id) FROM agency_candidates ac
                   JOIN compliance_records cr ON ac.candidate_id = cr.candidate_id
                   WHERE ac.agency_id=%s AND cr.overall_status='non_compliant'""",
                (agency_id,),
            ).fetchone()["cnt"]

            pending = total - compliant - non_compliant

            # Average compliance score
            avg_score_row = db.execute(
                """SELECT AVG(cr.overall_score) FROM agency_candidates ac
                   JOIN compliance_records cr ON ac.candidate_id = cr.candidate_id
                   WHERE ac.agency_id=%s""",
                (agency_id,),
            ).fetchone()
            avg_score = round(list(avg_score_row.values())[0] or 0, 1)

            # Active alerts
            active_alerts = db.execute(
                """SELECT COUNT(*) AS cnt FROM monitoring_alerts ma
                   JOIN agency_candidates ac ON ma.candidate_id = ac.candidate_id
                   WHERE ac.agency_id=%s AND ma.is_resolved=0""",
                (agency_id,),
            ).fetchone()["cnt"]

            # Checks completed this month
            month_start = datetime.now(timezone.utc).replace(day=1).strftime("%Y-%m-%d")
            checks_this_month = 0
            for table in ["identity_checks", "dbs_checks", "right_to_work_checks", "registration_checks"]:
                try:
                    col = "completed_at" if table != "right_to_work_checks" else "checked_at"
                    count = db.execute(
                        f"""SELECT COUNT(*) AS cnt FROM {table} t
                            JOIN agency_candidates ac ON t.candidate_id = ac.candidate_id
                            WHERE ac.agency_id=%s AND t.{col} >= %s""",
                        (agency_id, month_start),
                    ).fetchone()["cnt"]
                    checks_this_month += count
                except Exception:
                    pass

            return {
                "total_candidates": total,
                "compliant": compliant,
                "non_compliant": non_compliant,
                "pending": pending,
                "compliance_rate": round((compliant / total * 100) if total > 0 else 0, 1),
                "avg_compliance_score": avg_score,
                "active_alerts": active_alerts,
                "checks_this_month": checks_this_month,
            }

    @staticmethod
    def get_time_to_clear(agency_id: str = None) -> dict:
        """Get average time-to-clear metrics per check type."""
        results = {}
        with get_db() as db:
            # Identity checks
            agency_filter = ""
            params = []
            if agency_id:
                agency_filter = "JOIN agency_candidates ac ON t.candidate_id = ac.candidate_id WHERE ac.agency_id=%s AND"
                params = [agency_id]
            else:
                agency_filter = "WHERE"

            for check_type, table, start_col, end_col in [
                ("identity", "identity_checks", "started_at", "completed_at"),
                ("dbs", "dbs_checks", "submitted_at", "completed_at"),
            ]:
                try:
                    row = db.execute(
                        f"""SELECT AVG(EXTRACT(EPOCH FROM ({end_col}::timestamp - {start_col}::timestamp)) / 86400.0) as avg_days,
                                   MIN(EXTRACT(EPOCH FROM ({end_col}::timestamp - {start_col}::timestamp)) / 86400.0) as min_days,
                                   MAX(EXTRACT(EPOCH FROM ({end_col}::timestamp - {start_col}::timestamp)) / 86400.0) as max_days,
                                   COUNT(*) AS total
                            FROM {table} t
                            {agency_filter} t.{end_col} IS NOT NULL AND t.{start_col} IS NOT NULL""",
                        tuple(params),
                    ).fetchone()
                    if row:
                        results[check_type] = {
                            "avg_days": round(row["avg_days"] or 0, 1),
                            "min_days": round(row["min_days"] or 0, 1),
                            "max_days": round(row["max_days"] or 0, 1),
                            "total_completed": row["total"] or 0,
                        }
                except Exception:
                    results[check_type] = {"avg_days": 0, "min_days": 0, "max_days": 0, "total_completed": 0}

            # Employment verifications
            try:
                row = db.execute(
                    f"""SELECT AVG(EXTRACT(EPOCH FROM (completed_at::timestamp - sent_at::timestamp)) / 86400.0) as avg_days,
                               MIN(EXTRACT(EPOCH FROM (completed_at::timestamp - sent_at::timestamp)) / 86400.0) as min_days,
                               MAX(EXTRACT(EPOCH FROM (completed_at::timestamp - sent_at::timestamp)) / 86400.0) as max_days,
                               COUNT(*) AS total
                        FROM employment_verifications
                        WHERE completed_at IS NOT NULL AND sent_at IS NOT NULL""",
                ).fetchone()
                if row:
                    results["employment_verification"] = {
                        "avg_days": round(row["avg_days"] or 0, 1),
                        "min_days": round(row["min_days"] or 0, 1),
                        "max_days": round(row["max_days"] or 0, 1),
                        "total_completed": row["total"] or 0,
                    }
            except Exception:
                results["employment_verification"] = {"avg_days": 0, "min_days": 0, "max_days": 0, "total_completed": 0}

            # References
            try:
                row = db.execute(
                    """SELECT AVG(EXTRACT(EPOCH FROM (completed_at::timestamp - created_at::timestamp)) / 86400.0) as avg_days,
                              MIN(EXTRACT(EPOCH FROM (completed_at::timestamp - created_at::timestamp)) / 86400.0) as min_days,
                              MAX(EXTRACT(EPOCH FROM (completed_at::timestamp - created_at::timestamp)) / 86400.0) as max_days,
                              COUNT(*) AS total
                       FROM references_
                       WHERE completed_at IS NOT NULL AND created_at IS NOT NULL""",
                ).fetchone()
                if row:
                    results["references"] = {
                        "avg_days": round(row["avg_days"] or 0, 1),
                        "min_days": round(row["min_days"] or 0, 1),
                        "max_days": round(row["max_days"] or 0, 1),
                        "total_completed": row["total"] or 0,
                    }
            except Exception:
                results["references"] = {"avg_days": 0, "min_days": 0, "max_days": 0, "total_completed": 0}

        return results

    @staticmethod
    def get_verification_response_rates(agency_id: str = None) -> dict:
        """Get verification response rate analytics."""
        with get_db() as db:
            rates = {}

            # Employment verifications
            try:
                total_ev = db.execute("SELECT COUNT(*) AS cnt FROM employment_verifications WHERE sent_at IS NOT NULL").fetchone()["cnt"]
                completed_ev = db.execute("SELECT COUNT(*) AS cnt FROM employment_verifications WHERE status IN ('verified', 'completed')").fetchone()["cnt"]
                disputed_ev = db.execute("SELECT COUNT(*) AS cnt FROM employment_verifications WHERE status='disputed'").fetchone()["cnt"]
                pending_ev = db.execute("SELECT COUNT(*) AS cnt FROM employment_verifications WHERE status='sent'").fetchone()["cnt"]
                rates["employment_verification"] = {
                    "total_sent": total_ev,
                    "completed": completed_ev,
                    "disputed": disputed_ev,
                    "pending": pending_ev,
                    "response_rate": round((completed_ev + disputed_ev) / total_ev * 100 if total_ev > 0 else 0, 1),
                }
            except Exception:
                rates["employment_verification"] = {"total_sent": 0, "completed": 0, "disputed": 0, "pending": 0, "response_rate": 0}

            # References
            try:
                total_ref = db.execute("SELECT COUNT(*) AS cnt FROM references_ WHERE created_at IS NOT NULL").fetchone()["cnt"]
                completed_ref = db.execute("SELECT COUNT(*) AS cnt FROM references_ WHERE status='completed'").fetchone()["cnt"]
                pending_ref = db.execute("SELECT COUNT(*) AS cnt FROM references_ WHERE status IN ('sent', 'pending')").fetchone()["cnt"]
                rates["references"] = {
                    "total_sent": total_ref,
                    "completed": completed_ref,
                    "pending": pending_ref,
                    "response_rate": round(completed_ref / total_ref * 100 if total_ref > 0 else 0, 1),
                }
            except Exception:
                rates["references"] = {"total_sent": 0, "completed": 0, "pending": 0, "response_rate": 0}

            return rates

    @staticmethod
    def get_expiry_forecast(agency_id: str = None, days_ahead: int = 90) -> dict:
        """Forecast upcoming expiries in the next N days."""
        now = datetime.now(timezone.utc)
        cutoff = (now + timedelta(days=days_ahead)).isoformat()
        now_iso = now.isoformat()

        with get_db() as db:
            forecasts = {"visa": [], "dbs": [], "registration": [], "training": []}

            # Visa expiries
            try:
                rows = db.execute(
                    """SELECT r.candidate_id, c.first_name, c.last_name, r.visa_expiry
                       FROM right_to_work_checks r
                       JOIN candidates c ON r.candidate_id = c.id
                       WHERE r.visa_expiry IS NOT NULL AND r.visa_expiry BETWEEN %s AND %s
                       ORDER BY r.visa_expiry ASC""",
                    (now_iso, cutoff),
                ).fetchall()
                forecasts["visa"] = [{"candidate_id": r["candidate_id"], "name": f'{r["first_name"]} {r["last_name"]}', "expiry": r["visa_expiry"]} for r in rows]
            except Exception:
                pass

            # DBS renewals
            try:
                rows = db.execute(
                    """SELECT d.candidate_id, c.first_name, c.last_name, d.next_renewal
                       FROM dbs_checks d
                       JOIN candidates c ON d.candidate_id = c.id
                       WHERE d.next_renewal IS NOT NULL AND d.next_renewal BETWEEN %s AND %s
                       ORDER BY d.next_renewal ASC""",
                    (now_iso, cutoff),
                ).fetchall()
                forecasts["dbs"] = [{"candidate_id": r["candidate_id"], "name": f'{r["first_name"]} {r["last_name"]}', "expiry": r["next_renewal"]} for r in rows]
            except Exception:
                pass

            # Registration renewals
            try:
                rows = db.execute(
                    """SELECT r.candidate_id, c.first_name, c.last_name, r.next_check, r.body
                       FROM registration_checks r
                       JOIN candidates c ON r.candidate_id = c.id
                       WHERE r.next_check IS NOT NULL AND r.next_check BETWEEN %s AND %s AND r.is_active=1
                       ORDER BY r.next_check ASC""",
                    (now_iso, cutoff),
                ).fetchall()
                forecasts["registration"] = [{"candidate_id": r["candidate_id"], "name": f'{r["first_name"]} {r["last_name"]}', "expiry": r["next_check"], "body": r["body"]} for r in rows]
            except Exception:
                pass

            # Training expiries
            try:
                rows = db.execute(
                    """SELECT t.candidate_id, c.first_name, c.last_name, t.expiry_date, t.certificate_name
                       FROM training_certificates t
                       JOIN candidates c ON t.candidate_id = c.id
                       WHERE t.expiry_date IS NOT NULL AND t.expiry_date BETWEEN %s AND %s AND t.status='valid'
                       ORDER BY t.expiry_date ASC""",
                    (now_iso, cutoff),
                ).fetchall()
                forecasts["training"] = [{"candidate_id": r["candidate_id"], "name": f'{r["first_name"]} {r["last_name"]}', "expiry": r["expiry_date"], "certificate": r["certificate_name"]} for r in rows]
            except Exception:
                pass

            summary = {k: len(v) for k, v in forecasts.items()}
            summary["total"] = sum(summary.values())

            return {"days_ahead": days_ahead, "summary": summary, "forecasts": forecasts}

    @staticmethod
    def generate_compliance_csv(agency_id: str = None) -> str:
        """Generate a CSV string of compliance data for export."""
        import csv
        import io

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Candidate ID", "Name", "Email", "Profession", "Compliance Status",
                         "Compliance Score", "Identity", "DBS", "RTW", "Registration",
                         "References", "Employment", "Training", "Last Evaluated"])

        with get_db() as db:
            if agency_id:
                rows = db.execute(
                    """SELECT c.id, c.first_name, c.last_name, c.email, c.profession,
                              cr.overall_status, cr.overall_score, cr.details, cr.last_evaluated
                       FROM candidates c
                       JOIN agency_candidates ac ON c.id = ac.candidate_id
                       LEFT JOIN compliance_records cr ON c.id = cr.candidate_id
                       WHERE ac.agency_id=%s
                       ORDER BY c.last_name""",
                    (agency_id,),
                ).fetchall()
            else:
                rows = db.execute(
                    """SELECT c.id, c.first_name, c.last_name, c.email, c.profession,
                              cr.overall_status, cr.overall_score, cr.details, cr.last_evaluated
                       FROM candidates c
                       LEFT JOIN compliance_records cr ON c.id = cr.candidate_id
                       ORDER BY c.last_name""",
                ).fetchall()

            for row in rows:
                r = dict(row)
                details = {}
                if r.get("details"):
                    try:
                        details = json.loads(r["details"]) if isinstance(r["details"], str) else r["details"]
                    except (json.JSONDecodeError, TypeError):
                        pass

                checks = details.get("checks", {})
                writer.writerow([
                    r.get("id", ""),
                    f"{r.get('first_name', '')} {r.get('last_name', '')}",
                    r.get("email", ""),
                    r.get("profession", ""),
                    r.get("overall_status", "pending"),
                    r.get("overall_score", 0),
                    checks.get("identity", {}).get("status", "pending") if isinstance(checks.get("identity"), dict) else "pending",
                    checks.get("dbs", {}).get("status", "pending") if isinstance(checks.get("dbs"), dict) else "pending",
                    checks.get("right_to_work", {}).get("status", "pending") if isinstance(checks.get("right_to_work"), dict) else "pending",
                    checks.get("registration", {}).get("status", "pending") if isinstance(checks.get("registration"), dict) else "pending",
                    checks.get("references", {}).get("status", "pending") if isinstance(checks.get("references"), dict) else "pending",
                    checks.get("employment", {}).get("status", "pending") if isinstance(checks.get("employment"), dict) else "pending",
                    checks.get("training", {}).get("status", "pending") if isinstance(checks.get("training"), dict) else "pending",
                    r.get("last_evaluated", ""),
                ])

        return output.getvalue()

    @staticmethod
    def get_check_volume_trend(agency_id: str = None, months: int = 6) -> list:
        """Get monthly check volume trend for the past N months."""
        with get_db() as db:
            trend = []
            now = datetime.now(timezone.utc)

            for i in range(months - 1, -1, -1):
                month_start = (now.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
                if i > 0:
                    month_end = (now.replace(day=1) - timedelta(days=30 * (i - 1))).replace(day=1)
                else:
                    month_end = now + timedelta(days=1)

                start_str = month_start.strftime("%Y-%m-%d")
                end_str = month_end.strftime("%Y-%m-%d")
                label = month_start.strftime("%b %Y")

                total = 0
                for table, col in [
                    ("identity_checks", "completed_at"),
                    ("dbs_checks", "completed_at"),
                    ("right_to_work_checks", "checked_at"),
                    ("registration_checks", "last_checked"),
                ]:
                    try:
                        count = db.execute(
                            f"SELECT COUNT(*) AS cnt FROM {table} WHERE {col} >= %s AND {col} < %s",
                            (start_str, end_str),
                        ).fetchone()["cnt"]
                        total += count
                    except Exception:
                        pass

                trend.append({"month": label, "checks": total})

            return trend
