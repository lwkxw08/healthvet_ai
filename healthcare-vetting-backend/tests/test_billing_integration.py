"""Integration tests for credit pack billing, re-vet billing, and invoice generation.

Covers:
- Credit pack purchase and credit deduction
- Re-vet billing (credit pack, manual invoicing, online payment)
- Invoice generation for various billing modes
- Credit exhaustion and PAYG fallback
- Credit pack top-up and carry-over
"""
import uuid

from jose import jwt as jose_jwt


# ── Credit Pack Purchase ────────────────────────────────────────


def _create_credit_pack_tier(client, admin_token, tier_key=None, credits=100, price=500):
    """Helper: create a credit pack tier and return its key."""
    tier_key = tier_key or f"test_{uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/billing/tiers",
        json={
            "tier_key": tier_key,
            "name": f"Test Pack {tier_key}",
            "monthly_price": price,
            "monthly_checks": credits,
            "features": ["basic_checks"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    return tier_key


def _purchase_credit_pack(client, agency_token, tier_key):
    """Helper: purchase a credit pack for the agency behind the token."""
    resp = client.post(
        "/api/billing/subscribe",
        json={"agency_id": "me", "tier": tier_key, "billing_method": "stripe"},
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200
    return resp.json()


def _get_agency_id(token):
    payload = jose_jwt.get_unverified_claims(token)
    return payload["sub"]


class TestCreditPackPurchase:
    """Verify end-to-end credit pack purchase flow."""

    def test_purchase_creates_subscription(self, client, admin_token, agency_with_id):
        tier_key = _create_credit_pack_tier(client, admin_token, credits=50, price=250)
        token = agency_with_id["token"]

        sub = _purchase_credit_pack(client, token, tier_key)
        assert sub["tier"] == tier_key
        assert sub["status"] == "active"
        assert float(sub["credits_total"]) == 50.0
        assert float(sub["credits_used"]) == 0

    def test_purchase_creates_invoice(self, client, admin_token, agency_with_id):
        tier_key = _create_credit_pack_tier(client, admin_token, credits=30, price=150)
        token = agency_with_id["token"]
        _purchase_credit_pack(client, token, tier_key)

        resp = client.get(
            "/api/billing/history/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        invoices = resp.json()
        credit_invoices = [i for i in invoices if i.get("check_type") == "credit_pack"]
        assert len(credit_invoices) >= 1
        latest = credit_invoices[0]
        assert float(latest["sell_amount"]) == 150.0

    def test_remaining_checks_after_purchase(self, client, admin_token, agency_with_id):
        tier_key = _create_credit_pack_tier(client, admin_token, credits=75, price=375)
        token = agency_with_id["token"]
        _purchase_credit_pack(client, token, tier_key)

        resp = client.get(
            "/api/billing/remaining-checks/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_credit_pack"] is True
        assert float(data["credits_remaining"]) >= 75.0


class TestCreditDeduction:
    """Verify credit deduction when billing a check."""

    def test_use_subscription_check_deducts_credits(self, client, admin_token, agency_with_id):
        tier_key = _create_credit_pack_tier(client, admin_token, credits=10, price=100)
        token = agency_with_id["token"]
        _purchase_credit_pack(client, token, tier_key)

        agency_id = agency_with_id["agency_id"]

        from app.services.billing import BillingService
        result = BillingService.use_subscription_check(
            agency_id, "fake-candidate-id", "Test DBS Check",
            sell_amount=50.0, cost_amount=10.0, check_type="full_vetting",
        )
        assert result["within_credit"] is True
        assert result["status"] == "paid"
        assert result["credits_consumed"] > 0

    def test_credit_exhaustion_creates_payg_invoice(self, client, admin_token, agency_with_id):
        tier_key = _create_credit_pack_tier(client, admin_token, credits=1, price=10)
        token = agency_with_id["token"]
        _purchase_credit_pack(client, token, tier_key)

        agency_id = agency_with_id["agency_id"]
        from app.services.billing import BillingService

        # Use up the single credit
        BillingService.use_subscription_check(
            agency_id, "fake-cand-1", "First check", 50.0, 10.0, "full_vetting",
        )
        # Second check should fall back to PAYG
        result = BillingService.use_subscription_check(
            agency_id, "fake-cand-2", "Second check", 50.0, 10.0, "full_vetting",
        )
        assert result["within_credit"] is False
        assert "invoice_id" in result

    def test_credit_transaction_recorded(self, client, admin_token, agency_with_id):
        tier_key = _create_credit_pack_tier(client, admin_token, credits=20, price=200)
        token = agency_with_id["token"]
        _purchase_credit_pack(client, token, tier_key)

        agency_id = agency_with_id["agency_id"]
        from app.services.billing import BillingService
        BillingService.use_subscription_check(
            agency_id, "fake-cand-txn", "Txn Test", 50.0, 10.0, "full_vetting",
        )

        resp = client.get(
            "/api/billing/credit-transactions/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        txns = resp.json()
        assert len(txns) >= 1
        assert any(t.get("candidate_id") == "fake-cand-txn" for t in txns)


class TestCreditPackTopUp:
    """Verify credit carry-over on top-up."""

    def test_topup_carries_over_remaining(self, client, admin_token, agency_with_id):
        tier_a = _create_credit_pack_tier(client, admin_token, credits=20, price=100)
        tier_b = _create_credit_pack_tier(client, admin_token, credits=30, price=200)
        token = agency_with_id["token"]

        # Buy first pack
        _purchase_credit_pack(client, token, tier_a)

        # Use 5 credits
        agency_id = agency_with_id["agency_id"]
        from app.services.billing import BillingService
        for i in range(5):
            BillingService.use_subscription_check(
                agency_id, f"carry-{i}", f"Check {i}", 10.0, 2.0, "full_vetting",
            )

        # Top up with second pack — should carry 15 remaining
        sub = _purchase_credit_pack(client, token, tier_b)
        # 30 new + 15 remaining = 45
        assert float(sub["credits_total"]) == 45.0


# ── Re-Vet Billing ────────────────────────────────────────────


class TestRevetBilling:
    """Test re-vet request billing flows."""

    def test_revet_manual_invoice_billing(self, client, admin_token, agency_with_candidate):
        """Agency with manual_invoicing gets a pending invoice for re-vet."""
        from app.database import get_db
        agency_id = agency_with_candidate["agency_id"]
        # Ensure billing mode is manual
        with get_db() as db:
            db.execute("UPDATE agencies SET billing_mode='manual_invoicing' WHERE id=%s", (agency_id,))

        resp = client.post(
            f"/api/agencies/candidates/{agency_with_candidate['candidate_id']}/request-revet",
            json={"sections": ["dbs"]},
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data.get("payment", {}).get("billing_mode") == "manual_invoicing"

    def test_revet_credit_pack_billing(self, client, admin_token, agency_with_candidate):
        """Agency with credit pack pays via credit deduction."""
        from app.database import get_db
        agency_id = agency_with_candidate["agency_id"]
        # Set billing mode
        with get_db() as db:
            db.execute("UPDATE agencies SET billing_mode='credit_pack' WHERE id=%s", (agency_id,))

        tier_key = _create_credit_pack_tier(client, admin_token, credits=100, price=500)
        _purchase_credit_pack(client, agency_with_candidate["agency_token"], tier_key)

        resp = client.post(
            f"/api/agencies/candidates/{agency_with_candidate['candidate_id']}/request-revet",
            json={"sections": ["dbs", "rtw"]},
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data

    def test_revet_invalid_section_rejected(self, client, agency_with_candidate):
        """Invalid section names are rejected."""
        resp = client.post(
            f"/api/agencies/candidates/{agency_with_candidate['candidate_id']}/request-revet",
            json={"sections": ["invalid_section"]},
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 400

    def test_revet_monitoring_activates_monitoring(self, client, admin_token, agency_with_candidate):
        """Re-vet with monitoring section activates monitoring on the candidate."""
        from app.database import get_db
        agency_id = agency_with_candidate["agency_id"]
        candidate_id = agency_with_candidate["candidate_id"]
        with get_db() as db:
            db.execute("UPDATE agencies SET billing_mode='manual_invoicing' WHERE id=%s", (agency_id,))

        resp = client.post(
            f"/api/agencies/candidates/{candidate_id}/request-revet",
            json={"sections": ["monitoring"]},
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200

        # Verify monitoring_active was set
        with get_db() as db:
            db.execute(
                "SELECT monitoring_active, monitoring_expires_at FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
                (agency_id, candidate_id),
            )
            row = db.fetchone()
            ac = dict(row)
            assert ac["monitoring_active"] == 1
            assert ac["monitoring_expires_at"] is not None

    def test_revet_pricing_endpoint(self, client, agency_with_candidate):
        """Agency can fetch re-vet pricing."""
        resp = client.get(
            "/api/agencies/revet-pricing",
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data
        assert isinstance(data["sections"], list)


# ── Invoice Generation ─────────────────────────────────────────


class TestInvoiceGeneration:
    """Test invoice creation across different billing paths."""

    def test_manual_invoice_creation_by_admin(self, client, admin_token, agency_with_candidate):
        """Admin can create a manual invoice for an agency."""
        resp = client.post(
            "/api/admin/invoices",
            json={
                "agency_id": agency_with_candidate["agency_id"],
                "description": "Manual test invoice",
                "sell_amount": 99.99,
                "cost_amount": 20.0,
            },
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "invoice_id" in data or "id" in data

    def test_invoice_appears_in_agency_history(self, client, admin_token, agency_with_id):
        """Invoices created appear in agency billing history."""
        token = agency_with_id["token"]
        # Create a credit pack to generate an invoice
        tier_key = _create_credit_pack_tier(client, admin_token, credits=5, price=25)
        _purchase_credit_pack(client, token, tier_key)

        resp = client.get(
            "/api/billing/history/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        invoices = resp.json()
        assert len(invoices) >= 1
        assert all("id" in inv for inv in invoices)
        assert all("status" in inv for inv in invoices)

    def test_invoice_list_admin(self, client, admin_token):
        """Admin can list all invoices."""
        resp = client.get(
            "/api/admin/invoices",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_no_subscription_creates_payg_invoice(self, client, admin_token):
        """Agency without credit pack gets a PAYG invoice when billing a check."""
        # Register a fresh agency with no credit pack
        email = f"payg-{uuid.uuid4().hex[:8]}@test.viperai"
        resp = client.post("/api/auth/agencies/register", json={
            "name": "PAYG Test Agency",
            "email": email,
            "password": "TestPassword123!",
            "contact_name": "PAYG Contact",
            "phone": "07700900099",
            "plan": "standard",
        })
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        payload = jose_jwt.get_unverified_claims(token)
        agency_id = payload["sub"]

        from app.services.billing import BillingService
        result = BillingService.use_subscription_check(
            agency_id, "fake-payg-cand", "DBS Check", 77.0, 15.0, "full_vetting",
        )
        assert result["within_credit"] is False
        assert result["status"] == "pending"
        assert "invoice_id" in result
