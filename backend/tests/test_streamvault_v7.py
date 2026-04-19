"""
Iteration 7 backend tests — SSRF-hardened VAST resolve, Profile Feed, Leaderboards,
Games autocomplete, Notifications (unread filter), grade-up helper presence.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN = {"email": "admin@streamvault.com", "password": "Admin123!"}
STREAMER = {"email": "progamer@demo.com", "password": "Demo123!"}


# ---------- Fixtures ----------

@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login_session(creds):
    """Returns a fresh requests.Session authenticated via httpOnly cookies + user dict."""
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{API}/auth/login", json=creds)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    data = r.json()
    # user_id is on the root of login response
    user = {"user_id": data.get("user_id"), "username": data.get("username"), "email": data.get("email")}
    return s, user


@pytest.fixture(scope="module")
def streamer_auth():
    sess, user = _login_session(STREAMER)
    return {"session": sess, "user": user}


@pytest.fixture(scope="module")
def admin_auth():
    sess, user = _login_session(ADMIN)
    return {"session": sess, "user": user}


@pytest.fixture(scope="module")
def anon():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---------- SSRF hardening on /api/ads/vast/resolve ----------

class TestVASTResolveSSRF:

    def test_localhost_blocked(self, api):
        r = api.get(f"{API}/ads/vast/resolve", params={"url": "http://localhost/test"})
        assert r.status_code == 400
        assert "non-public" in r.text.lower() or "address" in r.text.lower()

    def test_private_ip_blocked(self, api):
        r = api.get(f"{API}/ads/vast/resolve", params={"url": "http://192.168.1.1/x"})
        assert r.status_code == 400

    def test_loopback_ip_blocked(self, api):
        r = api.get(f"{API}/ads/vast/resolve", params={"url": "http://127.0.0.1/x"})
        assert r.status_code == 400

    def test_file_scheme_blocked(self, api):
        r = api.get(f"{API}/ads/vast/resolve", params={"url": "file:///etc/passwd"})
        assert r.status_code == 400

    def test_ftp_scheme_blocked(self, api):
        r = api.get(f"{API}/ads/vast/resolve", params={"url": "ftp://some/x"})
        assert r.status_code == 400

    def test_empty_url_blocked(self, api):
        # FastAPI query-string passes empty string; backend returns 400.
        r = api.get(f"{API}/ads/vast/resolve", params={"url": ""})
        assert r.status_code in (400, 422)

    def test_10_dot_private_blocked(self, api):
        r = api.get(f"{API}/ads/vast/resolve", params={"url": "http://10.0.0.5/x"})
        assert r.status_code == 400

    def test_link_local_blocked(self, api):
        r = api.get(f"{API}/ads/vast/resolve", params={"url": "http://169.254.169.254/latest/meta-data"})
        assert r.status_code == 400


# ---------- Profile Feed ----------

class TestProfileFeed:

    def test_post_requires_auth(self, anon):
        r = anon.post(f"{API}/my/feed", json={"content": "hi"})
        assert r.status_code in (401, 403)

    def test_post_empty_content_rejected(self, streamer_auth):
        r = streamer_auth["session"].post(f"{API}/my/feed", json={"content": "   "})
        assert r.status_code == 400

    def test_post_then_get_then_delete(self, api, streamer_auth, admin_auth):
        content = "TEST_feed_post_iter7 hello world"
        # CREATE
        r = streamer_auth["session"].post(f"{API}/my/feed", json={"content": content})
        assert r.status_code == 200, r.text
        post = r.json()
        assert "post_id" in post
        assert post["content"] == content
        assert post["user_id"] == streamer_auth["user"]["user_id"]
        post_id = post["post_id"]

        # GET via public feed
        uid = streamer_auth["user"]["user_id"]
        r2 = api.get(f"{API}/users/{uid}/feed")
        assert r2.status_code == 200
        data = r2.json()
        assert "items" in data and "total" in data
        assert any(it.get("post_id") == post_id for it in data["items"]), "new post should appear in user feed"

        # DELETE as non-owner (admin) → 404
        r3 = admin_auth["session"].delete(f"{API}/my/feed/{post_id}")
        assert r3.status_code == 404

        # DELETE as owner → 200
        r4 = streamer_auth["session"].delete(f"{API}/my/feed/{post_id}")
        assert r4.status_code == 200

        # Confirm deleted
        r5 = api.get(f"{API}/users/{uid}/feed")
        assert not any(it.get("post_id") == post_id for it in r5.json()["items"])


# ---------- Leaderboards ----------

class TestLeaderboards:

    def test_donors_all(self, api):
        r = api.get(f"{API}/leaderboard/donors", params={"period": "all", "limit": 10})
        assert r.status_code == 200
        data = r.json()
        assert data.get("period") == "all"
        assert "items" in data
        for i, it in enumerate(data["items"]):
            assert it.get("rank") == i + 1
            assert "user_id" in it
            assert "username" in it
            assert "total" in it
            assert "count" in it

    def test_donors_month_week(self, api):
        for p in ("month", "week"):
            r = api.get(f"{API}/leaderboard/donors", params={"period": p})
            assert r.status_code == 200
            assert r.json().get("period") == p

    def test_donors_streamer_filter(self, api, streamer_auth):
        uid = streamer_auth["user"]["user_id"]
        r = api.get(f"{API}/leaderboard/donors", params={"streamer_id": uid})
        assert r.status_code == 200
        data = r.json()
        assert data.get("streamer_id") == uid

    def test_subscribers_global(self, api):
        r = api.get(f"{API}/leaderboard/subscribers")
        assert r.status_code == 200
        data = r.json()
        assert "items" in data
        for i, it in enumerate(data["items"]):
            assert it.get("rank") == i + 1
            assert "user_id" in it

    def test_subscribers_per_streamer(self, api, streamer_auth):
        uid = streamer_auth["user"]["user_id"]
        r = api.get(f"{API}/leaderboard/subscribers", params={"streamer_id": uid})
        assert r.status_code == 200
        data = r.json()
        assert data.get("streamer_id") == uid
        assert "items" in data


# ---------- Games autocomplete ----------

class TestGamesSearch:

    def test_search_valorant(self, api):
        r = api.get(f"{API}/games/search", params={"q": "val"})
        assert r.status_code == 200
        items = r.json().get("items", [])
        names_lower = [g.lower() for g in items]
        assert any("valorant" in n for n in names_lower)
        assert any("valheim" in n for n in names_lower)

    def test_search_empty_returns_first_n(self, api):
        r = api.get(f"{API}/games/search", params={"q": "", "limit": 5})
        assert r.status_code == 200
        items = r.json().get("items", [])
        assert len(items) == 5

    def test_search_no_matches(self, api):
        r = api.get(f"{API}/games/search", params={"q": "zzzzznotareal"})
        assert r.status_code == 200
        assert r.json().get("items", []) == []


# ---------- Notifications unread filter ----------

class TestNotifications:

    def test_notifications_unread_filter(self, streamer_auth):
        s = streamer_auth["session"]
        # Get all
        r_all = s.get(f"{API}/notifications")
        assert r_all.status_code == 200
        assert isinstance(r_all.json(), list)

        # Get unread
        r_un = s.get(f"{API}/notifications", params={"unread": "true", "limit": 20})
        assert r_un.status_code == 200
        items = r_un.json()
        assert isinstance(items, list)
        for n in items:
            assert n.get("read", False) is False


# ---------- Achievements + grade-up helper presence ----------

class TestAchievementsGradeHelper:

    def test_my_achievements_returns_grade_field(self, streamer_auth):
        s = streamer_auth["session"]
        r = s.get(f"{API}/my/achievements")
        assert r.status_code == 200
        data = r.json()
        assert "grade" in data
        assert "grades" in data
        # Idempotent second call
        r2 = s.get(f"{API}/my/achievements")
        assert r2.status_code == 200
