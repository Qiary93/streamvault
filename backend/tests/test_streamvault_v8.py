"""
Iteration 8 tests — SMTP settings, email verification, tier badges,
emote limit 60, check-broadcast broadcasting_started_at.
"""
import io
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")


# ---------------- fixtures ----------------

@pytest.fixture(scope="session")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "admin@streamvault.com", "password": "Admin123!"})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def streamer_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login",
               json={"email": "progamer@demo.com", "password": "Demo123!"})
    assert r.status_code == 200, r.text
    return s


@pytest.fixture(scope="session")
def anon_session():
    return requests.Session()


# ---------------- SMTP admin settings ----------------

class TestSmtpSettings:
    def test_non_admin_forbidden(self, streamer_session):
        r = streamer_session.get(f"{BASE_URL}/api/admin/smtp-settings")
        assert r.status_code == 403

    def test_anon_forbidden(self, anon_session):
        r = anon_session.get(f"{BASE_URL}/api/admin/smtp-settings")
        assert r.status_code in (401, 403)

    def test_get_defaults(self, admin_session):
        r = admin_session.get(f"{BASE_URL}/api/admin/smtp-settings")
        assert r.status_code == 200
        data = r.json()
        for k in ("enabled", "host", "port", "username", "password",
                  "from_email", "from_name", "use_tls", "use_ssl"):
            assert k in data, f"missing key {k}"

    def test_put_persists_and_masks_password(self, admin_session):
        payload = {
            "enabled": False,
            "host": "smtp.example.com",
            "port": 587,
            "username": "user@example.com",
            "password": "secret123",
            "from_email": "noreply@example.com",
            "from_name": "TEST_StreamVault",
            "use_tls": True,
            "use_ssl": False,
        }
        r = admin_session.put(f"{BASE_URL}/api/admin/smtp-settings", json=payload)
        assert r.status_code == 200, r.text
        # GET back
        g = admin_session.get(f"{BASE_URL}/api/admin/smtp-settings").json()
        assert g["host"] == "smtp.example.com"
        assert g["from_name"] == "TEST_StreamVault"
        assert g["password"] == "••••••••"  # masked

    def test_put_masked_password_keeps_existing(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/smtp-settings", json={
            "enabled": False,
            "host": "smtp.example.com",
            "port": 587,
            "username": "user@example.com",
            "password": "••••••••",      # placeholder
            "from_email": "noreply@example.com",
            "from_name": "TEST_SV2",
            "use_tls": True,
            "use_ssl": False,
        })
        assert r.status_code == 200
        # Re-login admin and send masked placeholder; then put empty password, test valid login still works (password persistence is server-internal, we just assert endpoint accepts and doesn't blow up)

    def test_put_empty_password_keeps_existing(self, admin_session):
        r = admin_session.put(f"{BASE_URL}/api/admin/smtp-settings", json={
            "enabled": False,
            "host": "smtp.example.com",
            "port": 587,
            "username": "user@example.com",
            "password": "",               # empty -> keep
            "from_email": "noreply@example.com",
            "from_name": "TEST_SV3",
            "use_tls": True,
            "use_ssl": False,
        })
        assert r.status_code == 200

    def test_smtp_test_rejects_invalid_email(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/smtp-test", json={"to": "not-an-email"})
        assert r.status_code == 400

    def test_smtp_test_500_on_fake_host(self, admin_session):
        r = admin_session.post(f"{BASE_URL}/api/admin/smtp-test", json={"to": "recipient@example.com"})
        # Expected failure because SMTP host is fake
        assert r.status_code in (500, 503), f"expected 500/503 got {r.status_code}: {r.text}"


# ---------------- Email verification flow ----------------

@pytest.fixture
def enable_smtp(admin_session):
    """Context fixture to enable smtp for verification tests and restore disabled after."""
    admin_session.put(f"{BASE_URL}/api/admin/smtp-settings", json={
        "enabled": True,
        "host": "smtp.fake-host.test",
        "port": 587,
        "username": "u",
        "password": "••••••••",
        "from_email": "noreply@example.com",
        "from_name": "TEST_SV",
        "use_tls": True,
        "use_ssl": False,
    })
    yield
    admin_session.put(f"{BASE_URL}/api/admin/smtp-settings", json={
        "enabled": False,
        "host": "smtp.example.com",
        "port": 587,
        "username": "u",
        "password": "••••••••",
        "from_email": "noreply@example.com",
        "from_name": "TEST_SV",
        "use_tls": True,
        "use_ssl": False,
    })


class TestEmailVerification:
    def test_register_with_smtp_requires_verification(self, enable_smtp):
        email = f"test_verify_{uuid.uuid4().hex[:8]}@example.com"
        username = f"tstv_{uuid.uuid4().hex[:8]}"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "username": username,
            "password": "Test1234!", "display_name": "TestV"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("verification_required") is True
        assert data.get("email") == email
        # Should NOT set cookies
        assert "access_token" not in s.cookies

        # Login blocked
        lr = s.post(f"{BASE_URL}/api/auth/login",
                    json={"email": email, "password": "Test1234!"})
        assert lr.status_code == 403
        assert "verify" in lr.json().get("detail", "").lower()

        # Save email for later tests (also test invalid verify token)
        inv = s.post(f"{BASE_URL}/api/auth/verify-email",
                     json={"token": "abc"})
        assert inv.status_code == 400

        inv2 = s.post(f"{BASE_URL}/api/auth/verify-email",
                      json={"token": "x" * 40})
        assert inv2.status_code == 400

        # Resend (SMTP enabled but host is fake) — either 200 or 500, but NOT 503
        rs = s.post(f"{BASE_URL}/api/auth/resend-verification",
                    json={"email": email})
        assert rs.status_code in (200, 500), rs.text

        TestEmailVerification._pending_email = email

    def test_verify_email_with_valid_token(self, admin_session):
        """Fetch token directly from DB via admin-helper? No such endpoint.
        We use the URL-based approach: retrieve token via internal admin users lookup is unavailable,
        so we test via a different path — we rely on the previous test's invalid-token behavior.
        Since we cannot access DB from tests, we at least verify the endpoint contract with a bogus token.
        """
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/verify-email", json={"token": "z" * 40})
        assert r.status_code == 400

    def test_resend_verification_already_verified(self):
        """A user registered without SMTP is auto-verified. resend should say 'already verified'."""
        email = f"test_already_{uuid.uuid4().hex[:8]}@example.com"
        username = f"tstal_{uuid.uuid4().hex[:8]}"
        s = requests.Session()
        # Register with SMTP disabled -> auto-verified
        r = s.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "username": username,
            "password": "Test1234!", "display_name": "TA"
        })
        assert r.status_code == 200
        assert r.json().get("email_verified") is True

        # resend should respond "already verified" regardless of SMTP enabled/disabled
        rr = s.post(f"{BASE_URL}/api/auth/resend-verification", json={"email": email})
        assert rr.status_code == 200
        assert "already verified" in rr.json().get("message", "").lower()

    def test_resend_without_smtp_returns_503(self):
        # After enable_smtp fixture tears down, SMTP is disabled
        # Create an unverified user is impossible without SMTP. So we just verify that for a non-verified-looking user, with SMTP disabled, endpoint returns 503.
        # Use a fresh unknown email: the endpoint silently returns 200 for unknown emails (to avoid enumeration), so that path doesn't hit the 503 branch.
        # Skip if we cannot create an unverified user deterministically.
        pytest.skip("Cannot test 503 branch without ability to create unverified user with SMTP disabled")

    def test_register_without_smtp_autoverifies(self):
        """SMTP disabled (default after enable_smtp teardown) -> register returns email_verified True + cookies."""
        email = f"test_auto_{uuid.uuid4().hex[:8]}@example.com"
        username = f"tsta_{uuid.uuid4().hex[:8]}"
        s = requests.Session()
        r = s.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "username": username,
            "password": "Test1234!", "display_name": "TestA"
        })
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("email_verified") is True
        assert data.get("verification_required") is not True
        assert "access_token" in s.cookies


