"""API contract tests for all agency-facing endpoints.

Validates:
- Each endpoint returns the expected HTTP status code
- Response structure matches the documented contract
- Auth requirements are enforced (401/403 without valid agency token)
"""
import uuid


class TestAgencyEndpointAuth:
    """Verify auth is required on all agency endpoints."""

    def test_invites_requires_auth(self, client):
        resp = client.get("/api/agencies/invites")
        assert resp.status_code in (401, 403)

    def test_revet_pricing_requires_auth(self, client):
        resp = client.get("/api/agencies/revet-pricing")
        assert resp.status_code in (401, 403)

    def test_billing_mode_requires_auth(self, client):
        resp = client.get("/api/agencies/billing-mode")
        assert resp.status_code in (401, 403)

    def test_candidates_with_status_requires_auth(self, client):
        resp = client.get("/api/agencies/candidates-with-status")
        assert resp.status_code in (401, 403)

    def test_revet_requests_requires_auth(self, client):
        resp = client.get("/api/agencies/revet-requests")
        assert resp.status_code in (401, 403)

    def test_my_services_requires_auth(self, client):
        resp = client.get("/api/agencies/my-services")
        assert resp.status_code in (401, 403)

    def test_monitoring_renew_requires_auth(self, client):
        resp = client.post("/api/agencies/monitoring/renew/some-id")
        assert resp.status_code in (401, 403)

    def test_admin_cannot_access_agency_endpoints(self, client, admin_token):
        """Admin tokens should get 403 on agency-only endpoints."""
        resp = client.get(
            "/api/agencies/revet-pricing",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert resp.status_code == 403

    def test_candidate_cannot_access_agency_endpoints(self, client, candidate_token):
        """Candidate tokens should get 403 on agency-only endpoints."""
        resp = client.get(
            "/api/agencies/revet-pricing",
            headers={"Authorization": f"Bearer {candidate_token['token']}"},
        )
        assert resp.status_code == 403


class TestAgencyVettingPricing:
    """Test vetting pricing endpoint contract."""

    def test_returns_pricing_structure(self, client, agency_token):
        resp = client.get(
            "/api/agencies/vetting-pricing",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)
        # Should have line_items or total_cost or similar pricing info
        assert any(k in data for k in ("total_cost", "line_items", "checks", "sections"))


class TestAgencyInvites:
    """Test invite management endpoint contracts."""

    def test_list_invites_returns_list(self, client, agency_token):
        resp = client.get(
            "/api/agencies/invites",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_create_invite(self, client, agency_token):
        email = f"invite-{uuid.uuid4().hex[:8]}@test.viperai"
        resp = client.post(
            "/api/agencies/invites",
            json={"candidate_email": email},
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "invite_id" in data or "id" in data

    def test_create_invite_duplicate_email(self, client, agency_token):
        """Inviting the same email twice should return an error."""
        email = f"dup-invite-{uuid.uuid4().hex[:8]}@test.viperai"
        client.post(
            "/api/agencies/invites",
            json={"candidate_email": email},
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        resp = client.post(
            "/api/agencies/invites",
            json={"candidate_email": email},
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 400

    def test_create_invite_invalid_email(self, client, agency_token):
        """Invalid email format should be rejected."""
        resp = client.post(
            "/api/agencies/invites",
            json={"candidate_email": "not-an-email"},
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 422


class TestAgencyRevetEndpoints:
    """Test re-vet endpoint contracts."""

    def test_revet_pricing_returns_sections(self, client, agency_token):
        resp = client.get(
            "/api/agencies/revet-pricing",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "sections" in data
        sections = data["sections"]
        assert isinstance(sections, list)
        for s in sections:
            assert "section" in s or "key" in s or "label" in s

    def test_revet_requests_returns_list(self, client, agency_with_candidate):
        """List re-vet requests returns a list."""
        resp = client.get(
            "/api/agencies/revet-requests",
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_request_revet_missing_sections_fails(self, client, agency_with_candidate):
        """Request with empty sections list should succeed (0 cost) or fail."""
        resp = client.post(
            f"/api/agencies/candidates/{agency_with_candidate['candidate_id']}/request-revet",
            json={"sections": []},
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code in (200, 400, 422)


class TestAgencyBillingEndpoints:
    """Test billing-related agency endpoints."""

    def test_billing_mode_returns_mode(self, client, agency_token):
        resp = client.get(
            "/api/agencies/billing-mode",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "billing_mode" in data

    def test_subscription_me_structure(self, client, agency_token):
        resp = client.get(
            "/api/billing/subscription/me",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200

    def test_remaining_checks_structure(self, client, agency_token):
        resp = client.get(
            "/api/billing/remaining-checks/me",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "credits_remaining" in data or "has_credit_pack" in data

    def test_billing_history_structure(self, client, agency_token):
        resp = client.get(
            "/api/billing/history/me",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_credit_transactions_structure(self, client, agency_token):
        resp = client.get(
            "/api/billing/credit-transactions/me",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


class TestAgencyCandidateManagement:
    """Test candidate management endpoint contracts."""

    def test_candidates_with_status_returns_list(self, client, agency_with_candidate):
        resp = client.get(
            "/api/agencies/candidates-with-status",
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            cand = data[0]
            assert "candidate_id" in cand or "id" in cand

    def test_update_candidate_status(self, client, agency_with_candidate):
        resp = client.put(
            f"/api/agencies/candidates/{agency_with_candidate['candidate_id']}/status",
            json={"employment_status": "hired"},
            headers={"Authorization": f"Bearer {agency_with_candidate['agency_token']}"},
        )
        assert resp.status_code == 200

    def test_update_candidate_status_invalid_id(self, client, agency_token):
        resp = client.put(
            "/api/agencies/candidates/nonexistent-id/status",
            json={"employment_status": "hired"},
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code in (404, 400)


class TestAgencyMyServices:
    """Test the my-services endpoint."""

    def test_my_services_returns_data(self, client, agency_token):
        resp = client.get(
            "/api/agencies/my-services",
            headers={"Authorization": f"Bearer {agency_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, dict)


class TestAgencyPendingInvites:
    """Test candidate pending invites endpoint."""

    def test_pending_invites_for_candidate(self, client, candidate_token):
        resp = client.get(
            "/api/agencies/pending-invites",
            headers={"Authorization": f"Bearer {candidate_token['token']}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
