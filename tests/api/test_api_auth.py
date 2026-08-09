"""Integration tests for Authentication and Identity API routes (browser PKCE + session store)."""

from unittest.mock import patch, MagicMock
from starlette.testclient import TestClient


def test_auth_session_unauthenticated(client: TestClient):
    """Without a session token, returns unauthenticated but valid structure."""
    resp = client.get("/api/v1/auth/session")
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is False
    assert data["auth_mode"] == "unauthenticated"
    assert "note" in data["claims"]


def test_auth_session_invalid_token_returns_401(client: TestClient):
    """A bogus session token must return 401."""
    resp = client.get(
        "/api/v1/auth/session",
        headers={"X-Session-Token": "00000000-dead-beef-0000-000000000000"},
    )
    assert resp.status_code == 401


def test_auth_login_initiates_flow(client: TestClient):
    """POST /auth/login returns flow_id, login_url with PKCE params, and poll_url."""
    # Patch the callback server thread so it doesn't actually bind to :8100 during tests
    with patch("pie.api.routers.auth.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/api/v1/auth/login")

    assert resp.status_code == 200
    data = resp.json()
    assert "flow_id" in data
    assert "login_url" in data
    assert "login.microsoftonline.com" in data["login_url"]
    assert "04b07795-8ddb-461a-bbee-02f9e1bf7b46" in data["login_url"]
    assert "code_challenge" in data["login_url"]
    assert "S256" in data["login_url"]
    assert "poll_url" in data
    assert data["flow_id"] in data["poll_url"]


def test_auth_poll_unknown_flow_returns_404(client: TestClient):
    """Polling an unknown flow_id returns 404."""
    resp = client.get("/api/v1/auth/poll/nonexistent-flow-id-xyz")
    assert resp.status_code == 404


def test_auth_poll_pending_flow(client: TestClient):
    """Polling a freshly initiated flow returns pending status."""
    with patch("pie.api.routers.auth.threading.Thread") as mock_thread:
        mock_thread.return_value = MagicMock()
        resp = client.post("/api/v1/auth/login")
    flow_id = resp.json()["flow_id"]

    poll = client.get(f"/api/v1/auth/poll/{flow_id}")
    assert poll.status_code == 200
    assert poll.json()["status"] == "pending"


def test_auth_logout_without_session(client: TestClient):
    """Logout with no session token returns graceful no-session response."""
    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["status"] == "no_session"


def test_auth_session_store_lifecycle():
    """Unit-test the session store create/get/delete lifecycle directly."""
    from pie.auth.session_store import SessionStore

    store = SessionStore()
    session = store.create_session(
        tenant_id="tenant-abc",
        user_id="dev@company.com",
        display_name="Dev User",
        access_token="fake-arm-token",
        expires_in_seconds=3600,
    )
    assert session.session_token
    assert not session.is_expired
    assert store.active_count() == 1

    found = store.get_session(session.session_token)
    assert found is not None
    assert found.user_id == "dev@company.com"

    store.delete_session(session.session_token)
    assert store.get_session(session.session_token) is None
    assert store.active_count() == 0


def test_auth_session_with_valid_token(client: TestClient):
    """A valid session token from the store must return authenticated=True."""
    from pie.auth.session_store import get_session_store

    store = get_session_store()
    session = store.create_session(
        tenant_id="6df067fb-6816-4dc8-af4d-07eba42c900b",
        user_id="engineer@watco.com",
        display_name="Watco Engineer",
        access_token="real-arm-token",
        expires_in_seconds=3600,
    )

    resp = client.get(
        "/api/v1/auth/session",
        headers={"X-Session-Token": session.session_token},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["authenticated"] is True
    assert data["user_id"] == "engineer@watco.com"
    assert data["tenant_id"] == "6df067fb-6816-4dc8-af4d-07eba42c900b"
    assert data["auth_mode"] == "oauth2_pkce_browser"

    # Cleanup
    store.delete_session(session.session_token)
