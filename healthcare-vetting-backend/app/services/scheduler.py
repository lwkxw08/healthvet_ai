"""
Scheduled Monitoring Service
Runs monitoring checks on a configurable schedule and sends email notifications.
"""
import logging
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_scheduler = None


def get_scheduler():
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler()
    return _scheduler


def start_scheduler():
    """Start the background scheduler for monitoring tasks."""
    scheduler = get_scheduler()
    if scheduler.running:
        return

    # Run monitoring checks daily at 2 AM
    scheduler.add_job(
        run_scheduled_monitoring,
        CronTrigger(hour=2, minute=0),
        id="daily_monitoring",
        replace_existing=True,
        name="Daily Monitoring Checks",
    )

    # Run expiry warning checks daily at 8 AM
    scheduler.add_job(
        run_expiry_warnings,
        CronTrigger(hour=8, minute=0),
        id="expiry_warnings",
        replace_existing=True,
        name="Expiry Warning Checks",
    )

    # Run fraud pattern scan weekly on Sunday at 3 AM
    scheduler.add_job(
        run_fraud_scan,
        CronTrigger(day_of_week="sun", hour=3),
        id="weekly_fraud_scan",
        replace_existing=True,
        name="Weekly Fraud Pattern Scan",
    )

    # Run payment reminders daily at 9 AM
    scheduler.add_job(
        run_payment_reminders,
        CronTrigger(hour=9, minute=0),
        id="payment_reminders",
        replace_existing=True,
        name="Payment Reminder Checks",
    )

    # Run weekly admin analytics report every Monday at 7 AM
    scheduler.add_job(
        run_weekly_admin_report,
        CronTrigger(day_of_week="mon", hour=7, minute=0),
        id="weekly_admin_report",
        replace_existing=True,
        name="Weekly Admin Analytics Report",
    )

    # Run monitoring subscription expiry checks daily at 8:30 AM
    scheduler.add_job(
        run_monitoring_expiry_checks,
        CronTrigger(hour=8, minute=30),
        id="monitoring_expiry_checks",
        replace_existing=True,
        name="Monitoring Subscription Expiry Checks",
    )

    scheduler.start()
    logger.info("Monitoring scheduler started with 6 jobs")


def stop_scheduler():
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown()
        _scheduler = None


def run_scheduled_monitoring():
    """Run all monitoring checks and send notifications."""
    from app.services.monitoring import MonitoringService
    from app.services.email_service import EmailService

    logger.info("Running scheduled monitoring checks...")
    try:
        results = MonitoringService.run_all_checks()

        # Count total alerts generated
        total_alerts = sum(len(v) for v in results.values())
        if total_alerts > 0:
            # Send notifications to affected agencies
            EmailService.send_monitoring_summary(results)
            logger.info(f"Monitoring complete: {total_alerts} new alerts generated, notifications sent")
        else:
            logger.info("Monitoring complete: no new alerts")
    except Exception as e:
        logger.error(f"Scheduled monitoring failed: {e}")


def _should_send_expiry_warning(db, candidate_id: str, credential_type: str,
                                credential_id: str, now: datetime,
                                interval_days: int = 10) -> bool:
    """Check if enough time has passed since the last expiry warning for this credential.
    Returns True if no warning has been sent, or if >= interval_days since last warning."""
    try:
        db.execute(
            """SELECT last_warned_at FROM expiry_warning_log
               WHERE candidate_id=%s AND credential_type=%s
               AND COALESCE(credential_id, '')=%s""",
            (candidate_id, credential_type, credential_id or ""),
        )
        row = db.fetchone()
        if not row:
            return True
        last_warned = datetime.fromisoformat(dict(row)["last_warned_at"])
        return (now - last_warned).days >= interval_days
    except Exception:
        return True  # table may not exist yet; allow sending


def _record_expiry_warning(db, candidate_id: str, credential_type: str,
                           credential_id: str, now_str: str):
    """Record that an expiry warning was sent for this credential."""
    from app.utils.auth import generate_id
    try:
        db.execute(
            """INSERT INTO expiry_warning_log
               (id, candidate_id, credential_type, credential_id, last_warned_at, warning_count)
               VALUES (%s, %s, %s, %s, %s, 1)
               ON CONFLICT (candidate_id, credential_type, credential_id)
               DO UPDATE SET last_warned_at=%s, warning_count = expiry_warning_log.warning_count + 1""",
            (generate_id(), candidate_id, credential_type, credential_id or "",
             now_str, now_str),
        )
    except Exception as e:
        logger.warning(f"Failed to record expiry warning: {e}")


