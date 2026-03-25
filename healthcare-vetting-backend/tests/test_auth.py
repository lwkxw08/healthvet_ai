"""Tests for authentication endpoints."""


def test_admin_login_success(client):
    resp = client.post("/api/auth/admin/login", json={
        "email": "admin@healthvet.ai",
        "password": "admin123",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_type"] == "admin"
    assert "access_token" in data


def test_admin_login_wrong_password(client):
    resp = client.post("/api/auth/admin/login", json={
        "email": "admin@healthvet.ai",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_candidate_register_and_login(client):
    import uuid
    email = f"auth-test-{uuid.uuid4().hex[:8]}@test.healthvet"
    # Register
    resp = client.post("/api/auth/candidates/register", json={
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Auth",
        "last_name": "Test",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_type"] == "candidate"
    assert data["access_token"]

    # Login with same credentials
    resp2 = client.post("/api/auth/candidates/login", json={
        "email": email,
        "password": "SecurePass123!",
    })
    assert resp2.status_code == 200
    assert resp2.json()["user_type"] == "candidate"


def test_candidate_register_duplicate_email(client):
    import uuid
    email = f"dup-{uuid.uuid4().hex[:8]}@test.healthvet"
    client.post("/api/auth/candidates/register", json={
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Dup",
        "last_name": "Test",
    })
    # Second registration with same email should fail
    resp = client.post("/api/auth/candidates/register", json={
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Dup2",
        "last_name": "Test2",
    })
    assert resp.status_code == 400
    assert "already registered" in resp.json()["detail"].lower()


def test_candidate_login_wrong_password(client):
    import uuid
    email = f"wrongpw-{uuid.uuid4().hex[:8]}@test.healthvet"
    client.post("/api/auth/candidates/register", json={
        "email": email,
        "password": "SecurePass123!",
        "first_name": "Wrong",
        "last_name": "PW",
    })
    resp = client.post("/api/auth/candidates/login", json={
        "email": email,
        "password": "WrongPassword!",
    })
    assert resp.status_code == 401


def test_agency_register_and_login(client):
    import uuid
    email = f"agency-auth-{uuid.uuid4().hex[:8]}@test.healthvet"
    resp = client.post("/api/auth/agencies/register", json={
        "name": "Auth Test Agency",
        "email": email,
        "password": "AgencyPass123!",
        "contact_name": "Contact",
        "phone": "07700900001",
        "plan": "standard",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_type"] == "agency"

    resp2 = client.post("/api/auth/agencies/login", json={
        "email": email,
        "password": "AgencyPass123!",
    })
    assert resp2.status_code == 200


def test_token_refresh(client, admin_token):
    resp = client.post(
        "/api/auth/token/refresh",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_type"] == "admin"
    assert "access_token" in data


def test_token_refresh_no_token(client):
    resp = client.post("/api/auth/token/refresh")
    assert resp.status_code == 401
