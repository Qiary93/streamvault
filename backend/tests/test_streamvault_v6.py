"""
Iteration 6 backend tests for StreamVault:
- /api/recommended: only live+broadcasting streamers, includes viewer_count/game_name/active_stream_id
- /api/categories: no broken (Pexels-404) image URLs
- /api/my/chat-settings: new fields (followers_only, subscribers_only, restricted_words, restricted_words_mode)
- /api/my/achievements + /api/users/{id}/achievements: 4 grades with missions & done flags
- /api/my/streamer-path: 4 missions (subs/followers/hours/chatters)
- /api/my/following: total + items list, is_live flag, live-first sort, pagination
- /api/admin/other-settings: GET/PUT admin-only, /api/config/features public
- /api/my/ad-opt-out: GET/PUT persists
- /api/ads/active?stream_id=X with opt-out -> ad:null reason=streamer_opt_out
- /api/admin/ad-settings: accepts vast ad_type + vast_url persists
- /api/ads/vast/resolve?url=INVALID -> 400
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"

STREAMER_EMAIL = "progamer@demo.com"
STREAMER_PASS = "Demo123!"
ADMIN_EMAIL = "admin@streamvault.com"
ADMIN_PASS = "Admin123!"


def _login(email, password):
    s = requests.Session()
    r = s.post(f"{API}/auth/login", json={"email": email, "password": password})
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if token:
        s.headers.update({"Authorization": f"Bearer {token}"})
    s.user_data = data.get("user", {}) or {}
    s.user_id = s.user_data.get("user_id") or data.get("user_id")
    return s


@pytest.fixture(scope="session")
def streamer_session():
    return _login(STREAMER_EMAIL, STREAMER_PASS)


@pytest.fixture(scope="session")
def admin_session():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


# ============= /api/recommended =============
class TestRecommended:
    def test_recommended_returns_list(self):
        r = requests.get(f"{API}/recommended")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)

    def test_recommended_only_live_broadcasting(self):
        r = requests.get(f"{API}/recommended")
        assert r.status_code == 200
        data = r.json()
        for item in data:
            # Each item must include enriched fields per spec
            assert "active_stream_id" in item
            assert "viewer_count" in item
            assert "game_name" in item
            assert item.get("broadcasting") is True
            assert item.get("is_streaming") is True
            assert isinstance(item.get("viewer_count"), int)
            assert "user_id" in item
            # Admins should not appear
            assert item.get("role") != "admin"


# ============= /api/categories: no broken image URLs =============
class TestCategories:
    def test_category_images_no_pexels_404(self):
        r = requests.get(f"{API}/categories")
        assert r.status_code == 200
        cats = r.json()
        assert isinstance(cats, list) and len(cats) > 0
        # sample fetch first 5 image urls — ensure status != 404
        bad = []
        for c in cats[:15]:
            url = c.get("image_url") or ""
            if not url:
                continue
            try:
                hr = requests.head(url, timeout=6, allow_redirects=True)
                if hr.status_code == 404:
                    bad.append((c.get("name"), url))
            except Exception:
                pass
        assert not bad, f"Broken category images (404): {bad}"


# ============= /api/my/chat-settings =============
class TestChatSettings:
    def test_get_defaults_shape(self, streamer_session):
        r = streamer_session.get(f"{API}/my/chat-settings")
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("chat_enabled", "rules", "followers_only", "subscribers_only",
                  "restricted_words", "restricted_words_mode"):
            assert k in data, f"missing key {k}"
        assert isinstance(data["restricted_words"], list)
        assert data["restricted_words_mode"] in ("filter", "block")

    def test_put_persists_new_fields(self, streamer_session):
        payload = {
            "chat_enabled": True,
            "rules": "Be kind",
            "followers_only": True,
            "subscribers_only": False,
            "restricted_words": ["badword1", "BadWord2", "  "],
            "restricted_words_mode": "block",
        }
        r = streamer_session.put(f"{API}/my/chat-settings", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data.get("followers_only") is True
        assert data.get("subscribers_only") is False
        assert data.get("restricted_words_mode") == "block"
        # restricted_words should be lowercased + whitespace trimmed
        rw = data.get("restricted_words")
        assert isinstance(rw, list)
        assert "badword1" in rw
        assert "badword2" in rw
        # GET must return same
        r2 = streamer_session.get(f"{API}/my/chat-settings")
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2["followers_only"] is True
        assert d2["restricted_words_mode"] == "block"
        assert "badword1" in d2["restricted_words"]

    def test_invalid_mode_defaults_to_filter(self, streamer_session):
        r = streamer_session.put(f"{API}/my/chat-settings", json={
            "chat_enabled": True, "rules": "", "followers_only": False,
            "subscribers_only": False, "restricted_words": [],
            "restricted_words_mode": "invalid_mode_xxx",
        })
        assert r.status_code == 200
        assert r.json().get("restricted_words_mode") == "filter"


# ============= /api/my/achievements =============
class TestAchievements:
    def test_my_achievements_shape(self, streamer_session):
        r = streamer_session.get(f"{API}/my/achievements")
        assert r.status_code == 200, r.text
        data = r.json()
        for k in ("grade", "verified", "stats", "grades"):
            assert k in data
        assert isinstance(data["grades"], list)
        assert len(data["grades"]) == 4, f"expected 4 grades, got {len(data['grades'])}"
        for g in data["grades"]:
            assert "grade" in g
            assert "missions" in g
            assert isinstance(g["missions"], list) and len(g["missions"]) > 0
            for m in g["missions"]:
                assert "id" in m and "done" in m and "required" in m and "current" in m
                assert isinstance(m["done"], bool)
        assert isinstance(data["verified"], bool)

    def test_public_achievements(self, streamer_session):
        uid = streamer_session.user_id
        assert uid
        r = requests.get(f"{API}/users/{uid}/achievements")
        assert r.status_code == 200
        data = r.json()
        assert "grades" in data and len(data["grades"]) == 4


# ============= /api/my/streamer-path =============
class TestStreamerPath:
    def test_missions_shape(self, streamer_session):
        r = streamer_session.get(f"{API}/my/streamer-path")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "missions" in data
        missions = data["missions"]
        assert isinstance(missions, list) and len(missions) == 4
        ids = {m["id"] for m in missions}
        assert ids == {"subs_50", "followers_500", "hours_300", "chatters_500"}
        for m in missions:
            assert "current" in m and "required" in m and "done" in m
            assert isinstance(m["done"], bool)


# ============= /api/my/following =============
class TestFollowing:
    def test_following_shape(self, streamer_session):
        r = streamer_session.get(f"{API}/my/following?limit=20&offset=0")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "total" in data and "items" in data
        assert isinstance(data["items"], list)
        for u in data["items"]:
            assert "is_live" in u
            assert "user_id" in u
        # Live-first sort
        if len(data["items"]) > 1:
            live_flags = [bool(u.get("is_live")) for u in data["items"]]
            first_false = next((i for i, v in enumerate(live_flags) if not v), None)
            if first_false is not None:
                # No True after first False
                assert not any(live_flags[first_false:]), "items not live-first sorted"

    def test_pagination_limit_offset(self, streamer_session):
        r = streamer_session.get(f"{API}/my/following?limit=2&offset=0")
        assert r.status_code == 200
        d = r.json()
        assert d.get("limit") == 2 and d.get("offset") == 0
        assert len(d["items"]) <= 2


# ============= /api/admin/other-settings + /api/config/features =============
class TestAdminOtherSettings:
    def test_non_admin_forbidden(self, streamer_session):
        r = streamer_session.get(f"{API}/admin/other-settings")
        assert r.status_code == 403

    def test_admin_get_put_roundtrip(self, admin_session):
        # read current
        r = admin_session.get(f"{API}/admin/other-settings")
        assert r.status_code == 200, r.text
        original = r.json()
        orig_ach = original.get("achievements_enabled", True)
        orig_path = original.get("path_enabled", True)
        # toggle off
        r2 = admin_session.put(f"{API}/admin/other-settings", json={
            "achievements_enabled": False, "path_enabled": False,
        })
        assert r2.status_code == 200
        d2 = r2.json()
        assert d2.get("achievements_enabled") is False
        assert d2.get("path_enabled") is False
        # public features endpoint reflects change
        rf = requests.get(f"{API}/config/features")
        assert rf.status_code == 200
        ff = rf.json()
        assert ff.get("achievements_enabled") is False
        assert ff.get("path_enabled") is False
        # restore original (per task instruction "toggle ON back at end")
        admin_session.put(f"{API}/admin/other-settings", json={
            "achievements_enabled": orig_ach, "path_enabled": orig_path,
        })
        rf2 = requests.get(f"{API}/config/features")
        assert rf2.status_code == 200
        assert rf2.json().get("achievements_enabled") is orig_ach

    def test_config_features_public(self):
        r = requests.get(f"{API}/config/features")
        assert r.status_code == 200
        d = r.json()
        assert "achievements_enabled" in d and "path_enabled" in d


# ============= /api/my/ad-opt-out =============
class TestAdOptOut:
    def test_get_default(self, streamer_session):
        # ensure clean: set false
        streamer_session.put(f"{API}/my/ad-opt-out", json={"opt_out": False})
        r = streamer_session.get(f"{API}/my/ad-opt-out")
        assert r.status_code == 200
        assert r.json().get("opt_out") is False

    def test_put_toggles(self, streamer_session):
        r = streamer_session.put(f"{API}/my/ad-opt-out", json={"opt_out": True})
        assert r.status_code == 200
        assert r.json().get("opt_out") is True
        r2 = streamer_session.get(f"{API}/my/ad-opt-out")
        assert r2.json().get("opt_out") is True
        # restore
        streamer_session.put(f"{API}/my/ad-opt-out", json={"opt_out": False})


# ============= /api/ads/active respects opt-out =============
class TestAdsActiveOptOut:
    def test_optout_returns_null_ad(self, streamer_session, admin_session):
        # 1. Enable ad-settings with a slot so cfg.enabled=True
        cur = admin_session.get(f"{API}/admin/ad-settings").json()
        slot = {
            "slot_id": "TEST_slot_optout",
            "name": "TEST slot",
            "placement": "live_pre_roll",
            "ad_type": "html",
            "ad_code": "<div>TEST</div>",
            "duration_sec": 5,
            "active": True,
        }
        payload = {
            "enabled": True,
            "revenue_share_percent": cur.get("revenue_share_percent", 70.0),
            "cpm_rates": cur.get("cpm_rates", {}),
            "ad_slots": (cur.get("ad_slots") or []) + [slot],
        }
        r0 = admin_session.put(f"{API}/admin/ad-settings", json=payload)
        assert r0.status_code == 200

        # 2. Streamer opts out
        streamer_session.put(f"{API}/my/ad-opt-out", json={"opt_out": True})

        # 3. Find streamer's stream (any stream — even non-live)
        #    use /api/streams + filter by user_id
        streams_r = requests.get(f"{API}/streams?limit=100")
        stream_id = None
        if streams_r.status_code == 200:
            for s in streams_r.json():
                if s.get("user_id") == streamer_session.user_id:
                    stream_id = s.get("stream_id")
                    break
        if not stream_id:
            # try /my/stream
            ms = streamer_session.get(f"{API}/my/stream")
            if ms.status_code == 200:
                stream_id = ms.json().get("stream_id")
        if not stream_id:
            pytest.skip("No stream found for streamer to test opt-out")

        r = requests.get(f"{API}/ads/active?placement=live_pre_roll&stream_id={stream_id}")
        assert r.status_code == 200
        d = r.json()
        assert d.get("ad") is None
        assert d.get("reason") == "streamer_opt_out"

        # cleanup
        streamer_session.put(f"{API}/my/ad-opt-out", json={"opt_out": False})
        # remove TEST slot
        cur2 = admin_session.get(f"{API}/admin/ad-settings").json()
        slots2 = [s for s in (cur2.get("ad_slots") or []) if s.get("slot_id") != "TEST_slot_optout"]
        admin_session.put(f"{API}/admin/ad-settings", json={
            "enabled": cur2.get("enabled", False),
            "revenue_share_percent": cur2.get("revenue_share_percent", 70.0),
            "cpm_rates": cur2.get("cpm_rates", {}),
            "ad_slots": slots2,
        })


# ============= /api/admin/ad-settings: VAST ad_type persists =============
class TestAdminAdSettingsVast:
    def test_vast_slot_persists(self, admin_session):
        cur = admin_session.get(f"{API}/admin/ad-settings").json()
        vast_slot = {
            "slot_id": "TEST_vast_slot",
            "name": "TEST VAST",
            "placement": "live_pre_roll",
            "ad_type": "vast",
            "vast_url": "https://example.com/vast.xml",
            "click_url": "https://example.com",
            "duration_sec": 15,
            "active": True,
        }
        payload = {
            "enabled": cur.get("enabled", False),
            "revenue_share_percent": cur.get("revenue_share_percent", 70.0),
            "cpm_rates": cur.get("cpm_rates", {}),
            "ad_slots": (cur.get("ad_slots") or []) + [vast_slot],
        }
        r = admin_session.put(f"{API}/admin/ad-settings", json=payload)
        assert r.status_code == 200, r.text
        # fetch back
        r2 = admin_session.get(f"{API}/admin/ad-settings")
        slots = r2.json().get("ad_slots") or []
        found = next((s for s in slots if s.get("slot_id") == "TEST_vast_slot"), None)
        assert found is not None, "VAST slot not persisted"
        assert found.get("ad_type") == "vast"
        assert found.get("vast_url") == "https://example.com/vast.xml"

        # cleanup
        cur3 = admin_session.get(f"{API}/admin/ad-settings").json()
        slots3 = [s for s in (cur3.get("ad_slots") or []) if s.get("slot_id") != "TEST_vast_slot"]
        admin_session.put(f"{API}/admin/ad-settings", json={
            "enabled": cur3.get("enabled", False),
            "revenue_share_percent": cur3.get("revenue_share_percent", 70.0),
            "cpm_rates": cur3.get("cpm_rates", {}),
            "ad_slots": slots3,
        })


# ============= /api/ads/vast/resolve =============
class TestVastResolve:
    def test_invalid_url_returns_400(self):
        r = requests.get(f"{API}/ads/vast/resolve?url=not_a_url")
        assert r.status_code == 400

    def test_empty_url_returns_400(self):
        r = requests.get(f"{API}/ads/vast/resolve?url=")
        assert r.status_code in (400, 422)
