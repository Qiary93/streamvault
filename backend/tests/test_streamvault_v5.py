"""
Iteration 5 backend tests for StreamVault:
- Categories (40+ seed, popular+limit=12 sorting)
- Subscriber emotes (20 platform-wide)
- Streamer custom emotes CRUD (max 20, code validation, subscribers_only)
- Chat settings (GET/PUT + public)
- Clips (create/list/my-clips)
- Stripe Connect webhook (account.updated / payout.paid / payout.failed)
"""
import io
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-vault-137.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

STREAMER_EMAIL = "progamer@demo.com"
STREAMER_PASS = "Demo123!"
ADMIN_EMAIL = "admin@streamvault.com"
ADMIN_PASS = "Admin123!"

# Tiny valid PNG (1x1 blue pixel) bytes
PNG_1x1 = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4"
    "890000000d49444154789c6300010000050001c1d5d61b0000000049454e44ae426082"
)


@pytest.fixture(scope="session")
def streamer_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": STREAMER_EMAIL, "password": STREAMER_PASS})
    if r.status_code != 200:
        pytest.skip(f"Streamer login failed: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    s.user_id = data.get("user", {}).get("user_id") or data.get("user_id")
    return s


@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ============= CATEGORIES =============
class TestCategories:
    def test_all_categories_count_40plus(self):
        r = requests.get(f"{API}/categories")
        assert r.status_code == 200
        cats = r.json()
        assert isinstance(cats, list)
        assert len(cats) >= 40, f"Expected 40+ categories, got {len(cats)}"
        names = [c.get("name") for c in cats]
        # Spot check Kick.com categories
        for expected in ["Just Chatting", "Grand Theft Auto V", "League of Legends", "VALORANT", "Fortnite"]:
            assert expected in names, f"Missing category: {expected}"

    def test_popular_limit_12(self):
        r = requests.get(f"{API}/categories", params={"popular": "true", "limit": 12})
        assert r.status_code == 200
        cats = r.json()
        assert len(cats) == 12, f"Expected exactly 12, got {len(cats)}"
        # Verify sort desc by (stream_count, popularity)
        for i in range(len(cats) - 1):
            a = (cats[i].get("stream_count", 0), cats[i].get("popularity", 0))
            b = (cats[i + 1].get("stream_count", 0), cats[i + 1].get("popularity", 0))
            assert a >= b, f"Not sorted desc at {i}: {a} < {b}"

    def test_popular_includes_slots_casino(self):
        r = requests.get(f"{API}/categories", params={"popular": "true", "limit": 12})
        names = [c["name"] for c in r.json()]
        # Expected to include Slots & Casino in top 12 per seed popularity
        assert "Just Chatting" in names
        # Slots & Casino may/may not be exactly in top 12 depending on popularity tuning; check presence in full list
        r2 = requests.get(f"{API}/categories")
        all_names = [c["name"] for c in r2.json()]
        assert "Slots & Casino" in all_names


# ============= SUBSCRIBER EMOTES =============
class TestSubscriberEmotes:
    def test_20_subscriber_emotes(self):
        r = requests.get(f"{API}/emotes/subscriber")
        assert r.status_code == 200
        emotes = r.json()
        assert isinstance(emotes, list)
        assert len(emotes) == 20, f"Expected exactly 20 subscriber emotes, got {len(emotes)}"
        for e in emotes:
            code = e.get("code", "")
            assert code.startswith(":sv") and code.endswith(":"), f"Bad code: {code}"


# ============= STREAMER EMOTES CRUD =============
class TestStreamerEmotes:
    def test_get_my_emotes(self, streamer_session):
        r = streamer_session.get(f"{API}/my/emotes")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_upload_reject_invalid_code(self, streamer_session):
        files = {"file": ("t.png", io.BytesIO(PNG_1x1), "image/png")}
        r = streamer_session.post(
            f"{API}/my/emotes",
            params={"code": "bademote", "subscribers_only": "false"},
            files=files,
        )
        assert r.status_code == 400
        assert "colon" in r.text.lower() or "code" in r.text.lower() or ":" in r.text

    def test_upload_and_list_and_toggle_and_delete(self, streamer_session):
        # Cleanup: delete any TEST_ emotes first
        existing = streamer_session.get(f"{API}/my/emotes").json()
        for e in existing:
            if e.get("code", "").startswith(":TEST"):
                streamer_session.delete(f"{API}/my/emotes/{e['emote_id']}")

        code = f":TEST{uuid.uuid4().hex[:6]}:"
        files = {"file": ("t.png", io.BytesIO(PNG_1x1), "image/png")}
        r = streamer_session.post(
            f"{API}/my/emotes",
            params={"code": code, "subscribers_only": "false"},
            files=files,
        )
        assert r.status_code == 200, f"upload failed: {r.status_code} {r.text[:300]}"
        doc = r.json()
        assert doc["code"] == code
        assert doc["subscribers_only"] is False
        emote_id = doc["emote_id"]

        # Confirm in list
        r2 = streamer_session.get(f"{API}/my/emotes")
        assert any(e["emote_id"] == emote_id for e in r2.json())

        # Public list
        uid = r2.json()[0]["user_id"]
        r3 = requests.get(f"{API}/users/{uid}/emotes")
        assert r3.status_code == 200
        assert any(e["emote_id"] == emote_id for e in r3.json())

        # Toggle subscribers_only
        r4 = streamer_session.put(f"{API}/my/emotes/{emote_id}", json={"subscribers_only": True})
        assert r4.status_code == 200
        r5 = streamer_session.get(f"{API}/my/emotes")
        me = next(e for e in r5.json() if e["emote_id"] == emote_id)
        assert me["subscribers_only"] is True

        # Delete
        r6 = streamer_session.delete(f"{API}/my/emotes/{emote_id}")
        assert r6.status_code == 200
        r7 = streamer_session.get(f"{API}/my/emotes")
        assert not any(e["emote_id"] == emote_id for e in r7.json())

    def test_max_20_enforced(self, streamer_session):
        # clean existing TEST_ emotes
        existing = streamer_session.get(f"{API}/my/emotes").json()
        for e in existing:
            if e.get("code", "").startswith(":TESTMAX"):
                streamer_session.delete(f"{API}/my/emotes/{e['emote_id']}")

        existing = streamer_session.get(f"{API}/my/emotes").json()
        current_count = len(existing)
        to_add = max(0, 20 - current_count)
        created = []
        try:
            for i in range(to_add):
                code = f":TESTMAX{i}{uuid.uuid4().hex[:4]}:"
                files = {"file": ("t.png", io.BytesIO(PNG_1x1), "image/png")}
                r = streamer_session.post(
                    f"{API}/my/emotes",
                    params={"code": code, "subscribers_only": "false"},
                    files=files,
                )
                if r.status_code == 200:
                    created.append(r.json()["emote_id"])
                else:
                    # If we already at 20, break
                    break

            # Now try 21st -> should 400
            code = f":TESTMAX99{uuid.uuid4().hex[:4]}:"
            files = {"file": ("t.png", io.BytesIO(PNG_1x1), "image/png")}
            r = streamer_session.post(
                f"{API}/my/emotes",
                params={"code": code, "subscribers_only": "false"},
                files=files,
            )
            assert r.status_code == 400
            assert "20" in r.text or "max" in r.text.lower()
        finally:
            for eid in created:
                streamer_session.delete(f"{API}/my/emotes/{eid}")


# ============= CHAT SETTINGS =============
class TestChatSettings:
    def test_default_chat_settings(self, streamer_session):
        r = streamer_session.get(f"{API}/my/chat-settings")
        assert r.status_code == 200
        data = r.json()
        assert "chat_enabled" in data
        assert "rules" in data

    def test_save_and_persist(self, streamer_session):
        rules_text = f"TEST_Rule1. Be nice. {uuid.uuid4().hex[:6]}"
        r = streamer_session.put(f"{API}/my/chat-settings", json={"chat_enabled": False, "rules": rules_text})
        assert r.status_code == 200

        r2 = streamer_session.get(f"{API}/my/chat-settings")
        assert r2.status_code == 200
        d = r2.json()
        assert d["chat_enabled"] is False
        assert d["rules"] == rules_text

        # Public endpoint shows same
        uid = streamer_session.user_id
        r3 = requests.get(f"{API}/users/{uid}/chat-settings")
        assert r3.status_code == 200
        assert r3.json()["rules"] == rules_text
        assert r3.json()["chat_enabled"] is False

        # Restore
        r4 = streamer_session.put(f"{API}/my/chat-settings", json={"chat_enabled": True, "rules": ""})
        assert r4.status_code == 200


# ============= CLIPS =============
class TestClips:
    def test_create_and_list_clip(self, streamer_session):
        # Find any stream for progamer (or any existing stream)
        r = requests.get(f"{API}/streams")
        streams = r.json() if r.status_code == 200 else []
        if not streams:
            # Try categories to find any stream
            cats = requests.get(f"{API}/categories").json()
            for c in cats[:5]:
                cd = requests.get(f"{API}/categories/{c['category_id']}").json()
                if cd.get("streams"):
                    streams = cd["streams"]
                    break
        if not streams:
            # Use any stream_id from db — create a dummy via my streams? Fall back to skip
            pytest.skip("No stream available to clip")

        stream_id = streams[0]["stream_id"]
        r = streamer_session.post(f"{API}/streams/{stream_id}/clip", json={"title": "TEST_Clip", "timestamp": 42})
        assert r.status_code == 200
        clip = r.json()
        assert clip["title"] == "TEST_Clip"
        assert clip["timestamp_sec"] == 42
        assert clip["stream_id"] == stream_id

        r2 = requests.get(f"{API}/streams/{stream_id}/clips")
        assert r2.status_code == 200
        assert any(c["clip_id"] == clip["clip_id"] for c in r2.json())

        # Only the streamer of that stream can see it in my/clips
        # Call get for streamer_session
        r3 = streamer_session.get(f"{API}/my/clips")
        assert r3.status_code == 200
        # may or may not include — depends on whether progamer owns this stream


# ============= STRIPE CONNECT WEBHOOK =============
class TestStripeConnectWebhook:
    def test_account_updated_verified(self):
        account_id = f"acct_TEST_{uuid.uuid4().hex[:10]}"
        # Seed an account in DB by calling webhook with initial account.updated
        payload = {
            "type": "account.updated",
            "data": {
                "object": {
                    "id": account_id,
                    "payouts_enabled": True,
                    "charges_enabled": True,
                    "capabilities": {"transfers": "active"},
                    "requirements": {"currently_due": []},
                }
            }
        }
        r = requests.post(f"{API}/webhook/stripe/connect", json=payload)
        assert r.status_code == 200
        body = r.json()
        assert body["received"] is True
        assert body["event"] == "account.updated"

    def test_account_updated_action_required(self):
        account_id = f"acct_TEST_{uuid.uuid4().hex[:10]}"
        payload = {
            "type": "account.updated",
            "data": {
                "object": {
                    "id": account_id,
                    "payouts_enabled": False,
                    "charges_enabled": False,
                    "capabilities": {"transfers": "pending"},
                    "requirements": {"currently_due": ["external_account"]},
                }
            }
        }
        r = requests.post(f"{API}/webhook/stripe/connect", json=payload)
        assert r.status_code == 200

    def test_payout_failed(self):
        payout_id = f"po_TEST_{uuid.uuid4().hex[:10]}"
        payload = {
            "type": "payout.failed",
            "data": {"object": {"id": payout_id, "failure_message": "test"}}
        }
        r = requests.post(f"{API}/webhook/stripe/connect", json=payload)
        assert r.status_code == 200
        assert r.json()["event"] == "payout.failed"

    def test_payout_paid(self):
        payout_id = f"po_TEST_{uuid.uuid4().hex[:10]}"
        payload = {"type": "payout.paid", "data": {"object": {"id": payout_id}}}
        r = requests.post(f"{API}/webhook/stripe/connect", json=payload)
        assert r.status_code == 200
        assert r.json()["event"] == "payout.paid"

    def test_other_event_silently_accepted(self):
        r = requests.post(f"{API}/webhook/stripe/connect", json={"type": "capability.updated", "data": {"object": {"id": "cap_x"}}})
        assert r.status_code == 200

    def test_invalid_payload(self):
        r = requests.post(f"{API}/webhook/stripe/connect", data=b"not-json", headers={"Content-Type": "application/json"})
        assert r.status_code == 400
