"""Tests for security headers, CORS, and rate limiting."""


def test_security_headers_present(client):
    """Verify all OWASP security headers are set on responses."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    headers = resp.headers

    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "DENY"
    assert "max-age=" in headers.get("Strict-Transport-Security", "")
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert headers.get("X-XSS-Protection") == "0"
    assert "default-src" in headers.get("Content-Security-Policy", "")
    assert "camera=()" in headers.get("Permissions-Policy", "")


def test_request_id_header(client):
    """Verify X-Request-ID is returned on every response."""
    resp = client.get("/healthz")
    assert "X-Request-ID" in resp.headers
    assert len(resp.headers["X-Request-ID"]) > 0


def test_response_time_header(client):
    """Verify X-Response-Time is returned."""
    resp = client.get("/healthz")
    assert "X-Response-Time" in resp.headers


def test_custom_request_id_passed_through(client):
    """Verify client-provided X-Request-ID is preserved."""
    custom_id = "test-req-12345"
    resp = client.get("/healthz", headers={"X-Request-ID": custom_id})
    assert resp.headers.get("X-Request-ID") == custom_id


def test_healthz_endpoint(client):
    """Verify health check returns database status."""
    resp = client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "ok"
    assert "version" in data


def test_api_info_endpoint(client):
    """Verify API info endpoint returns expected structure."""
    resp = client.get("/api/info")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Viper AI"
    assert "features" in data
