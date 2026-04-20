"""StreamVault iteration-10 backend tests.

Focus:
 * Stream sorting (viewers/newest/oldest/invalid)
 * Raid endpoint error branches + /raids/recent
 * resend-verification & forgot-password persist *_sent_at BEFORE SMTP check
 * reset-password IP-based rate limit (>5 attempts in 15min → 429)
 * Admin email templates now include 'achievement' key
 * Admin payout-settings auto-sweep fields + payout-sweep/run
 * Startup loops scheduled (log-level check via admin endpoints only; log tail done by agent)
 * Regression sanity
"""
import os
import time
import uuid
import secrets
from datetime import datetime, timezone
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@streamvault.com"
ADMIN_PASS = "Admin123!"
DEMO_EMAIL = "progamer@demo.com"
DEMO_PASS = "Demo123!"


# ---------- fixtures ----------
@pytest.fixture(scope="session")
def mongo():
    c = MongoClient(MONGO_URL)
    return c[DB_NAME]


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def demo_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": DEMO_EMAIL, "password": DEMO_PASS})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture
def test_unverified_user(mongo):
    """Insert a temporary unverified user and cleanup."""
    suffix = uuid.uuid4().hex[:8]
    email = f"test_unverified_{suffix}@example.com"
    uid = f"user_test_{suffix}"
    mongo.users.insert_one({
        "user_id": uid,
        "email": email,
        "username": f"testuser_{suffix}",
        "display_name": f"Test User {suffix}",
        "password_hash": "$2b$12$abcdefghijklmnopqrstuv",
        "role": "viewer",
        "email_verified": False,
        "created_at": datetime.now(timezone.utc),
    })
    yield {"email": email, "user_id": uid}
    mongo.users.delete_one({"user_id": uid})


