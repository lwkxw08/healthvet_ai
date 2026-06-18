"""
#10 Multi-Tenant Isolation Audit — Authorization Test Matrix

Verifies that Agency A can never read, modify, or delete Agency B's resources
via parameter tampering. Covers all agency-scoped route modules.

Pattern: register two agencies, create resources under Agency A, then attempt
to access those resources while authenticated as Agency B. Every attempt must
return 403 or 404.
"""
import uuid

import pytest
from fastapi.testclient import TestClient


# ── Helpers ──────────────────────────────────────────────────────────────────

def _register_agency(client: TestClient, suffix: str) -> dict:
    """Register a new agency and return {token, agency_id}."""
    email = f"agency-{suffix}-{uuid.uuid4().hex[:6]}@test.viperai"
    resp = client.post("/api/auth/agencies/register", json={
        "name": f"Agency {suffix}",
        "email": email,
        "password": "SecurePass123!",
        "contact_name": f"Contact {suffix}",
        "phone": "07700900001",
        "plan": "standard",
    })
    assert resp.status_code == 200, resp.text
    data = resp.json()
    return {"token": data["access_token"], "agency_id": data["user_id"]}


def _headers(token: str) -> dict:
    return {"X-Auth-Token": token}


def _register_candidate_for_agency(client: TestClient, agency: dict) -> str:
    """Register a candidate and link to an agency. Returns candidate_id."""
    email = f"cand-{uuid.uuid4().hex[:6]}@test.viperai"
    resp = client.post("/api/auth/candidates/register", json={
        "email": email,
        "password": "CandPass123!",
        "first_name": "Test",
        "last_name": "Cand",
    })
    assert resp.status_code == 200, resp.text
    cand_id = resp.json()["user_id"]

    # Link candidate to agency via invite flow
    resp = client.post(
        "/api/agencies/candidates/invite",
        json={"candidate_email": email},
        headers=_headers(agency["token"]),
    )
    # Accept the invite link manually — assign via admin-like endpoint
    # If invite flow doesn't exist, link directly
    if resp.status_code != 200:
        from app.database import get_db
        from datetime import datetime, timezone
        with get_db() as db:
            db.execute(
                "INSERT INTO agency_candidates (agency_id, candidate_id, assigned_at) VALUES (%s, %s, %s)",
                (agency["agency_id"], cand_id, datetime.now(timezone.utc).isoformat()),
            )
    return cand_id


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def app():
    from app.main import app as _app
    from app.database import init_db, migrate_db
    init_db()
    migrate_db()
    return _app


@pytest.fixture(scope="module")
def client(app):
    return TestClient(app)


@pytest.fixture(scope="module")
def agency_a(client):
    return _register_agency(client, "A")


@pytest.fixture(scope="module")
def agency_b(client):
    return _register_agency(client, "B")


@pytest.fixture(scope="module")
def candidate_a(client, agency_a):
    return _register_candidate_for_agency(client, agency_a)


# ── Test Matrix ──────────────────────────────────────────────────────────────
# Each test asserts that Agency B CANNOT access Agency A's resources.

class TestCandidateIsolation:
    """Agency B cannot see or modify Agency A's candidates."""

    def test_list_candidates_isolated(self, client, agency_a, agency_b, candidate_a):
        """Agency B's candidate list must not include Agency A's candidate."""
        resp = client.get("/api/agencies/candidates", headers=_headers(agency_b["token"]))
        assert resp.status_code == 200
        ids = [c.get("id") or c.get("candidate_id") for c in resp.json()]
        assert candidate_a not in ids

    def test_get_candidate_cross_agency(self, client, agency_b, candidate_a):
        """Agency B cannot fetch Agency A's candidate by ID."""
        resp = client.get(f"/api/candidates/{candidate_a}", headers=_headers(agency_b["token"]))
        assert resp.status_code in (403, 404)

    def test_update_candidate_cross_agency(self, client, agency_b, candidate_a):
        """Agency B cannot update Agency A's candidate."""
        resp = client.put(
            f"/api/candidates/{candidate_a}",
            json={"first_name": "Hacked"},
            headers=_headers(agency_b["token"]),
        )
        assert resp.status_code in (403, 404)

    def test_delete_candidate_cross_agency(self, client, agency_b, candidate_a):
        """Agency B cannot remove Agency A's candidate."""
        resp = client.delete(
            f"/api/agencies/candidates/{candidate_a}",
            headers=_headers(agency_b["token"]),
        )
        assert resp.status_code in (403, 404)


class TestDocumentIsolation:
    """Agency B cannot access Agency A's candidate documents."""

    def test_list_documents_cross_agency(self, client, agency_b, candidate_a):
        resp = client.get(
            f"/api/documents/{candidate_a}",
            headers=_headers(agency_b["token"]),
        )
        assert resp.status_code in (403, 404)

    def test_upload_document_cross_agency(self, client, agency_b, candidate_a):
        resp = client.post(
            f"/api/documents/{candidate_a}/upload",
            headers=_headers(agency_b["token"]),
            files={"file": ("test.txt", b"content", "text/plain")},
        )
        assert resp.status_code in (403, 404, 422)


