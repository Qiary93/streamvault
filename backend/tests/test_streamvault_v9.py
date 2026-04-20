"""StreamVault iteration-9 backend regression tests.
Focus: broadcasting sync loop output, /api/recommended, admin email-templates,
forgot/reset-password, resend-verification rate limit, chat hearts, WS chat,
check-broadcast ISO datetime.
"""
import os
import time
import json
import secrets
import asyncio
import pytest
import requests
import websockets
from pymongo import MongoClient
from datetime import datetime, timezone

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-vault-137.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
WS_URL = BASE_URL.replace("https://", "wss://").replace("http://", "ws://") + "/api/ws/chat"

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")

ADMIN_EMAIL = "admin@streamvault.com"
ADMIN_PASS = "Admin123!"
DEMO_EMAIL = "progamer@demo.com"
DEMO_PASS = "Demo123!"


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


# -------- Regression: core endpoints still work --------
class TestRegression:
    def test_login_admin(self, admin_session):
        r = admin_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json().get("role") == "admin"

    def test_login_demo(self, demo_session):
        r = demo_session.get(f"{API}/auth/me")
        assert r.status_code == 200
        assert r.json().get("email") == DEMO_EMAIL

    def test_categories(self):
        r = requests.get(f"{API}/categories")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_donations_received_auth(self, demo_session):
        r = demo_session.get(f"{API}/donations/received")
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# -------- Recommended (broadcasting filter) --------
class TestRecommended:
    def test_recommended_returns_200_and_filters(self):
        r = requests.get(f"{API}/recommended")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        # Each returned stream must be is_live AND broadcasting
        for s in data:
            assert s.get("is_live") is True, s
            assert s.get("broadcasting") is True, s


# -------- Admin email templates --------
class TestEmailTemplates:
    def test_non_admin_403(self, demo_session):
        r = demo_session.get(f"{API}/admin/email-templates")
        assert r.status_code == 403

    def test_anon_401(self):
        r = requests.get(f"{API}/admin/email-templates")
        assert r.status_code in (401, 403)

    def test_get_defaults(self, admin_session):
        r = admin_session.get(f"{API}/admin/email-templates")
        assert r.status_code == 200
        body = r.json()
        assert "templates" in body and "available_vars" in body
        for key in ("verification", "welcome", "password_reset"):
            assert key in body["templates"]
            t = body["templates"][key]
            assert t.get("subject") and t.get("html") and t.get("text")
            assert key in body["available_vars"]

    def test_put_persists(self, admin_session):
        # Customize welcome template
        current = admin_session.get(f"{API}/admin/email-templates").json()["templates"]
        custom_subject = f"TEST Welcome {secrets.token_hex(4)}"
        current["welcome"]["subject"] = custom_subject
        r = admin_session.put(f"{API}/admin/email-templates", json={"templates": current})
        assert r.status_code == 200
        # Fetch back
        r2 = admin_session.get(f"{API}/admin/email-templates")
        assert r2.status_code == 200
        assert r2.json()["templates"]["welcome"]["subject"] == custom_subject


