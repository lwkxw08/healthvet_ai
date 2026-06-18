"""Shared test fixtures for the Viper AI test suite."""
import os
import sys
import tempfile

import pytest
from fastapi.testclient import TestClient

# Ensure the app package is importable
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use a temporary database for every test session
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_PATH"] = _tmp_db.name
# Disable rate limiting in tests
os.environ["RATE_LIMIT_ENABLED"] = "0"
# Seed admin with known test password
os.environ.setdefault("ADMIN_PASSWORD", "admin123")


@pytest.fixture(scope="session")
def app():
    """Create the FastAPI application with a fresh test database."""
    from app.main import app as _app
    from app.database import init_db, migrate_db

    init_db()
    migrate_db()
    return _app


@pytest.fixture(scope="session")
def client(app):
    """HTTP test client."""
    return TestClient(app)


@pytest.fixture()
def admin_token(client):
    """Get a valid admin JWT token."""
    resp = client.post("/api/auth/admin/login", json={
        "email": "admin@viperai.io",
        "password": "admin123",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture()
def agency_token(client):
    """Register a test agency and return its JWT token."""
    import uuid
    email = f"agency-{uuid.uuid4().hex[:8]}@test.viperai"
    resp = client.post("/api/auth/agencies/register", json={
        "name": "Test Agency",
        "email": email,
        "password": "TestPassword123!",
        "contact_name": "Test Contact",
        "phone": "07700900000",
        "plan": "standard",
    })
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture()
def candidate_token(client):
    """Register a test candidate and return its JWT + user_id."""
    import uuid
    email = f"cand-{uuid.uuid4().hex[:8]}@test.viperai"
    resp = client.post("/api/auth/candidates/register", json={
        "email": email,
        "password": "TestPassword123!",
        "first_name": "Test",
        "last_name": "Candidate",
    })
    assert resp.status_code == 200
    data = resp.json()
    return {"token": data["access_token"], "user_id": data["user_id"]}


@pytest.fixture()
def agency_with_id(client):
    """Register an agency and return (token, agency_id)."""
    import uuid
    from jose import jwt as jose_jwt
    email = f"agency-{uuid.uuid4().hex[:8]}@test.viperai"
    resp = client.post("/api/auth/agencies/register", json={
        "name": "Billing Test Agency",
        "email": email,
        "password": "TestPassword123!",
        "contact_name": "Billing Contact",
        "phone": "07700900001",
        "plan": "standard",
    })
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    payload = jose_jwt.get_unverified_claims(token)
    return {"token": token, "agency_id": payload["sub"], "email": email}


@pytest.fixture()
def agency_with_candidate(client, agency_with_id, candidate_token):
    """Set up an agency with a linked candidate. Returns dict with both."""
    from app.database import get_db
    from datetime import datetime, timezone
    agency_id = agency_with_id["agency_id"]
    candidate_id = candidate_token["user_id"]
    now = datetime.now(timezone.utc).isoformat()
    with get_db() as db:
        db.execute(
            "SELECT agency_id FROM agency_candidates WHERE agency_id=%s AND candidate_id=%s",
            (agency_id, candidate_id),
        )
        if not db.fetchone():
            db.execute(
                """INSERT INTO agency_candidates
                   (agency_id, candidate_id, employment_status, assigned_at)
                   VALUES (%s, %s, 'hired', %s)""",
                (agency_id, candidate_id, now),
            )
    return {
        "agency_token": agency_with_id["token"],
        "agency_id": agency_id,
        "candidate_id": candidate_id,
        "candidate_token": candidate_token["token"],
    }