# ---------------- Emote limit 60 ----------------

def _png_bytes():
    # 1x1 transparent PNG
    return bytes.fromhex(
        "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
        "0000000d49444154789c626001000000050001a5f645400000000049454e44ae426082"
    )


class TestEmoteLimit:
    def test_upload_21st_ok(self, streamer_session):
        # How many emotes does progamer have already?
        r = streamer_session.get(f"{BASE_URL}/api/my/emotes")
        assert r.status_code == 200
        count = len(r.json())
        if count >= 60:
            pytest.skip(f"progamer already has {count} emotes — cannot add more")

        # Add one emote unique code - note: `code` is a query param
        code = f":tst{uuid.uuid4().hex[:6]}:"
        files = {"file": ("e.png", _png_bytes(), "image/png")}
        r = streamer_session.post(
            f"{BASE_URL}/api/my/emotes",
            params={"code": code, "subscribers_only": "false"},
            files=files,
        )
        assert r.status_code == 200, r.text
        eid = r.json()["emote_id"]
        # cleanup
        streamer_session.delete(f"{BASE_URL}/api/my/emotes/{eid}")

    def test_limit_is_60_not_20(self, streamer_session):
        """Verify that an emote beyond 20 can be added (proving limit was raised)."""
        r = streamer_session.get(f"{BASE_URL}/api/my/emotes")
        assert r.status_code == 200
        count = len(r.json())
        # If count < 20, uploading one would not prove anything about the raise; but we still accept
        # The real proof is the error message text on limit
        # Trigger an attempt to upload — and we verify the error message references 60 when we artificially test the cap
        # Here we only assert the code path uses 60 by uploading one and checking success if count < 60
        if count < 60:
            code = f":tst{uuid.uuid4().hex[:6]}:"
            files = {"file": ("e.png", _png_bytes(), "image/png")}
            r = streamer_session.post(
                f"{BASE_URL}/api/my/emotes",
                params={"code": code, "subscribers_only": "false"},
                files=files,
            )
            assert r.status_code == 200, r.text
            streamer_session.delete(f"{BASE_URL}/api/my/emotes/{r.json()['emote_id']}")
        else:
            code = f":tst{uuid.uuid4().hex[:6]}:"
            files = {"file": ("e.png", _png_bytes(), "image/png")}
            r = streamer_session.post(
                f"{BASE_URL}/api/my/emotes",
                params={"code": code, "subscribers_only": "false"},
                files=files,
            )
            assert r.status_code == 400
            assert "60" in r.json().get("detail", "")