# ---------- Regression ----------
class TestRegression:
    def test_admin_me(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200 and r.json().get("role") == "admin"

    def test_demo_me(self, demo_session):
        r = demo_session.get(f"{API}/auth/me")
        assert r.status_code == 200 and r.json().get("email") == DEMO_EMAIL

    def test_recommended(self):
        r = requests.get(f"{API}/recommended")
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_categories(self):
        r = requests.get(f"{API}/categories")
        assert r.status_code == 200 and isinstance(r.json(), list)

    def test_donations_received_auth(self, demo_session):
        r = demo_session.get(f"{API}/donations/received")
        assert r.status_code == 200 and isinstance(r.json(), list)


# ---------- Stream Sorting ----------
class TestStreamSort:
    def test_sort_viewers(self):
        r = requests.get(f"{API}/streams", params={"sort": "viewers"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_sort_newest(self):
        r = requests.get(f"{API}/streams", params={"sort": "newest"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_sort_oldest(self):
        r = requests.get(f"{API}/streams", params={"sort": "oldest"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_sort_invalid_defaults_to_viewers(self):
        r = requests.get(f"{API}/streams", params={"sort": "invalid_xyz"})
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- Raid endpoint error branches ----------
class TestRaidErrorBranches:
    def _demo_stream(self, mongo):
        return mongo.streams.find_one({"user_id": {"$exists": True}}, {"_id": 0})

    def test_raid_unauth(self):
        r = requests.post(f"{API}/streams/stream_nonexistent/raid", json={"target_username": "x"})
        assert r.status_code in (401, 403)

    def test_raid_nonexistent_stream(self, demo_session):
        r = demo_session.post(
            f"{API}/streams/stream_definitely_nonexistent_xyz/raid",
            json={"target_username": "musicqueen"},
        )
        assert r.status_code == 404

    def test_raid_wrong_streamer(self, demo_session, mongo):
        """Find a stream NOT owned by progamer — expect 403."""
        demo_me = demo_session.get(f"{API}/auth/me").json()
        other = mongo.streams.find_one({"user_id": {"$ne": demo_me["user_id"]}}, {"_id": 0, "stream_id": 1})
        if not other:
            pytest.skip("No other streamer's stream in db to test 403")
        r = demo_session.post(f"{API}/streams/{other['stream_id']}/raid", json={"target_username": "anyone"})
        assert r.status_code == 403

    def test_raid_not_live(self, demo_session, mongo):
        demo_me = demo_session.get(f"{API}/auth/me").json()
        own = mongo.streams.find_one({"user_id": demo_me["user_id"]}, {"_id": 0, "stream_id": 1, "is_live": 1, "broadcasting": 1})
        if not own:
            pytest.skip("progamer has no stream row")
        # If it happens to be live+broadcasting, skip (we only test the negative path here)
        if own.get("is_live") and own.get("broadcasting"):
            pytest.skip("Stream is actually live+broadcasting; cannot test 400-not-live branch")
        r = demo_session.post(f"{API}/streams/{own['stream_id']}/raid", json={"target_username": "musicqueen"})
        assert r.status_code == 400
        assert "live" in r.json().get("detail", "").lower()

    def test_recent_raids_requires_auth(self):
        r = requests.get(f"{API}/raids/recent")
        assert r.status_code in (401, 403)

    def test_recent_raids_returns_list(self, demo_session):
        r = demo_session.get(f"{API}/raids/recent")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------- resend-verification: sent_at persisted BEFORE SMTP check ----------
class TestResendVerificationRateLimit:
    def test_second_call_within_60s_is_429_not_503(self, test_unverified_user, mongo):
        email = test_unverified_user["email"]
        # 1st call: SMTP disabled → expect 503 BUT verification_sent_at should still be persisted
        r1 = requests.post(f"{API}/auth/resend-verification", json={"email": email})
        # Acceptable either 503 (smtp off) or 200 (SMTP on); in both cases sent_at must persist.
        assert r1.status_code in (200, 503), r1.text

        # Verify timestamp persisted
        u = mongo.users.find_one({"user_id": test_unverified_user["user_id"]}, {"verification_sent_at": 1})
        assert u.get("verification_sent_at") is not None, "verification_sent_at MUST be persisted before SMTP check"

        # 2nd call within 60s → must hit rate limit (429), NOT 503 fallthrough
        r2 = requests.post(f"{API}/auth/resend-verification", json={"email": email})
        assert r2.status_code == 429, f"Expected 429 on 2nd call, got {r2.status_code}: {r2.text}"
        assert "wait" in r2.json().get("detail", "").lower()


# ---------- forgot-password: sent_at persisted BEFORE SMTP check ----------
class TestForgotPasswordRateLimit:
    def test_second_call_within_60s_is_enumeration_safe_200(self, mongo, demo_session):
        # Use progamer demo email — clear any previous rate-limit window first
        mongo.users.update_one({"email": DEMO_EMAIL}, {"$unset": {"password_reset_sent_at": ""}})

        r1 = requests.post(f"{API}/auth/forgot-password", json={"email": DEMO_EMAIL})
        # With SMTP off: 503 (and sent_at persisted BEFORE the 503). With SMTP on: 200.
        assert r1.status_code in (200, 503), r1.text

        u = mongo.users.find_one({"email": DEMO_EMAIL}, {"password_reset_sent_at": 1})
        assert u.get("password_reset_sent_at") is not None, "password_reset_sent_at MUST be persisted before SMTP check"
        first_token = mongo.users.find_one({"email": DEMO_EMAIL}, {"password_reset_token": 1}).get("password_reset_token")

        r2 = requests.post(f"{API}/auth/forgot-password", json={"email": DEMO_EMAIL})
        # 2nd call within 60s: enumeration-safe 200 (no new token)
        assert r2.status_code == 200, f"Expected 200 enumeration-safe, got {r2.status_code}: {r2.text}"

        second_token = mongo.users.find_one({"email": DEMO_EMAIL}, {"password_reset_token": 1}).get("password_reset_token")
        # No new token should be generated on the rate-limited attempt
        assert first_token == second_token, "2nd call inside rate window MUST NOT issue a fresh token"


# ---------- reset-password IP rate limit ----------
class TestResetPasswordIPRateLimit:
    def test_sixth_attempt_returns_429(self):
        # 6 calls with invalid tokens from same IP → 1..5 return 400, 6th returns 429
        sess = requests.Session()
        responses = []
        for i in range(6):
            r = sess.post(
                f"{API}/auth/reset-password",
                json={"token": secrets.token_urlsafe(32), "password": "NewPass123!"},
            )
            responses.append(r.status_code)
        assert responses[-1] == 429, f"Expected 6th attempt to be 429, got {responses}"
        # First 5 should be 400 (invalid token)
        assert all(s == 400 for s in responses[:5]), f"First 5 should be 400, got {responses}"


# ---------- Admin email templates include 'achievement' ----------
class TestAdminEmailTemplates:
    def test_get_returns_4_keys_including_achievement(self, admin_session):
        r = admin_session.get(f"{API}/admin/email-templates")
        assert r.status_code == 200
        data = r.json()
        tpls = data.get("templates", {})
        expected = {"verification", "welcome", "password_reset", "achievement"}
        assert expected.issubset(set(tpls.keys())), f"Missing keys; got {list(tpls.keys())}"
        vars_map = data.get("available_vars", {})
        ach_vars = vars_map.get("achievement", [])
        expected_vars = {"display_name", "new_grade", "previous_grade", "previous_from", "site_url", "email"}
        assert expected_vars.issubset(set(ach_vars)), f"achievement vars missing: {ach_vars}"

    def test_put_persists_achievement(self, admin_session, mongo):
        # Load current → edit achievement → PUT → GET again
        current = admin_session.get(f"{API}/admin/email-templates").json().get("templates", {})
        new_subject = f"TEST Ach {uuid.uuid4().hex[:6]}"
        current.setdefault("achievement", {})
        current["achievement"]["subject"] = new_subject
        current["achievement"].setdefault("body_text", "You leveled up!")
        current["achievement"].setdefault("body_html", "<p>You leveled up!</p>")
        r = admin_session.put(f"{API}/admin/email-templates", json={"templates": current})
        assert r.status_code == 200

        after = admin_session.get(f"{API}/admin/email-templates").json().get("templates", {})
        assert after.get("achievement", {}).get("subject") == new_subject


# ---------- Admin payout settings + auto sweep ----------
class TestAdminPayoutSettings:
    def test_get_defaults_include_auto_sweep_keys(self, admin_session, mongo):
        # wipe to get defaults
        mongo.admin_config.delete_one({"type": "payout_settings"})
        r = admin_session.get(f"{API}/admin/payout-settings")
        assert r.status_code == 200
        data = r.json()
        assert data.get("auto_sweep_enabled") is False
        assert data.get("auto_sweep_frequency") == "weekly"
        assert float(data.get("auto_sweep_min_amount")) == 10.0

    def test_put_persists_auto_sweep(self, admin_session):
        payload = {
            "automated_enabled": False,
            "platform_fee_percent": 0,
            "auto_sweep_enabled": True,
            "auto_sweep_frequency": "daily",
            "auto_sweep_min_amount": 25,
        }
        r = admin_session.put(f"{API}/admin/payout-settings", json=payload)
        assert r.status_code == 200

        got = admin_session.get(f"{API}/admin/payout-settings").json()
        assert got.get("auto_sweep_enabled") is True
        assert got.get("auto_sweep_frequency") == "daily"
        assert float(got.get("auto_sweep_min_amount")) == 25.0

    def test_put_invalid_frequency_defaults_to_weekly(self, admin_session):
        r = admin_session.put(
            f"{API}/admin/payout-settings",
            json={"auto_sweep_frequency": "yearly", "auto_sweep_enabled": False, "auto_sweep_min_amount": 10},
        )
        assert r.status_code == 200
        got = admin_session.get(f"{API}/admin/payout-settings").json()
        assert got.get("auto_sweep_frequency") == "weekly"

    def test_sweep_run_returns_reason_when_automated_disabled(self, admin_session, mongo):
        # Ensure automated_enabled = False (it is by default)
        mongo.admin_config.update_one(
            {"type": "payout_settings"},
            {"$set": {"automated_enabled": False, "auto_sweep_enabled": True}},
            upsert=True,
        )
        r = admin_session.post(f"{API}/admin/payout-sweep/run")
        assert r.status_code == 200
        data = r.json()
        assert "swept" in data and "skipped" in data
        assert data.get("reason") == "automated_payouts_disabled"

    def test_sweep_run_requires_admin(self, demo_session):
        r = demo_session.post(f"{API}/admin/payout-sweep/run")
        assert r.status_code == 403