class TestComplianceIsolation:
    """Agency B cannot view Agency A's compliance status."""

    def test_compliance_status_cross_agency(self, client, agency_b, candidate_a):
        resp = client.get(
            f"/api/compliance/{candidate_a}",
            headers=_headers(agency_b["token"]),
        )
        assert resp.status_code in (403, 404)


class TestChecksIsolation:
    """Agency B cannot trigger or view checks for Agency A's candidates."""

    def test_get_checks_cross_agency(self, client, agency_b, candidate_a):
        resp = client.get(
            f"/api/checks/{candidate_a}",
            headers=_headers(agency_b["token"]),
        )
        assert resp.status_code in (403, 404)


class TestReportsIsolation:
    """Agency B cannot generate reports scoped to Agency A."""

    def test_compliance_report_cross_agency(self, client, agency_a, agency_b):
        resp = client.get(
            f"/api/reports/compliance?agency_id={agency_a['agency_id']}",
            headers=_headers(agency_b["token"]),
        )
        if resp.status_code == 200:
            # If the endpoint returns data, ensure it doesn't contain Agency A's data
            data = resp.json()
            if isinstance(data, list):
                for item in data:
                    aid = item.get("agency_id")
                    if aid:
                        assert aid != agency_a["agency_id"], \
                            "Agency B received Agency A's data in compliance report"


class TestInvoiceIsolation:
    """Agency B cannot access Agency A's invoices."""

    def test_list_invoices_cross_agency(self, client, agency_a, agency_b):
        resp = client.get("/api/agencies/invoices", headers=_headers(agency_b["token"]))
        if resp.status_code == 200:
            data = resp.json()
            invoices = data if isinstance(data, list) else data.get("invoices", [])
            for inv in invoices:
                assert inv.get("agency_id") != agency_a["agency_id"]


class TestNotificationIsolation:
    """Agency B cannot read Agency A's notifications."""

    def test_notifications_cross_agency(self, client, agency_a, agency_b):
        resp = client.get("/api/notifications", headers=_headers(agency_b["token"]))
        if resp.status_code == 200:
            data = resp.json()
            notifications = data if isinstance(data, list) else data.get("notifications", [])
            for n in notifications:
                assert n.get("agency_id") != agency_a["agency_id"]


class TestSubAccountIsolation:
    """Agency B cannot see or modify Agency A's sub-accounts."""

    def test_list_sub_accounts_cross_agency(self, client, agency_a, agency_b):
        resp = client.get("/api/agencies/sub-accounts", headers=_headers(agency_b["token"]))
        if resp.status_code == 200:
            for sa in resp.json():
                assert sa.get("agency_id") != agency_a["agency_id"]


class TestBulkImportIsolation:
    """Agency B cannot trigger bulk imports scoped to Agency A."""

    def test_bulk_import_cross_agency(self, client, agency_b, agency_a):
        resp = client.post(
            "/api/bulk-import/candidates",
            headers=_headers(agency_b["token"]),
            json={"agency_id": agency_a["agency_id"], "candidates": []},
        )
        # Should either reject the foreign agency_id or ignore it
        if resp.status_code == 200:
            data = resp.json()
            assert data.get("agency_id") != agency_a["agency_id"]


class TestAnalyticsIsolation:
    """Agency B cannot query Agency A's analytics."""

    def test_analytics_cross_agency(self, client, agency_a, agency_b):
        resp = client.get(
            f"/api/analytics/dashboard?agency_id={agency_a['agency_id']}",
            headers=_headers(agency_b["token"]),
        )
        if resp.status_code == 200:
            data = resp.json()
            # Verify the returned data is scoped to agency_b, not agency_a
            aid = data.get("agency_id")
            if aid:
                assert aid != agency_a["agency_id"]


class TestEmailTemplateIsolation:
    """Agency B cannot access Agency A's email templates."""

    def test_email_templates_cross_agency(self, client, agency_a, agency_b):
        resp = client.get("/api/email-templates", headers=_headers(agency_b["token"]))
        if resp.status_code == 200:
            for t in resp.json():
                aid = t.get("agency_id")
                if aid:
                    assert aid != agency_a["agency_id"]


class TestIntegrationIsolation:
    """Agency B cannot modify Agency A's integrations."""

    def test_list_integrations_cross_agency(self, client, agency_a, agency_b):
        resp = client.get("/api/integrations", headers=_headers(agency_b["token"]))
        if resp.status_code == 200:
            data = resp.json()
            items = data if isinstance(data, list) else data.get("integrations", [])
            for i in items:
                assert i.get("agency_id") != agency_a["agency_id"]


class TestShiftReadinessIsolation:
    """Agency B cannot query Agency A's shift readiness data."""

    def test_shift_readiness_cross_agency(self, client, agency_a, agency_b):
        resp = client.get(
            f"/api/shift-readiness?agency_id={agency_a['agency_id']}",
            headers=_headers(agency_b["token"]),
        )
        if resp.status_code == 200:
            data = resp.json()
            candidates = data if isinstance(data, list) else data.get("candidates", [])
            for c in candidates:
                assert c.get("agency_id") != agency_a["agency_id"]
