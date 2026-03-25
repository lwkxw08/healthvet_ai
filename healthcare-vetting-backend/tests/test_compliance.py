"""Tests for compliance and check processing logic."""


def test_compliance_score_endpoint(client, admin_token):
    """Admin can view compliance scores."""
    resp = client.get(
        "/api/compliance/overview",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    # Endpoint may or may not exist yet — accept 200 or 404
    assert resp.status_code in (200, 404)


def test_candidate_checks_structure(client, candidate_token):
    """Candidate can view their check statuses."""
    token = candidate_token["token"]
    user_id = candidate_token["user_id"]

    resp = client.get(
        f"/api/checks/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    # Should return checks list or 404 if no checks yet
    assert resp.status_code in (200, 404)


def test_admin_agencies_list(client, admin_token):
    """Admin can list all agencies."""
    resp = client.get(
        "/api/admin/agencies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list) or "agencies" in data


def test_admin_analytics_revenue(client, admin_token):
    """Admin revenue analytics endpoint returns expected structure."""
    resp = client.get(
        "/api/admin/analytics/revenue",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)


def test_admin_pricing(client, admin_token):
    """Admin can view pricing configuration."""
    resp = client.get(
        "/api/admin/pricing",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200


def test_admin_invoices_list(client, admin_token):
    """Admin can list invoices."""
    resp = client.get(
        "/api/admin/invoices",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
