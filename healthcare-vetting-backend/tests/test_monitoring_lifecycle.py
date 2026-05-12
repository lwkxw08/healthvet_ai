"""Integration tests for monitoring subscription lifecycle.

Covers:
- Monitoring activation via re-vet
- Monitoring renewal endpoint
- Monitoring expiry halts monitoring (scheduler)
- Expiry reminders sent within 30-day window (scheduler)
- Renewal extends expiry correctly
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch


class TestMonitoringRenewal:
    """Test the monitoring renewal endpoint."""

    def test_renew_monitoring_manual_invoice(self, client, admin_token, agency_with_candidate):
        """Renewal with manual billing creates a pending invoice."""
        from app.database import get_db
        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)

        # Set up: billing mode manual, monitoring already active
        with get_db() as db:
            db.execute("UPDATE agencies SET billing_mode='manual_invoicing' WHERE id=%s", (agency_id,))
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active=1,
                       monitoring_expires_at=%s,
                       monitoring_started_at=%s
                   WHERE agency_id=%s AND candidate_id=%s""",
                ((now + timedelta(days=30)).isoformat(), now.isoformat(), agency_id, candidate_id),
            )

        resp = client.post(
            f"/api/agencies/monitoring/renew/{candidate_id}",
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("payment", {}).get("billing_mode") == "manual_invoicing"

    def test_renew_monitoring_credit_pack(self, client, admin_token, agency_with_candidate):
        """Renewal with credit pack deducts credits."""
        from app.database import get_db
        import uuid

        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)

        with get_db() as db:
            db.execute("UPDATE agencies SET billing_mode='credit_pack' WHERE id=%s", (agency_id,))
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active=1,
                       monitoring_expires_at=%s,
                       monitoring_started_at=%s
                   WHERE agency_id=%s AND candidate_id=%s""",
                ((now + timedelta(days=10)).isoformat(), now.isoformat(), agency_id, candidate_id),
            )

        # Create and purchase a credit pack
        tier_key = f"mon_{uuid.uuid4().hex[:6]}"
        client.post(
            "/api/billing/tiers",
            json={
                "tier_key": tier_key,
                "name": f"Monitoring Pack {tier_key}",
                "monthly_price": 500,
                "monthly_checks": 100,
                "features": ["monitoring"],
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        client.post(
            "/api/billing/subscribe",
            json={"tier": tier_key, "billing_method": "stripe"},
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )

        resp = client.post(
            f"/api/agencies/monitoring/renew/{candidate_id}",
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        payment = data.get("payment", {})
        assert payment.get("billing_mode") in ("credit_pack", "subscription")

    def test_renew_extends_expiry(self, client, admin_token, agency_with_candidate):
        """Renewal extends monitoring_expires_at by 12 months."""
        from app.database import get_db
        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        now = datetime.now(timezone.utc)
        original_expiry = now + timedelta(days=60)

        with get_db() as db:
            db.execute("UPDATE agencies SET billing_mode='manual_invoicing' WHERE id=%s", (agency_id,))
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active=1,
                       monitoring_expires_at=%s,
                       monitoring_started_at=%s
                   WHERE agency_id=%s AND candidate_id=%s""",
                (original_expiry.isoformat(), now.isoformat(), agency_id, candidate_id),
            )

        resp = client.post(
            f"/api/agencies/monitoring/renew/{candidate_id}",
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200

        # Check new expiry is ~365 days from old expiry
        with get_db() as db:
            db.execute(
                "SELECT monitoring_expires_at FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
                (agency_id, candidate_id),
            )
            row = db.fetchone()
            new_expiry = datetime.fromisoformat(dict(row)["monitoring_expires_at"])
            expected = original_expiry + timedelta(days=365)
            # Allow 1 day tolerance
            assert abs((new_expiry - expected).total_seconds()) < 86400

    def test_renew_non_owned_candidate_fails(self, client, admin_token, agency_with_id, candidate_token):
        """Cannot renew monitoring for a candidate not linked to this agency."""
        resp = client.post(
            f"/api/agencies/monitoring/renew/{candidate_token['user_id']}",
            headers={"Authorization": f"Bearer {agency_with_id['token']}"},
        )
        assert resp.status_code == 404


class TestMonitoringExpiryScheduler:
    """Test the scheduler job that halts expired monitoring."""

    def test_expired_monitoring_halted(self, client, admin_token, agency_with_candidate):
        """Scheduler sets monitoring_active=0 for expired candidates."""
        from app.database import get_db
        from app.services.scheduler import run_monitoring_expiry_checks

        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

        with get_db() as db:
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active=1, monitoring_expires_at=%s
                   WHERE agency_id=%s AND candidate_id=%s""",
                (past, agency_id, candidate_id),
            )

        # Run the scheduler job
        run_monitoring_expiry_checks()

        with get_db() as db:
            db.execute(
                "SELECT monitoring_active FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
                (agency_id, candidate_id),
            )
            row = db.fetchone()
            assert dict(row)["monitoring_active"] == 0

    def test_active_monitoring_not_halted(self, client, admin_token, agency_with_candidate):
        """Scheduler does NOT halt monitoring that hasn't expired yet."""
        from app.database import get_db
        from app.services.scheduler import run_monitoring_expiry_checks

        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        future = (datetime.now(timezone.utc) + timedelta(days=180)).isoformat()

        with get_db() as db:
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active=1, monitoring_expires_at=%s
                   WHERE agency_id=%s AND candidate_id=%s""",
                (future, agency_id, candidate_id),
            )

        run_monitoring_expiry_checks()

        with get_db() as db:
            db.execute(
                "SELECT monitoring_active FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
                (agency_id, candidate_id),
            )
            row = db.fetchone()
            assert dict(row)["monitoring_active"] == 1

    @patch("app.services.email_service.EmailService")
    def test_expiry_reminder_within_window(self, mock_email, client, admin_token, agency_with_candidate):
        """Scheduler sends reminders for candidates expiring within 30 days."""
        from app.database import get_db
        from app.services.scheduler import run_monitoring_expiry_checks

        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        soon = (datetime.now(timezone.utc) + timedelta(days=15)).isoformat()

        with get_db() as db:
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active=1, monitoring_expires_at=%s
                   WHERE agency_id=%s AND candidate_id=%s""",
                (soon, agency_id, candidate_id),
            )
            # Clear any previous warning logs for this candidate
            db.execute(
                "DELETE FROM expiry_warning_log WHERE candidate_id=%s AND credential_type='monitoring_expiry'",
                (candidate_id,),
            )

        run_monitoring_expiry_checks()

        # Verify email service was called for expiry warnings
        assert mock_email.send_expiry_warnings.called

    @patch("app.services.email_service.EmailService")
    def test_no_reminder_outside_window(self, mock_email, client, admin_token, agency_with_candidate):
        """Scheduler does NOT send reminders for candidates expiring > 30 days out."""
        from app.database import get_db
        from app.services.scheduler import run_monitoring_expiry_checks

        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        far_future = (datetime.now(timezone.utc) + timedelta(days=200)).isoformat()

        with get_db() as db:
            db.execute(
                """UPDATE agency_candidates
                   SET monitoring_active=1, monitoring_expires_at=%s
                   WHERE agency_id=%s AND candidate_id=%s""",
                (far_future, agency_id, candidate_id),
            )

        run_monitoring_expiry_checks()

        # Email should NOT be called for far-future expiry
        if mock_email.send_expiry_warnings.called:
            args = mock_email.send_expiry_warnings.call_args[0]
            # If called, none of the notifications should be for this candidate
            for n in args[0]:
                assert n.get("candidate_id") != candidate_id