# -------- Forgot/reset password --------
class TestPasswordReset:
    def test_forgot_password_valid_email(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": DEMO_EMAIL})
        # SMTP may be disabled (503) or enabled (200). Both acceptable.
        assert r.status_code in (200, 503), r.text
        if r.status_code == 200:
            assert "reset link" in r.json().get("message", "").lower() or "sent" in r.json().get("message", "").lower()

    def test_forgot_password_empty_email(self):
        r = requests.post(f"{API}/auth/forgot-password", json={"email": ""})
        assert r.status_code in (400, 503)

    def test_reset_password_invalid_token(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": "short", "password": "NewPass123!"})
        assert r.status_code == 400

    def test_reset_password_short_password(self):
        r = requests.post(f"{API}/auth/reset-password", json={"token": "a" * 40, "password": "abc"})
        assert r.status_code == 400


# -------- Resend-verification rate limit --------
class TestResendVerification:
    def test_resend_unverified_user(self, mongo):
        email = f"test_resend_{secrets.token_hex(4)}@example.com"
        # Create unverified user directly
        from bson import ObjectId
        user_doc = {
            "user_id": f"user_{secrets.token_hex(6)}",
            "email": email,
            "username": "testresend",
            "display_name": "Test Resend",
            "password_hash": "$2b$10$abc",
            "role": "user",
            "email_verified": False,
            "created_at": datetime.now(timezone.utc),
        }
        mongo.users.insert_one(user_doc)
        try:
            # First call — either 503 (SMTP disabled) or 200
            r1 = requests.post(f"{API}/auth/resend-verification", json={"email": email})
            assert r1.status_code in (200, 500, 503), r1.text

            # Check SMTP status
            smtp_cfg = mongo.admin_config.find_one({"type": "smtp"})
            smtp_enabled = bool(smtp_cfg and smtp_cfg.get("enabled"))

            if not smtp_enabled:
                assert r1.status_code == 503
                # When disabled, rate limit does NOT get set (503 raised before). That's fine.
            else:
                # Manually set verification_sent_at = now so 2nd call triggers 429
                mongo.users.update_one({"email": email}, {"$set": {"verification_sent_at": datetime.now(timezone.utc)}})
                r2 = requests.post(f"{API}/auth/resend-verification", json={"email": email})
                assert r2.status_code == 429
        finally:
            mongo.users.delete_one({"email": email})

    def test_resend_unknown_email_enum_safe(self):
        r = requests.post(f"{API}/auth/resend-verification", json={"email": f"nobody_{secrets.token_hex(4)}@x.com"})
        assert r.status_code == 200
        assert "exists" in r.json().get("message", "").lower() or "sent" in r.json().get("message", "").lower()


# -------- Chat hearts --------
class TestChatHeart:
    def test_heart_requires_auth(self):
        r = requests.post(f"{API}/streams/stream_dummy/chat/msg_dummy/heart")
        assert r.status_code in (401, 403)

    def test_heart_404_on_missing_message(self, demo_session):
        r = demo_session.post(f"{API}/streams/stream_dummy/chat/msg_doesnotexist/heart")
        assert r.status_code == 404

    def test_heart_toggle_valid(self, demo_session, mongo):
        # Insert a chat message directly
        stream_id = "stream_426cc5efe2b1"  # seeded demo stream
        msg_id = f"msg_test_{secrets.token_hex(6)}"
        mongo.chat_messages.insert_one({
            "message_id": msg_id,
            "stream_id": stream_id,
            "user_id": "test",
            "username": "test",
            "content": "hello",
            "hearts": 0,
            "created_at": datetime.now(timezone.utc),
        })
        try:
            r1 = demo_session.post(f"{API}/streams/{stream_id}/chat/{msg_id}/heart")
            assert r1.status_code == 200, r1.text
            j1 = r1.json()
            assert j1["hearted"] is True
            assert j1["hearts"] == 1
            r2 = demo_session.post(f"{API}/streams/{stream_id}/chat/{msg_id}/heart")
            assert r2.status_code == 200
            j2 = r2.json()
            assert j2["hearted"] is False
            assert j2["hearts"] == 0
        finally:
            mongo.chat_messages.delete_one({"message_id": msg_id})
            mongo.chat_hearts.delete_many({"message_id": msg_id})


# -------- Check-broadcast --------
class TestCheckBroadcast:
    def test_check_broadcast_shape(self, mongo):
        s = mongo.streams.find_one({}, {"stream_id": 1})
        if not s:
            pytest.skip("No stream in DB")
        r = requests.get(f"{API}/streams/{s['stream_id']}/check-broadcast")
        assert r.status_code == 200
        body = r.json()
        assert "broadcasting" in body
        if body.get("broadcasting") is True:
            assert "broadcasting_started_at" in body
            # must be ISO string with UTC offset
            assert isinstance(body["broadcasting_started_at"], str)
            assert "+00:00" in body["broadcasting_started_at"] or body["broadcasting_started_at"].endswith("Z")


# -------- WebSocket chat --------
class TestWsChat:
    def test_ws_chat_echo(self, demo_session, mongo):
        async def _run():
            s = mongo.streams.find_one({}, {"stream_id": 1})
            if not s:
                return "skip"
            stream_id = s["stream_id"]
            cookies = "; ".join(f"{k}={v}" for k, v in demo_session.cookies.get_dict().items())
            headers = [("Cookie", cookies)] if cookies else []
            url = f"{WS_URL}/{stream_id}"
            async with websockets.connect(url, additional_headers=headers, open_timeout=10) as ws:
                await asyncio.sleep(0.5)
                await ws.send(json.dumps({"type": "message", "content": f"ws-test-{secrets.token_hex(3)}"}))
                echo = None
                deadline = time.time() + 5
                while time.time() < deadline:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=2)
                    except asyncio.TimeoutError:
                        break
                    try:
                        msg = json.loads(raw)
                    except Exception:
                        continue
                    if msg.get("content", "").startswith("ws-test-") and msg.get("message_id"):
                        echo = msg
                        break
                return echo

        result = asyncio.run(_run())
        if result == "skip":
            pytest.skip("No stream in DB")
        assert result is not None, "did not receive echo message"
        assert "message_id" in result
        assert "created_at" in result
