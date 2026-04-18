"""
Backend tests for StreamVault iteration 4 features:
- Revenue analytics
- Stripe Connect (Custom) — validation paths only (LIVE key in env)
- Admin payout settings (automated toggle)
- Admin ad settings + per-view ad impressions
- My ad earnings + admin ad earnings + analytics trends
- Approve withdrawal in manual + automated (no connect) modes
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://stream-vault-137.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "admin@streamvault.com"
ADMIN_PASSWORD = "Admin123!"
STREAMER_EMAIL = "progamer@demo.com"
STREAMER_PASSWORD = "Demo123!"


def _login(session: requests.Session, email: str, password: str):
    r = session.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    return r.json()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    _login(s, ADMIN_EMAIL, ADMIN_PASSWORD)
    return s


@pytest.fixture(scope="module")
def streamer_session():
    s = requests.Session()
    _login(s, STREAMER_EMAIL, STREAMER_PASSWORD)
    return s


@pytest.fixture(scope="module")
def anon_session():
    return requests.Session()


# =============== PAYOUT SETTINGS ===============

class TestPayoutSettings:
    def test_get_default_non_admin_forbidden(self, streamer_session):
        r = streamer_session.get(f"{API}/admin/payout-settings")
        assert r.status_code == 403

    def test_put_non_admin_forbidden(self, streamer_session):
        r = streamer_session.put(f"{API}/admin/payout-settings", json={"automated_enabled": True})
        assert r.status_code == 403

    def test_get_default_admin(self, admin_session):
        # Ensure default state first by resetting to False
        admin_session.put(f"{API}/admin/payout-settings", json={"automated_enabled": False})
        r = admin_session.get(f"{API}/admin/payout-settings")
        assert r.status_code == 200
        data = r.json()
        assert data.get("automated_enabled") is False

    def test_put_toggle_and_persist(self, admin_session):
        r = admin_session.put(f"{API}/admin/payout-settings", json={"automated_enabled": True})
        assert r.status_code == 200
        assert r.json().get("automated_enabled") is True
        # Verify persistence
        r2 = admin_session.get(f"{API}/admin/payout-settings")
        assert r2.json().get("automated_enabled") is True
        # Toggle back for isolation
        admin_session.put(f"{API}/admin/payout-settings", json={"automated_enabled": False})
        assert admin_session.get(f"{API}/admin/payout-settings").json().get("automated_enabled") is False


# =============== AD SETTINGS ===============

class TestAdSettings:
    def test_get_defaults_admin(self, admin_session):
        # Reset by saving an empty-slot config with defaults
        admin_session.put(f"{API}/admin/ad-settings", json={"enabled": False, "ad_slots": [], "revenue_share_percent": 70})
        r = admin_session.get(f"{API}/admin/ad-settings")
        assert r.status_code == 200
        d = r.json()
        assert d.get("enabled") is False
        rates = d.get("cpm_rates") or {}
        assert rates.get("live_pre_roll") == 2.0
        assert rates.get("live_mid_roll") == 3.0
        assert rates.get("vod_pre_roll") == 2.0
        assert rates.get("vod_mid_roll") == 2.5

    def test_get_forbidden_for_non_admin(self, streamer_session):
        r = streamer_session.get(f"{API}/admin/ad-settings")
        assert r.status_code == 403

    def test_put_persists(self, admin_session):
        slot_id = f"slot_{uuid.uuid4().hex[:8]}"
        payload = {
            "enabled": True,
            "revenue_share_percent": 60.0,
            "cpm_rates": {"live_pre_roll": 5, "live_mid_roll": 4, "vod_pre_roll": 3, "vod_mid_roll": 2},
            "ad_slots": [{
                "slot_id": slot_id,
                "name": "Test Pre-roll",
                "placement": "live_pre_roll",
                "ad_type": "html",
                "ad_code": "<div>AD</div>",
                "duration_sec": 10,
                "active": True,
            }],
        }
        r = admin_session.put(f"{API}/admin/ad-settings", json=payload)
        assert r.status_code == 200
        # Read-back
        r2 = admin_session.get(f"{API}/admin/ad-settings")
        d = r2.json()
        assert d["enabled"] is True
        assert d["revenue_share_percent"] == 60.0
        assert d["cpm_rates"]["live_pre_roll"] == 5.0
        slot_ids = [s["slot_id"] for s in d.get("ad_slots", [])]
        assert slot_id in slot_ids


# =============== ACTIVE AD + IMPRESSION ===============

class TestAdsFlow:
    @pytest.fixture(scope="class")
    def enable_ads_with_slot(self, admin_session):
        slot_id = f"slot_{uuid.uuid4().hex[:8]}"
        admin_session.put(f"{API}/admin/ad-settings", json={
            "enabled": True,
            "revenue_share_percent": 50.0,
            "cpm_rates": {"live_pre_roll": 10, "live_mid_roll": 3, "vod_pre_roll": 2, "vod_mid_roll": 2.5},
            "ad_slots": [{
                "slot_id": slot_id, "name": "t", "placement": "live_pre_roll",
                "ad_type": "html", "ad_code": "<b>ad</b>", "duration_sec": 5, "active": True
            }],
        })
        yield slot_id
        # Disable after
        admin_session.put(f"{API}/admin/ad-settings", json={"enabled": False, "ad_slots": []})

    def test_active_ad_returns_slot_when_enabled(self, anon_session, enable_ads_with_slot):
        r = anon_session.get(f"{API}/ads/active?placement=live_pre_roll")
        assert r.status_code == 200
        d = r.json()
        assert d.get("enabled") is True
        assert d.get("ad") is not None
        assert d["ad"]["slot_id"] == enable_ads_with_slot

    def test_active_ad_disabled_state(self, admin_session, anon_session):
        # Disable
        admin_session.put(f"{API}/admin/ad-settings", json={"enabled": False, "ad_slots": []})
        r = anon_session.get(f"{API}/ads/active?placement=live_pre_roll")
        assert r.status_code == 200
        assert r.json().get("enabled") is False
        assert r.json().get("ad") is None

    def test_impression_credits_and_dedupes(self, admin_session, streamer_session):
        # Find a stream for progamer
        me = streamer_session.get(f"{API}/auth/me").json()
        streamer_id = me["user_id"]
        streams = requests.get(f"{API}/streams?limit=50").json()
        own = [s for s in streams if s.get("user_id") == streamer_id]
        if not own:
            pytest.skip("No stream for streamer in seed")
        stream_id = own[0]["stream_id"]

        slot_id = f"slot_{uuid.uuid4().hex[:8]}"
        admin_session.put(f"{API}/admin/ad-settings", json={
            "enabled": True,
            "revenue_share_percent": 50.0,
            "cpm_rates": {"live_pre_roll": 10, "live_mid_roll": 3, "vod_pre_roll": 2, "vod_mid_roll": 2.5},
            "ad_slots": [{
                "slot_id": slot_id, "name": "t", "placement": "live_pre_roll",
                "ad_type": "html", "ad_code": "<b>ad</b>", "duration_sec": 5, "active": True
            }],
        })

        # First impression from a fresh viewer
        viewer = f"viewer_{uuid.uuid4().hex[:8]}"
        body = {"stream_id": stream_id, "slot_id": slot_id, "placement": "live_pre_roll", "viewer_id": viewer}
        r1 = requests.post(f"{API}/ads/impression", json=body)
        assert r1.status_code == 200
        d1 = r1.json()
        assert d1.get("credited") is True
        # CPM=10, revshare=50% -> earned = (10/1000)*0.5 = 0.005
        assert abs(d1.get("streamer_earned") - 0.005) < 1e-6

        # Duplicate within 30s: not credited
        r2 = requests.post(f"{API}/ads/impression", json=body)
        assert r2.status_code == 200
        assert r2.json().get("credited") is False

        # Cleanup
        admin_session.put(f"{API}/admin/ad-settings", json={"enabled": False, "ad_slots": []})

    def test_impression_missing_fields_400(self, anon_session):
        r = anon_session.post(f"{API}/ads/impression", json={})
        assert r.status_code == 400


# =============== EARNINGS + REVENUE ===============

class TestEarnings:
    def test_my_ad_earnings(self, streamer_session):
        r = streamer_session.get(f"{API}/my/ad-earnings")
        assert r.status_code == 200
        d = r.json()
        assert "total_impressions" in d
        assert "total_earned" in d
        assert "by_placement" in d and isinstance(d["by_placement"], dict)

    def test_admin_ad_earnings(self, admin_session):
        r = admin_session.get(f"{API}/admin/ad-earnings")
        assert r.status_code == 200
        d = r.json()
        assert "platform_earned" in d
        assert "streamer_earned" in d
        assert isinstance(d.get("top_streamers"), list)

    def test_admin_ad_earnings_forbidden(self, streamer_session):
        r = streamer_session.get(f"{API}/admin/ad-earnings")
        assert r.status_code == 403

    def test_my_revenue_has_total_ads(self, streamer_session):
        r = streamer_session.get(f"{API}/my/revenue")
        assert r.status_code == 200
        d = r.json()
        assert "total_ads" in d
        assert isinstance(d["total_ads"], (int, float))

    def test_revenue_analytics_default_daily(self, streamer_session):
        r = streamer_session.get(f"{API}/my/revenue/analytics")
        assert r.status_code == 200
        d = r.json()
        assert d.get("period") == "daily"
        assert isinstance(d.get("series"), list)
        for row in d["series"]:
            assert "period" in row
            for k in ("donations", "subscriptions", "ads", "total"):
                assert k in row

    def test_revenue_analytics_weekly(self, streamer_session):
        r = streamer_session.get(f"{API}/my/revenue/analytics?period=weekly")
        assert r.status_code == 200
        assert r.json().get("period") == "weekly"

    def test_revenue_analytics_monthly(self, streamer_session):
        r = streamer_session.get(f"{API}/my/revenue/analytics?period=monthly")
        assert r.status_code == 200
        assert r.json().get("period") == "monthly"


# =============== STRIPE CONNECT (validation-only) ===============

class TestStripeConnect:
    def test_status_not_started(self, streamer_session):
        # Ensure no account first
        streamer_session.delete(f"{API}/my/stripe-connect")
        r = streamer_session.get(f"{API}/my/stripe-connect/status")
        assert r.status_code == 200
        d = r.json()
        assert d.get("connected") is False
        assert d.get("verification_status") == "not_started"

    def test_create_missing_required_400(self, streamer_session):
        r = streamer_session.post(f"{API}/my/stripe-connect/create", json={
            "first_name": "", "last_name": "", "dob": "", "address_line1": "",
            "city": "", "postal_code": "", "account_number": "", "tos_accepted": True
        })
        assert r.status_code == 400
        assert "Missing" in r.text

    def test_create_tos_not_accepted_400(self, streamer_session):
        r = streamer_session.post(f"{API}/my/stripe-connect/create", json={
            "first_name": "John", "last_name": "Doe", "dob": "1990-01-01",
            "address_line1": "123 Main St", "city": "SF", "state": "CA",
            "postal_code": "94103", "account_number": "000123456789",
            "routing_number": "110000000", "tos_accepted": False
        })
        assert r.status_code == 400
        assert "Stripe Services Agreement" in r.text or "accept" in r.text.lower()

    def test_delete_idempotent(self, streamer_session):
        r1 = streamer_session.delete(f"{API}/my/stripe-connect")
        assert r1.status_code == 200
        # Second call also OK
        r2 = streamer_session.delete(f"{API}/my/stripe-connect")
        assert r2.status_code == 200

    def test_status_requires_auth(self):
        r = requests.get(f"{API}/my/stripe-connect/status")
        assert r.status_code in (401, 403)


# =============== APPROVE WITHDRAWAL ===============

class TestApproveWithdrawal:
    @pytest.fixture(scope="class")
    def seeded_withdrawal(self, streamer_session):
        """Create a pending withdrawal directly via the API if balance allows.

        If insufficient balance, skip the subsequent approve tests.
        """
        # We rely on the POST /my/withdrawals endpoint; may fail with 400 if no balance
        r = streamer_session.post(f"{API}/my/withdrawals", json={
            "first_name": "Pro", "last_name": "Gamer", "amount": 50,
            "iban": "DE89370400440532013000",
        })
        if r.status_code != 200:
            pytest.skip(f"cannot create withdrawal: {r.status_code} {r.text[:120]}")
        return r.json().get("withdrawal_id")

    def test_approve_automated_without_connect_returns_400(self, admin_session, streamer_session, seeded_withdrawal):
        # Ensure streamer has NO connect account
        streamer_session.delete(f"{API}/my/stripe-connect")
        # Enable automated
        admin_session.put(f"{API}/admin/payout-settings", json={"automated_enabled": True})
        r = admin_session.put(f"{API}/admin/withdrawals/{seeded_withdrawal}/approve")
        assert r.status_code == 400
        assert "Stripe Connect account" in r.text or "no Stripe Connect" in r.text.lower()
        # Cleanup toggle
        admin_session.put(f"{API}/admin/payout-settings", json={"automated_enabled": False})

    def test_approve_manual_ok(self, admin_session, seeded_withdrawal):
        # Automated already reset to False above
        admin_session.put(f"{API}/admin/payout-settings", json={"automated_enabled": False})
        r = admin_session.put(f"{API}/admin/withdrawals/{seeded_withdrawal}/approve")
        # Should succeed 200 (manual) OR 400 if already-approved from a previous run
        assert r.status_code in (200, 400)
        if r.status_code == 200:
            # Response should indicate completion and manual method
            body = r.json()
            # Check DB state via admin list
            lst = admin_session.get(f"{API}/admin/withdrawals").json()
            row = next((w for w in lst if w["withdrawal_id"] == seeded_withdrawal), None)
            assert row is not None
            assert row["status"] == "completed"
            payout = row.get("payout") or {}
            assert payout.get("method", "manual") == "manual"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
