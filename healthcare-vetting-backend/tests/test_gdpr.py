"""Tests for GDPR compliance endpoints."""


def test_privacy_notice_public(client):
    """Privacy notice should be publicly accessible without auth."""
    resp = client.get("/api/gdpr/privacy-notice")
    assert resp.status_code == 200
    data = resp.json()
    # The API uses "controller" not "data_controller"
    assert "controller" in data
    assert "rights" in data
    assert "data_collected" in data


def test_retention_policies_list(client, admin_token):
    """Admin can list retention policies."""
    resp = client.get(
        "/api/gdpr/retention-policies",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_retention_policy_create(client, admin_token):
    """Admin can create a retention policy."""
    import uuid
    category = f"test_data_{uuid.uuid4().hex[:6]}"
    resp = client.post(
        "/api/gdpr/retention-policies",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "data_category": category,
            "retention_period_days": 365,
            "legal_basis": "Legitimate interest",
            "description": "Test retention policy",
            "auto_delete": False,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "policy_id" in data
    assert "created_at" in data


def test_dpia_crud(client, admin_token):
    """Admin can create, list, and update DPIAs."""
    # Create
    resp = client.post(
        "/api/gdpr/dpias",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Test DPIA",
            "description": "Testing data processing impact assessment",
            "data_types": "personal data, health records",
            "processing_purpose": "Healthcare vetting",
            "risk_level": "medium",
            "mitigations": "Encryption at rest, access controls",
        },
    )
    assert resp.status_code == 200
    dpia_id = resp.json()["dpia_id"]

    # List
    resp = client.get(
        "/api/gdpr/dpias",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    dpias = resp.json()
    assert any(d["id"] == dpia_id for d in dpias)

    # Update (must send all required fields)
    resp = client.put(
        f"/api/gdpr/dpias/{dpia_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "title": "Test DPIA Updated",
            "description": "Testing data processing impact assessment updated",
            "data_types": "personal data, health records",
            "processing_purpose": "Healthcare vetting",
            "risk_level": "low",
            "mitigations": "Encryption at rest, access controls",
            "status": "approved",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"


def test_consent_record_and_history(client, candidate_token):
    """Candidate can record consent and view consent history."""
    token = candidate_token["token"]
    user_id = candidate_token["user_id"]

    # Record consent (schema: consent_type, consent_given, privacy_policy_version, terms_version)
    resp = client.post(
        "/api/gdpr/consent",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "consent_type": "data_processing",
            "consent_given": True,
            "privacy_policy_version": "1.0",
            "terms_version": "1.0",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "consent_id" in data

    # View consent history
    resp = client.get(
        f"/api/gdpr/consent/{user_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    consents = resp.json()
    assert len(consents) >= 1


def test_data_export_candidate(client, candidate_token):
    """Candidate can request a data export (SAR)."""
    token = candidate_token["token"]
    user_id = candidate_token["user_id"]

    resp = client.post(
        "/api/gdpr/data-export",
        headers={"Authorization": f"Bearer {token}"},
        json={"candidate_id": user_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "candidate_id" in data
    assert "sections" in data
    assert "exported_at" in data


def test_erasure_request(client, admin_token, candidate_token):
    """Admin can request erasure of a candidate."""
    user_id = candidate_token["user_id"]

    resp = client.post(
        "/api/gdpr/erasure-request",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "candidate_id": user_id,
            "reason": "Candidate requested deletion under GDPR Article 17",
            "confirmed": True,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert "erasure_id" in data


def test_erasure_requests_audit_trail(client, admin_token):
    """Admin can view erasure request audit trail."""
    resp = client.get(
        "/api/gdpr/erasure-requests",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_privacy_notice_content_structure(client):
    """Privacy notice should contain all GDPR-required sections."""
    resp = client.get("/api/gdpr/privacy-notice")
    data = resp.json()
    # Must include data controller info
    assert "HealthVet" in data.get("controller", {}).get("name", "")
    # Must include rights
    rights = data.get("rights", [])
    assert len(rights) > 0
    assert any("access" in r.lower() for r in rights)
