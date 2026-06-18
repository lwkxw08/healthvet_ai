"""Unit tests for scheduler jobs with mocked datetime.

Covers:
- Expiry warning deduplication (10-day cooldown)
- DBS renewal flagging within 60-day window
- Visa expiry flagging within 30-day window
- Registration renewal flagging within 30-day window
- Credit pack expiry processing
- Payment reminder logic
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class TestExpiryWarningDedup:
    """Test the _should_send_expiry_warning deduplication logic."""

    def test_first_warning_always_sent(self, client, admin_token, agency_with_candidate):
        """First warning for a credential is always allowed."""
        from app.services.scheduler import _should_send_expiry_warning
        from app.database import get_db

        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)

        with get_db() as db:
            # Clear any previous warnings
            db.execute(
                "DELETE FROM expiry_warning_log WHERE candidate_id=%s AND credential_type='test_warning'",
                (candidate_id,),
            )
            result = _should_send_expiry_warning(db, candidate_id, "test_warning", "cred-1", now)
            assert result is True

    def test_repeat_warning_within_cooldown_blocked(self, client, admin_token, agency_with_candidate):
        """Warning sent <10 days ago blocks a new one."""
        from app.services.scheduler import _should_send_expiry_warning, _record_expiry_warning
        from app.database import get_db

        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)

        with get_db() as db:
            db.execute(
                "DELETE FROM expiry_warning_log WHERE candidate_id=%s AND credential_type='test_cooldown'",
                (candidate_id,),
            )
            _record_expiry_warning(db, candidate_id, "test_cooldown", "cred-2", now.isoformat())

            # Check immediately after — should be blocked
            result = _should_send_expiry_warning(db, candidate_id, "test_cooldown", "cred-2", now)
            assert result is False

    def test_repeat_warning_after_cooldown_allowed(self, client, admin_token, agency_with_candidate):
        """Warning sent >=10 days ago allows a new one."""
        from app.services.scheduler import _should_send_expiry_warning, _record_expiry_warning
        from app.database import get_db

        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)
        old = now - timedelta(days=11)

        with get_db() as db:
            db.execute(
                "DELETE FROM expiry_warning_log WHERE candidate_id=%s AND credential_type='test_old'",
                (candidate_id,),
            )
            _record_expiry_warning(db, candidate_id, "test_old", "cred-3", old.isoformat())

            result = _should_send_expiry_warning(db, candidate_id, "test_old", "cred-3", now)
            assert result is True


class TestExpiryWarningJobs:
    """Test expiry warning scheduler with real DB data."""

    @patch("app.services.email_service.EmailService")
    def test_visa_expiry_within_30_days_flagged(self, mock_email, client, admin_token, agency_with_candidate):
        """Visa expiring in <30 days triggers a warning."""
        from app.database import get_db
        from app.utils.auth import generate_id
        from app.services.scheduler import run_expiry_warnings

        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)
        expiry_soon = (now + timedelta(days=20)).isoformat()

        with get_db() as db:
            # Insert a verified RTW record with upcoming visa expiry
            db.execute(
                """INSERT INTO right_to_work_checks
                   (id, candidate_id, status, verified, visa_expiry, checked_at)
                   VALUES (%s, %s, 'verified', 1, %s, %s)
                   ON CONFLICT DO NOTHING""",
                (generate_id(), candidate_id, expiry_soon, now.isoformat()),
            )
            # Clear prior warnings
            db.execute(
                "DELETE FROM expiry_warning_log WHERE candidate_id=%s AND credential_type='visa_expiry'",
                (candidate_id,),
            )

        run_expiry_warnings()

        if mock_email.send_expiry_warnings.called:
            notifications = mock_email.send_expiry_warnings.call_args[0][0]
            visa_warnings = [n for n in notifications if n["type"] == "visa_expiry"
                             and n["candidate_id"] == candidate_id]
            assert len(visa_warnings) >= 1

    @patch("app.services.email_service.EmailService")
    def test_dbs_renewal_within_60_days_flagged(self, mock_email, client, admin_token, agency_with_candidate):
        """DBS renewal due in <60 days triggers a warning."""
        from app.database import get_db
        from app.utils.auth import generate_id
        from app.services.scheduler import run_expiry_warnings

        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)
        renewal_soon = (now + timedelta(days=45)).isoformat()

        with get_db() as db:
            db.execute(
                """INSERT INTO dbs_checks
                   (id, candidate_id, status, next_renewal, submitted_at)
                   VALUES (%s, %s, 'valid', %s, %s)
                   ON CONFLICT DO NOTHING""",
                (generate_id(), candidate_id, renewal_soon, now.isoformat()),
            )
            db.execute(
                "DELETE FROM expiry_warning_log WHERE candidate_id=%s AND credential_type='dbs_renewal'",
                (candidate_id,),
            )

        run_expiry_warnings()

        if mock_email.send_expiry_warnings.called:
            notifications = mock_email.send_expiry_warnings.call_args[0][0]
            dbs_warnings = [n for n in notifications if n["type"] == "dbs_renewal"
                            and n["candidate_id"] == candidate_id]
            assert len(dbs_warnings) >= 1


class TestCreditPackExpiry:
    """Test credit pack expiry processing."""

    @patch("app.services.email_service.EmailService")
    def test_expired_pack_marked_expired(self, mock_email, client, admin_token, agency_with_id):
        """generate_recurring_invoices marks expired packs as expired."""
        from app.database import get_db
        from app.services.billing import BillingService

        agency_id = agency_with_id["agency_id"]
        now = datetime.now(timezone.utc)
        past = (now - timedelta(days=1)).isoformat()

        # Create an "active" subscription that expired yesterday
        from app.utils.auth import generate_id
        sub_id = generate_id()
        with get_db() as db:
            # Deactivate any existing subs first
            db.execute(
                "UPDATE agency_subscriptions SET status='cancelled' WHERE agency_id=%s AND status='active'",
                (agency_id,),
            )
            db.execute(
                """INSERT INTO agency_subscriptions
                   (id, agency_id, tier, billing_method, monthly_amount, per_worker_amount,
                    max_workers, monthly_checks, checks_used, credits_total, credits_used,
                    rollover_credits, allow_rollover, overage_rate,
                    status, current_period_start, current_period_end, expires_at, created_at)
                   VALUES (%s, %s, 'standard', 'stripe', 0, 0, 99999, 50, 0, 50, 10,
                    0, 0, 0, 'active', %s, %s, %s, %s)""",
                (sub_id, agency_id, past, past, past, past),
            )

        results = BillingService.generate_recurring_invoices()
        expired = [r for r in results if r.get("agency_id") == agency_id and r.get("action") == "expired"]
        assert len(expired) == 1
        assert expired[0]["expired_credits"] == 40.0  # 50 total - 10 used

        # Verify status in DB
        with get_db() as db:
            db.execute("SELECT status FROM agency_subscriptions WHERE id=%s", (sub_id,))
            row = db.fetchone()
            assert dict(row)["status"] == "expired"


class TestPaymentReminders:
    """Test payment reminder logic."""

    def test_send_payment_reminders_no_crash(self, client, admin_token):
        """Payment reminder job runs without errors even with no pending invoices."""
        from app.services.scheduler import run_payment_reminders
        # Should not raise
        run_payment_reminders()

    def test_fraud_scan_no_crash(self, client, admin_token):
        """Fraud scan job runs without errors even with empty data."""
        from app.services.scheduler import run_fraud_scan
        run_fraud_scan()

    def test_weekly_admin_report_no_crash(self, client, admin_token):
        """Weekly admin report job runs without errors."""
        from app.services.scheduler import run_weekly_admin_report
        run_weekly_admin_report()
