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

    # Run expiry warning checks every 6 hours
    scheduler.add_job(
        run_expiry_warnings,
        CronTrigger(hour="*/6"),
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

    scheduler.start()
    logger.info("Monitoring scheduler started with 5 jobs")


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


def run_expiry_warnings():
    """Check for upcoming expiries and send warning emails."""
    from app.services.email_service import EmailService
    from app.database import get_db
    from datetime import timedelta

    logger.info("Running expiry warning checks...")
    now = datetime.now(timezone.utc)

    try:
        with get_db() as db:
            # Visa expiries in next 30 days
            visa_expiring = db.execute(
                """SELECT r.*, c.first_name, c.last_name, c.email as candidate_email,
                          a.email as agency_email, a.name as agency_name
                   FROM right_to_work_checks r
                   JOIN candidates c ON r.candidate_id = c.id
                   LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                   LEFT JOIN agencies a ON ac.agency_id = a.id
                   WHERE r.visa_expiry IS NOT NULL AND r.verified = 1
                   AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
            ).fetchall()

            expiry_notifications = []
            for row in visa_expiring:
                r = dict(row)
                try:
                    expiry = datetime.fromisoformat(r["visa_expiry"])
                    days_left = (expiry - now).days
                    if 0 < days_left <= 30:
                        expiry_notifications.append({
                            "type": "visa_expiry",
                            "candidate_name": f"{r['first_name']} {r['last_name']}",
                            "candidate_email": r["candidate_email"],
                            "agency_email": r.get("agency_email"),
                            "agency_name": r.get("agency_name"),
                            "days_left": days_left,
                            "expiry_date": r["visa_expiry"],
                        })
                except (ValueError, TypeError):
                    continue

            # DBS renewal checks
            dbs_expiring = db.execute(
                """SELECT d.*, c.first_name, c.last_name, c.email as candidate_email,
                          a.email as agency_email, a.name as agency_name
                   FROM dbs_checks d
                   JOIN candidates c ON d.candidate_id = c.id
                   LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                   LEFT JOIN agencies a ON ac.agency_id = a.id
                   WHERE d.next_renewal IS NOT NULL
                   AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
            ).fetchall()

            for row in dbs_expiring:
                r = dict(row)
                try:
                    renewal = datetime.fromisoformat(r["next_renewal"])
                    days_left = (renewal - now).days
                    if 0 < days_left <= 60:
                        expiry_notifications.append({
                            "type": "dbs_renewal",
                            "candidate_name": f"{r['first_name']} {r['last_name']}",
                            "candidate_email": r["candidate_email"],
                            "agency_email": r.get("agency_email"),
                            "agency_name": r.get("agency_name"),
                            "days_left": days_left,
                            "expiry_date": r["next_renewal"],
                        })
                except (ValueError, TypeError):
                    continue

            # Registration renewals
            reg_expiring = db.execute(
                """SELECT r.*, c.first_name, c.last_name, c.email as candidate_email,
                          a.email as agency_email, a.name as agency_name
                   FROM registration_checks r
                   JOIN candidates c ON r.candidate_id = c.id
                   LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                   LEFT JOIN agencies a ON ac.agency_id = a.id
                   WHERE r.next_check IS NOT NULL AND r.is_active = 1
                   AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
            ).fetchall()

            for row in reg_expiring:
                r = dict(row)
                try:
                    next_check = datetime.fromisoformat(r["next_check"])
                    days_left = (next_check - now).days
                    if 0 < days_left <= 30:
                        expiry_notifications.append({
                            "type": "registration_renewal",
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

            # Training certificate expiries
            try:
                training_expiring = db.execute(
                    """SELECT t.*, c.first_name, c.last_name, c.email as candidate_email,
                              a.email as agency_email, a.name as agency_name
                       FROM training_certificates t
                       JOIN candidates c ON t.candidate_id = c.id
                       LEFT JOIN agency_candidates ac ON c.id = ac.candidate_id
                       LEFT JOIN agencies a ON ac.agency_id = a.id
                       WHERE t.expiry_date IS NOT NULL AND t.status = 'valid'
                       AND (ac.employment_status = 'hired' OR ac.employment_status IS NULL)""",
                ).fetchall()

                for row in training_expiring:
                    r = dict(row)
                    try:
                        expiry = datetime.fromisoformat(r["expiry_date"])
                        days_left = (expiry - now).days
                        if 0 < days_left <= 30:
                            expiry_notifications.append({
                                "type": "training_expiry",
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
                logger.info(f"Sent {len(expiry_notifications)} expiry warning notifications")
            else:
                logger.info("No expiry warnings to send")

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
            total_candidates = db.execute("SELECT COUNT(*) as cnt FROM candidates").fetchone()
            total_candidates = dict(total_candidates)["cnt"] if total_candidates else 0

            compliant = db.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE compliance_status='compliant'"
            ).fetchone()
            compliant = dict(compliant)["cnt"] if compliant else 0

            flagged = db.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE compliance_status IN ('flagged','incomplete')"
            ).fetchone()
            flagged = dict(flagged)["cnt"] if flagged else 0

            total_agencies = db.execute("SELECT COUNT(*) as cnt FROM agencies").fetchone()
            total_agencies = dict(total_agencies)["cnt"] if total_agencies else 0

            # Revenue this week
            week_revenue = db.execute(
                "SELECT COALESCE(SUM(sell_amount),0) as total FROM invoices WHERE status='paid' AND created_at >= date('now','-7 days')"
            ).fetchone()
            week_revenue = dict(week_revenue)["total"] if week_revenue else 0

            pending_invoices = db.execute(
                "SELECT COUNT(*) as cnt, COALESCE(SUM(COALESCE(adjusted_amount, sell_amount)),0) as total FROM invoices WHERE status='pending'"
            ).fetchone()
            pi = dict(pending_invoices) if pending_invoices else {"cnt": 0, "total": 0}

            # New candidates this week
            new_candidates = db.execute(
                "SELECT COUNT(*) as cnt FROM candidates WHERE created_at >= date('now','-7 days')"
            ).fetchone()
            new_candidates = dict(new_candidates)["cnt"] if new_candidates else 0

            # Build email content
            now = datetime.now(timezone.utc)
            week_start = (now - timedelta(days=7)).strftime("%d %b %Y")
            week_end = now.strftime("%d %b %Y")

            subject = f"HealthVet AI — Weekly Report ({week_start} - {week_end})"
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
                f"— HealthVet AI Compliance Team"
            )

            # Send to all admin users
            admins = db.execute("SELECT email FROM admins").fetchall()
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
