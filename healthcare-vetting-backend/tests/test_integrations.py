"""Tests for REST API + Webhook integration endpoints."""


def test_create_api_key(client, agency_token):
    """Agency can create an API key."""
    resp = client.post(
        "/api/integrations/api-keys",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={
            "name": "Test Integration Key",
            "scopes": ["candidates:read", "compliance:read"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "api_key" in data
    assert data["name"] == "Test Integration Key"
    assert data["api_key"].startswith("hv_")


def test_list_api_keys(client, agency_token):
    """Agency can list their API keys."""
    # Create one first
    client.post(
        "/api/integrations/api-keys",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={"name": "List Test Key", "scopes": ["candidates:read"]},
    )
    resp = client.get(
        "/api/integrations/api-keys",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200
    keys = resp.json()
    assert isinstance(keys, list)
    assert len(keys) >= 1


def test_revoke_api_key(client, agency_token):
    """Agency can revoke an API key."""
    # Create
    create_resp = client.post(
        "/api/integrations/api-keys",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={"name": "Revoke Test Key", "scopes": ["candidates:read"]},
    )
    key_id = create_resp.json().get("key_id")
    assert key_id is not None

    # Revoke
    resp = client.delete(
        f"/api/integrations/api-keys/{key_id}",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200


def test_webhook_subscribe(client, agency_token):
    """Agency can subscribe to webhook events."""
    resp = client.post(
        "/api/integrations/webhooks",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={
            "url": "https://example.com/webhook",
            "events": ["check.completed", "candidate.status_changed"],
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "subscription_id" in data
    assert "secret" in data
    assert data["secret"].startswith("whsec_")


def test_webhook_list(client, agency_token):
    """Agency can list their webhook subscriptions."""
    # Create one first
    client.post(
        "/api/integrations/webhooks",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={
            "url": "https://example.com/webhook-list",
            "events": ["check.completed"],
        },
    )
    resp = client.get(
        "/api/integrations/webhooks",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200
    hooks = resp.json()
    assert isinstance(hooks, list)
    assert len(hooks) >= 1


def test_webhook_delete(client, agency_token):
    """Agency can delete a webhook subscription."""
    create_resp = client.post(
        "/api/integrations/webhooks",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={
            "url": "https://example.com/webhook-del",
            "events": ["check.completed"],
        },
    )
    sub_id = create_resp.json().get("subscription_id")
    assert sub_id is not None

    resp = client.delete(
        f"/api/integrations/webhooks/{sub_id}",
        headers={"Authorization": f"Bearer {agency_token}"},
    )
    assert resp.status_code == 200


def test_webhook_test_event(client, agency_token):
    """Agency can send a test webhook event."""
    # Create a webhook first
    create_resp = client.post(
        "/api/integrations/webhooks",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={
            "url": "https://httpbin.org/post",
            "events": ["check.completed"],
        },
    )
    sub_id = create_resp.json().get("subscription_id")
    assert sub_id is not None

    resp = client.post(
        "/api/integrations/webhooks/test",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={"subscription_id": sub_id},
    )
    # Should succeed (even if delivery fails due to network)
    assert resp.status_code in (200, 202)


def test_api_key_auth_public_endpoints(client, agency_token):
    """API key authentication works for public API endpoints."""
    # Create an API key
    create_resp = client.post(
        "/api/integrations/api-keys",
        headers={"Authorization": f"Bearer {agency_token}"},
        json={
            "name": "Public API Test",
            "scopes": ["candidates:read", "compliance:read", "invoices:read"],
        },
    )
    data = create_resp.json()
    raw_key = data.get("api_key")
    assert raw_key is not None

    # Use API key to access public endpoint (router prefix is /api/integrations)
    resp = client.get(
        "/api/integrations/v1/candidates",
        headers={"X-API-Key": raw_key},
    )
    assert resp.status_code == 200
    assert "candidates" in resp.json()


def test_api_key_auth_invalid_key(client):
    """Invalid API key should be rejected."""
    resp = client.get(
        "/api/integrations/v1/candidates",
        headers={"X-API-Key": "hv_invalidkey12345678901234567890123456789012345678"},
    )
    assert resp.status_code == 401


def test_api_key_auth_no_key(client):
    """Missing API key should be rejected."""
    resp = client.get("/api/integrations/v1/candidates")
    assert resp.status_code == 401