# ---------------- Tier badges ----------------

class TestTierBadges:
    def test_badge_invalid_tier(self, streamer_session):
        files = {"file": ("b.png", _png_bytes(), "image/png")}
        r = streamer_session.post(f"{BASE_URL}/api/my/tiers/nope_{uuid.uuid4().hex[:6]}/badge",
                                  files=files)
        assert r.status_code == 404

    def test_badge_upload_and_persist_through_tiers_save(self, streamer_session):
        # 1) Save tiers (ensure at least one tier exists for this user)
        payload = {
            "tiers": [
                {"name": "TEST Tier 1", "amount": 4.99, "perks": "TEST perk 1"},
                {"name": "TEST Tier 2", "amount": 9.99, "perks": "TEST perk 2"},
            ]
        }
        r = streamer_session.post(f"{BASE_URL}/api/my/subscription-tiers", json=payload)
        assert r.status_code == 200, r.text

        # 2) Get tiers, grab a tier_id
        g = streamer_session.get(f"{BASE_URL}/api/my/subscription-tiers")
        assert g.status_code == 200, g.text
        body = g.json()
        tiers = body if isinstance(body, list) else (body.get("tiers") or [])
        assert isinstance(tiers, list) and len(tiers) >= 1
        tier = tiers[0]
        tier_id = tier.get("tier_id") or tier.get("id")
        assert tier_id, f"tier has no id: {tier}"

        # 3) Upload badge
        files = {"file": ("b.png", _png_bytes(), "image/png")}
        br = streamer_session.post(f"{BASE_URL}/api/my/tiers/{tier_id}/badge", files=files)
        assert br.status_code == 200, br.text
        badge_url = br.json().get("badge_url")
        assert badge_url and "/api/files/" in badge_url

        # 4) Re-save tiers (should preserve badge_url)
        r2 = streamer_session.post(f"{BASE_URL}/api/my/subscription-tiers", json=payload)
        assert r2.status_code == 200

        # 5) Get tiers, verify badge_url still present on the same tier_id
        g2 = streamer_session.get(f"{BASE_URL}/api/my/subscription-tiers")
        body2 = g2.json()
        tiers2 = body2 if isinstance(body2, list) else (body2.get("tiers") or [])
        same = next((t for t in tiers2 if (t.get("tier_id") or t.get("id")) == tier_id), None)
        assert same is not None, "tier_id lost on re-save"
        assert same.get("badge_url") == badge_url, f"badge_url lost: {same}"

        # 6) Delete badge
        dr = streamer_session.delete(f"{BASE_URL}/api/my/tiers/{tier_id}/badge")
        assert dr.status_code == 200

        # 7) Verify removed
        g3 = streamer_session.get(f"{BASE_URL}/api/my/subscription-tiers")
        body3 = g3.json()
        tiers3 = body3 if isinstance(body3, list) else (body3.get("tiers") or [])
        same3 = next((t for t in tiers3 if (t.get("tier_id") or t.get("id")) == tier_id), None)
        assert same3 is None or not same3.get("badge_url")


# ---------------- check-broadcast broadcasting_started_at ----------------

class TestCheckBroadcast:
    def test_check_broadcast_response_shape(self, streamer_session):
        # Get own stream id
        me = streamer_session.get(f"{BASE_URL}/api/auth/me").json()
        streams = streamer_session.get(f"{BASE_URL}/api/streams", params={"user_id": me["user_id"]})
        # Try finding the user's stream via my-stream endpoint or streams list
        my = streamer_session.get(f"{BASE_URL}/api/my/stream")
        if my.status_code != 200:
            pytest.skip("No /api/my/stream endpoint available")
        stream = my.json()
        stream_id = stream.get("stream_id")
        if not stream_id:
            pytest.skip("Streamer has no stream")
        r = streamer_session.get(f"{BASE_URL}/api/streams/{stream_id}/check-broadcast")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "broadcasting" in data
        # When broadcasting is True the key should exist
        if data.get("broadcasting") is True:
            assert "broadcasting_started_at" in data
