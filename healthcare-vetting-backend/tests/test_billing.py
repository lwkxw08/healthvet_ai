"""Tests for billing, subscription, and credit pack functionality."""


def test_get_subscription_tiers(client, admin_token):
    """Admin can view subscription tiers."""
    resp = client.get(
        "/api/billing/tiers",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_create_subscription_tier(client, admin_token):
    """Admin can create a new subscription tier."""
    import uuid
    tier_key = f"test_tier_{uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/billing/tiers",
        json={
            "tier_key": tier_key,
            "name": "Test Tier",
            "monthly_price": 199.99,
            "monthly_checks": 50,
            "features": ["basic_checks", "email_support"],
        },
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tier_key"] == tier_key
    assert data["name"] == "Test Tier"


def test_get_partial_credit_rates(client, admin_token):
    """Admin can view partial credit rates."""
    resp = client.get(
        "/api/billing/partial-credit-rates",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_agency_subscription_flow(client, agency_token):
    """Agency can view their subscription status."""
    resp = client.get(
        "/api/billing/subscription/me",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200


def test_agency_billing_history(client, agency_token):
    """Agency can view billing history."""
    resp = client.get(
        "/api/billing/history/me",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_agency_remaining_checks(client, agency_token):
    """Agency can check remaining credits."""
    resp = client.get(
        "/api/billing/remaining-checks/me",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200


def test_credit_transactions(client, agency_token):
    """Agency can view credit transactions."""
    resp = client.get(
        "/api/billing/credit-transactions/me",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