def run_expiry_warnings():
    """Check for upcoming expiries and send warning emails.

    Deduplication: each credential is only warned about once every 10 days.
    Uses the expiry_warning_log table to track when the last warning was sent.
    """
    from app.services.email_service import EmailService
    from app.database import get_db

    logger.info("Running expiry warning checks...")
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    try:
        with get_db() as db:
            expiry_notifications = []

            # ── Visa expiries (30-day window) ──
            db.execute(
                """SELECT r.*, c.first_name, c.last_name, c.email as candidate_email,
                          a.email as agency_email, a.name as agency_name
                   FROM right_to_work_checks r
                   JOIN candidates c ON r.candidate_id = c.id
                   LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                   LEFT JOIN agencies a ON ac.agency_id = a.id
                   WHERE r.visa_expiry IS NOT NULL AND r.verified = 1
                   AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
            )
            for row in db.fetchall():
                r = dict(row)
                try:
                    expiry = datetime.fromisoformat(r["visa_expiry"])
                    days_left = (expiry - now).days
                    if 0 < days_left <= 30 and _should_send_expiry_warning(
                        db, r["candidate_id"], "visa_expiry", r.get("id", ""), now
                    ):
                        expiry_notifications.append({
                            "type": "visa_expiry",
                            "candidate_id": r["candidate_id"],
                            "credential_id": r.get("id", ""),
                            "candidate_name": f"{r['first_name']} {r['last_name']}",
                            "candidate_email": r["candidate_email"],
                            "agency_email": r.get("agency_email"),
                            "agency_name": r.get("agency_name"),
                            "days_left": days_left,
                            "expiry_date": r["visa_expiry"],
                        })
                except (ValueError, TypeError):
                    continue

            # ── DBS renewal (60-day window) ──
            db.execute(
                """SELECT d.*, c.first_name, c.last_name, c.email as candidate_email,
                          a.email as agency_email, a.name as agency_name
                   FROM dbs_checks d
                   JOIN candidates c ON d.candidate_id = c.id
                   LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                   LEFT JOIN agencies a ON ac.agency_id = a.id
                   WHERE d.next_renewal IS NOT NULL
                   AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
            )
            for row in db.fetchall():
                r = dict(row)
                try:
                    renewal = datetime.fromisoformat(r["next_renewal"])
                    days_left = (renewal - now).days
                    if 0 < days_left <= 60 and _should_send_expiry_warning(
                        db, r["candidate_id"], "dbs_renewal", r.get("id", ""), now
                    ):
                        expiry_notifications.append({
                            "type": "dbs_renewal",
                            "candidate_id": r["candidate_id"],
                            "credential_id": r.get("id", ""),
                            "candidate_name": f"{r['first_name']} {r['last_name']}",
                            "candidate_email": r["candidate_email"],
                            "agency_email": r.get("agency_email"),
                            "agency_name": r.get("agency_name"),
                            "days_left": days_left,
                            "expiry_date": r["next_renewal"],
                        })
                except (ValueError, TypeError):
                    continue

            # ── Registration renewals (30-day window) ──
            db.execute(
                """SELECT r.*, c.first_name, c.last_name, c.email as candidate_email,
                          a.email as agency_email, a.name as agency_name
                   FROM registration_checks r
                   JOIN candidates c ON r.candidate_id = c.id
                   LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                   LEFT JOIN agencies a ON ac.agency_id = a.id
                   WHERE r.next_check IS NOT NULL AND r.is_active = 1
                   AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
            )
            for row in db.fetchall():
                r = dict(row)
                try:
                    next_check = datetime.fromisoformat(r["next_check"])
                    days_left = (next_check - now).days
                    if 0 < days_left <= 30 and _should_send_expiry_warning(
                        db, r["candidate_id"], "registration_renewal", r.get("id", ""), now
                    ):
                        expiry_notifications.append({
                            "type": "registration_renewal",
                            "candidate_id": r["candidate_id"],
                            "credential_id": r.get("id", ""),
                            "candidate_name": f"{r['first_name']} {r['last_name']}",
                            "candidate_email": r["candidate_email"],
                            "agency_email": r.get("agency_email"),
                            "agency_name": r.get("agency_name"),
                            "days_left": days_left,
                            "expiry_date": r["next_check"],
                            "body": r.get("body", ""),
                        })
                except (ValueError, TypeError):
                    continue

            # ── Training certificate expiries (30-day window) ──
            try:
                db.execute(
                    """SELECT t.*, c.first_name, c.last_name, c.email as candidate_email,
                              a.email as agency_email, a.name as agency_name
                       FROM training_certificates t
                       JOIN candidates c ON t.candidate_id = c.id
                       LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                       LEFT JOIN agencies a ON ac.agency_id = a.id
                       WHERE t.expiry_date IS NOT NULL AND t.status = 'valid'
                       AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
                )
                for row in db.fetchall():
                    r = dict(row)
                    try:
                        expiry = datetime.fromisoformat(r["expiry_date"])
                        days_left = (expiry - now).days
                        if 0 < days_left <= 30 and _should_send_expiry_warning(
                            db, r["candidate_id"], "training_expiry", r.get("id", ""), now
                        ):
                            expiry_notifications.append({
                                "type": "training_expiry",
                                "candidate_id": r["candidate_id"],
                                "credential_id": r.get("id", ""),
                                "candidate_name": f"{r['first_name']} {r['last_name']}",
                                "candidate_email": r["candidate_email"],
                                "agency_email": r.get("agency_email"),
                                "agency_name": r.get("agency_name"),
                                "days_left": days_left,
                                "expiry_date": r["expiry_date"],
                                "certificate_name": r.get("certificate_name", ""),
                            })
                    except (ValueError, TypeError):
                        continue
            except Exception:
                pass  # training_certificates table may not exist yet

            if expiry_notifications:
                EmailService.send_expiry_warnings(expiry_notifications)
                # Record that we sent warnings for these credentials
                for n in expiry_notifications:
                    _record_expiry_warning(
                        db, n["candidate_id"], n["type"],
                        n.get("credential_id", ""), now_str,
                    )
                logger.info(f"Sent {len(expiry_notifications)} expiry warning notifications")
            else:
                logger.info("No expiry warnings to send (all within 10-day cooldown or none due)")

    except Exception as e:
        logger.error(f"Expiry warning check failed: {e}")


