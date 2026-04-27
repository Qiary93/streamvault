"""Backend tests for Admin Auto-Updater endpoints (StreamVault).

Covers:
- /api/admin/updates/check
- /api/admin/updates/status
- /api/admin/updates/history
- /api/admin/updates/apply
- /api/admin/updates/rollback
- 403 for non-admin users
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL")
if not BASE_URL:
    # Fallback to frontend env file
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
BASE_URL = (BASE_URL or "").rstrip("/")

ADMIN_EMAIL = "admin@streamvault.com"
ADMIN_PASSWORD = "Admin123!"
DEMO_EMAIL = "progamer@demo.com"
DEMO_PASSWORD = "Demo123!"


def _login(session, email, password):
    r = session.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    return r


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    # If token returned, attach Authorization too (defensive)
    try:
        token = r.json().get("token") or r.json().get("access_token")
        if token:
            s.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass
    return s


@pytest.fixture(scope="module")
def user_session():
    s = requests.Session()
    r = _login(s, DEMO_EMAIL, DEMO_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Demo user login failed: {r.status_code} {r.text[:200]}")
    try:
        token = r.json().get("token") or r.json().get("access_token")
        if token:
            s.headers.update({"Authorization": f"Bearer {token}"})
    except Exception:
        pass
    return s


# ---------------- /check ----------------
class TestUpdatesCheck:
    def test_check_admin_returns_supported(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/updates/check", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("supported") is True
        # required fields
        for k in ("current_sha", "current_short", "branch", "behind"):
            assert k in data, f"missing {k}"
        assert isinstance(data["current_sha"], str) and len(data["current_sha"]) >= 7
        assert "changelog" in data
        # Changelog content from fake repo
        if data.get("changelog"):
            assert "v1.2.0" in data["changelog"] or "##" in data["changelog"]

    def test_check_non_admin_forbidden(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/admin/updates/check", timeout=15)
        assert r.status_code == 403

    def test_check_unauth_forbidden(self):
        r = requests.get(f"{BASE_URL}/api/admin/updates/check", timeout=15)
        assert r.status_code in (401, 403)


# ---------------- /status ----------------
class TestUpdatesStatus:
    def test_status_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/updates/status", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "status" in data
        # Seeded fake repo has status=success
        if data.get("status") == "success":
            assert data.get("stage") == "completed"
            assert "log_tail" in data
            assert isinstance(data["log_tail"], str)

    def test_status_non_admin_forbidden(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/admin/updates/status", timeout=15)
        assert r.status_code == 403


# ---------------- /history ----------------
class TestUpdatesHistory:
    def test_history_admin(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/updates/history", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, list)
        assert len(data) >= 3
        # spot check fields
        first = data[0]
        assert "status" in first
        assert "mode" in first

    def test_history_non_admin_forbidden(self, user_session):
        r = user_session.get(f"{BASE_URL}/api/admin/updates/history", timeout=15)
        assert r.status_code == 403


# ---------------- /rollback ----------------
class TestUpdatesRollback:
    def test_rollback_empty_sha(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/updates/rollback",
            json={"target_sha": ""},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is False

    def test_rollback_short_sha(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/updates/rollback",
            json={"target_sha": "abc"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is False

    def test_rollback_valid_sha(self, admin_session):
        r = admin_session.post(
            f"{BASE_URL}/api/admin/updates/rollback",
            json={"target_sha": "abc1234567890"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True
        assert "requested_at" in data
        assert isinstance(data.get("message"), str)

    def test_rollback_non_admin_forbidden(self, user_session):
        r = user_session.post(
            f"{BASE_URL}/api/admin/updates/rollback",
            json={"target_sha": "abc1234567890"},
            timeout=15,
        )
        assert r.status_code == 403


# ---------------- /apply ----------------
class TestUpdatesApply:
    def test_apply_admin_queues(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/updates/apply", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("ok") is True

    def test_apply_non_admin_forbidden(self, user_session):
        r = user_session.post(f"{BASE_URL}/api/admin/updates/apply", timeout=15)
        assert r.status_code == 403