def run_payment_reminders():
    """Send payment reminders for unpaid invoices."""
    from app.services.billing import BillingService

    logger.info("Running payment reminder checks...")
    try:
        reminders = BillingService.send_payment_reminders()
        if reminders:
            logger.info(f"Payment reminders sent: {len(reminders)} reminders")
        else:
            logger.info("No payment reminders to send")
    except Exception as e:
        logger.error(f"Payment reminder check failed: {e}")


def run_fraud_scan():
    """Run weekly cross-candidate fraud detection scan."""
    from app.services.fraud_detection import FraudDetectionService

    logger.info("Running weekly fraud detection scan...")
    try:
        results = FraudDetectionService.run_full_scan()
        logger.info(f"Fraud scan complete: {results.get('total_flags', 0)} flags found")
    except Exception as e:
        logger.error(f"Fraud scan failed: {e}")


def run_weekly_admin_report():
    """Generate and email a weekly analytics summary to all admin users."""
    from app.database import get_db
    from app.services.email_service import EmailService
    from app.config import DASHBOARD_URL

    logger.info("Generating weekly admin analytics report...")
    try:
        with get_db() as db:
            # Gather key metrics
            db.execute("SELECT COUNT(*) as cnt FROM candidates")
            total_candidates = db.fetchone()
            total_candidates = dict(total_candidates)["cnt"] if total_candidates else 0

            db.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE compliance_status='compliant'"
            )
            compliant = db.fetchone()
            compliant = dict(compliant)["cnt"] if compliant else 0

            db.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE compliance_status IN ('flagged','incomplete')"
            )
            flagged = db.fetchone()
            flagged = dict(flagged)["cnt"] if flagged else 0

            db.execute("SELECT COUNT(*) as cnt FROM agencies")
            total_agencies = db.fetchone()
            total_agencies = dict(total_agencies)["cnt"] if total_agencies else 0

            # Revenue this week
            db.execute(
                "SELECT COALESCE(SUM(sell_amount),0) as total FROM invoices WHERE status='paid' AND created_at >= date('now','-7 days')"
            )
            week_revenue = db.fetchone()
            week_revenue = dict(week_revenue)["total"] if week_revenue else 0

            db.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(COALESCE(adjusted_amount, sell_amount)),0) as total FROM invoices WHERE status='pending'"
            )
            pending_invoices = db.fetchone()
            pi = dict(pending_invoices) if pending_invoices else {"cnt": 0, "total": 0}

            # New candidates this week
            db.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE created_at >= date('now','-7 days')"
            )
            new_candidates = db.fetchone()
            new_candidates = dict(new_candidates)["cnt"] if new_candidates else 0

            # Build email content
            now = datetime.now(timezone.utc)
            week_start = (now - timedelta(days=7)).strftime("%d %b %Y")
            week_end = now.strftime("%d %b %Y")

            subject = f"Viper AI — Weekly Report ({week_start} - {week_end})"
            body = (
                f"Weekly Analytics Summary\n"
                f"Period: {week_start} — {week_end}\n\n"
                f"CANDIDATES\n"
                f"  Total: {total_candidates}\n"
                f"  Compliant: {compliant}\n"
                f"  Flagged/Incomplete: {flagged}\n"
                f"  New this week: {new_candidates}\n\n"
                f"AGENCIES\n"
                f"  Total: {total_agencies}\n\n"
                f"FINANCIALS\n"
                f"  Revenue this week: \u00a3{week_revenue:,.2f}\n"
                f"  Pending invoices: {pi['cnt']} (\u00a3{pi['total']:,.2f})\n\n"
                f"View full dashboard: {DASHBOARD_URL}/admin\n\n"
                f"— Viper AI Compliance Team"
            )

            # Send to all admin users
            db.execute("SELECT email FROM admins")
            admins = db.fetchall()
            for admin_row in admins:
                admin_email = dict(admin_row)["email"]
                EmailService._store_notification(
                    recipient_email=admin_email,
                    recipient_name="Admin",
                    subject=subject,
                    body=body,
                    notification_type="weekly_admin_report",
                )
                logger.info(f"Weekly admin report sent to {admin_email}")

            if not admins:
                logger.info("No admin users found for weekly report")

    except Exception as e:
        logger.error(f"Weekly admin report generation failed: {e}")


def run_monitoring_expiry_checks():
    """Check for candidates whose monitoring subscription is expiring and:
    1. Send reminders every 10 days until expiry (reuses the expiry_warning_log dedup)
    2. On actual expiry, set monitoring_active=0 to halt monitoring
    """
    from app.services.email_service import EmailService
    from app.database import get_db

    logger.info("Running monitoring subscription expiry checks...")
    now = datetime.now(timezone.utc)
    now_str = now.isoformat()

    try:
        with get_db() as db:
            # --- Part 1: Expire monitoring for candidates past their expiry date ---
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active = 0
                   WHERE monitoring_active = 1
                   AND monitoring_expires_at IS NOT NULL
                   AND monitoring_expires_at <= %s""",
                (now_str,),
            )
            expired_count = db.rowcount or 0
            if expired_count > 0:
                logger.info(f"Halted monitoring for {expired_count} expired candidate(s)")

            # --- Part 2: Send expiry reminders (30-day lookahead, 10-day intervals) ---
            db.execute(
                """SELECT ac.agency_id, ac.candidate_id, ac.monitoring_expires_at,
                          c.first_name, c.last_name, c.email AS candidate_email,
                          a.email AS agency_email, a.name AS agency_name
                   FROM agency_candidates ac
                   JOIN candidates c ON ac.candidate_id = c.id
                   JOIN agencies a ON ac.agency_id = a.id
                   WHERE ac.monitoring_active = 1
                   AND ac.monitoring_expires_at IS NOT NULL""",
            )
            expiry_notifications = []
            for row in db.fetchall():
                r = dict(row)
                try:
                    expiry = datetime.fromisoformat(r["monitoring_expires_at"])
                    days_left = (expiry - now).days
                    if 0 < days_left <= 30 and _should_send_expiry_warning(
                        db, r["candidate_id"], "monitoring_expiry",
                        f"monitoring_{r['agency_id']}", now
                    ):
                        expiry_notifications.append({
                            "type": "monitoring_expiry",
                            "candidate_id": r["candidate_id"],
                            "credential_id": f"monitoring_{r['agency_id']}",
                            "candidate_name": f"{r['first_name']} {r['last_name']}",
                            "candidate_email": r["candidate_email"],
                            "agency_email": r.get("agency_email"),
                            "agency_name": r.get("agency_name"),
                            "days_left": days_left,
                            "expiry_date": r["monitoring_expires_at"],
                        })
                except (ValueError, TypeError):
                    continue

            if expiry_notifications:
                EmailService.send_expiry_warnings(expiry_notifications)
                for n in expiry_notifications:
                    _record_expiry_warning(
                        db, n["candidate_id"], n["type"],
                        n.get("credential_id", ""), now_str,
                    )
                logger.info(f"Sent {len(expiry_notifications)} monitoring expiry warning(s)")
            else:
                logger.info("No monitoring expiry warnings to send")

    except Exception as e:
        logger.error(f"Monitoring expiry check failed: {e}")
