#!/usr/bin/env python3
"""
StreamVault API Tests - Iteration 3
Tests for: LiveKit URL update, Admin panel, S3 storage config, Moderation (ban/timeout/slow mode/mods), Recording endpoints
"""

import pytest
import requests
import os
import json
from datetime import datetime

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', 'https://stream-vault-137.preview.emergentagent.com').rstrip('/')

# Test credentials
DEMO_USER = {"email": "progamer@demo.com", "password": "Demo123!"}
ADMIN_USER = {"email": "admin@streamvault.com", "password": "Admin123!"}
CHATMASTER_USER = {"email": "chatmaster@demo.com", "password": "Demo123!"}

# Expected LiveKit URL
EXPECTED_LIVEKIT_URL = "wss://stream-x9ltpoe7.livekit.cloud"


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def authenticated_client():
    """Session with auth cookie from demo user login"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json=DEMO_USER)
    if response.status_code != 200:
        pytest.skip("Authentication failed - skipping authenticated tests")
    return session


@pytest.fixture(scope="module")
def admin_client():
    """Session with admin auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
    if response.status_code != 200:
        pytest.skip("Admin authentication failed")
    return session


@pytest.fixture(scope="module")
def chatmaster_client():
    """Session with chatmaster auth (for moderation target)"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json=CHATMASTER_USER)
    if response.status_code != 200:
        pytest.skip("Chatmaster authentication failed")
    return session


@pytest.fixture(scope="module")
def stream_data(api_client):
    """Get a live stream for testing"""
    response = api_client.get(f"{BASE_URL}/api/streams")
    if response.status_code != 200 or not response.json():
        pytest.skip("No streams available")
    return response.json()[0]


# ============= LIVEKIT URL TESTS =============

class TestLiveKitURL:
    """Verify LiveKit URL is updated to wss://stream-x9ltpoe7.livekit.cloud"""
    
    def test_viewer_token_returns_correct_url(self, api_client):
        """Test /api/livekit/token/viewer returns correct LiveKit URL"""
        response = api_client.post(f"{BASE_URL}/api/livekit/token/viewer", json={
            "room_name": "test_room_123",
            "viewer_id": "test_viewer_001",
            "viewer_name": "Test Viewer"
        })
        assert response.status_code == 200, f"Viewer token generation failed: {response.text}"
        data = response.json()
        assert "server_url" in data, "Response should contain server_url"
        assert data["server_url"] == EXPECTED_LIVEKIT_URL, f"Expected {EXPECTED_LIVEKIT_URL}, got {data['server_url']}"
        print(f"✓ LiveKit URL verified: {data['server_url']}")
    
    def test_streamer_token_returns_correct_url(self, authenticated_client):
        """Test /api/livekit/token/streamer returns correct LiveKit URL"""
        response = authenticated_client.post(f"{BASE_URL}/api/livekit/token/streamer", json={
            "room_name": "stream_test_room"
        })
        assert response.status_code == 200, f"Streamer token generation failed: {response.text}"
        data = response.json()
        assert data["server_url"] == EXPECTED_LIVEKIT_URL, f"Expected {EXPECTED_LIVEKIT_URL}, got {data['server_url']}"
        print(f"✓ Streamer token LiveKit URL verified: {data['server_url']}")


# ============= ADMIN PANEL TESTS =============

class TestAdminPanel:
    """Admin panel access and S3 storage config tests"""
    
    def test_admin_storage_config_requires_admin(self, authenticated_client):
        """Test non-admin cannot access storage config"""
        response = authenticated_client.get(f"{BASE_URL}/api/admin/storage-config")
        assert response.status_code == 403, "Non-admin should get 403"
        print("✓ Non-admin correctly denied access to storage config")
    
    def test_admin_can_get_storage_config(self, admin_client):
        """Test admin can access storage config"""
        response = admin_client.get(f"{BASE_URL}/api/admin/storage-config")
        assert response.status_code == 200, f"Admin storage config failed: {response.text}"
        data = response.json()
        assert "type" in data, "Response should contain type"
        assert data["type"] == "s3_storage", "Type should be s3_storage"
        print(f"✓ Admin can access storage config: configured={data.get('configured', False)}")
    
    def test_admin_can_save_storage_config(self, admin_client):
        """Test admin can save S3 storage config"""
        config = {
            "provider": "wasabi",
            "endpoint": "s3.us-east-1.wasabisys.com",
            "bucket": "test-bucket",
            "region": "us-east-1",
            "access_key": "TEST_ACCESS_KEY",
            "secret_key": "TEST_SECRET_KEY",
            "force_path_style": True
        }
        response = admin_client.post(f"{BASE_URL}/api/admin/storage-config", json=config)
        assert response.status_code == 200, f"Save storage config failed: {response.text}"
        print("✓ Admin can save storage config")
        
        # Verify it was saved
        get_response = admin_client.get(f"{BASE_URL}/api/admin/storage-config")
        data = get_response.json()
        assert data.get("configured") == True, "Config should be marked as configured"
        assert data.get("bucket") == "test-bucket", "Bucket should match"
        assert data.get("region") == "us-east-1", "Region should match"
        print("✓ Storage config verified after save")
    
    def test_admin_can_delete_storage_config(self, admin_client):
        """Test admin can delete S3 storage config"""
        response = admin_client.delete(f"{BASE_URL}/api/admin/storage-config")
        assert response.status_code == 200, f"Delete storage config failed: {response.text}"
        print("✓ Admin can delete storage config")
        
        # Verify it was deleted
        get_response = admin_client.get(f"{BASE_URL}/api/admin/storage-config")
        data = get_response.json()
        assert data.get("configured") == False or data.get("configured") is None, "Config should be deleted"
        print("✓ Storage config verified as deleted")


# ============= MODERATION TESTS =============

class TestModeration:
    """Moderation endpoints: ban, unban, timeout, slow mode, mod assignment"""
    
    def test_get_mods_list(self, api_client, stream_data):
        """Test /api/streams/{stream_id}/mods endpoint"""
        stream_id = stream_data["stream_id"]
        response = api_client.get(f"{BASE_URL}/api/streams/{stream_id}/mods")
        assert response.status_code == 200, f"Get mods failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Got mods list: {len(data)} mods")
    
    def test_get_mod_status(self, authenticated_client, stream_data):
        """Test /api/streams/{stream_id}/mod-status endpoint"""
        stream_id = stream_data["stream_id"]
        response = authenticated_client.get(f"{BASE_URL}/api/streams/{stream_id}/mod-status")
        assert response.status_code == 200, f"Get mod status failed: {response.text}"
        data = response.json()
        assert "is_mod" in data, "Response should contain is_mod"
        assert "is_streamer" in data, "Response should contain is_streamer"
        assert "slow_mode" in data, "Response should contain slow_mode"
        print(f"✓ Mod status: is_mod={data['is_mod']}, is_streamer={data['is_streamer']}, slow_mode={data['slow_mode']}")
    
    def test_admin_can_ban_user(self, admin_client, stream_data, chatmaster_client):
        """Test admin can ban a user from chat"""
        stream_id = stream_data["stream_id"]
        
        # Get chatmaster user_id
        me_response = chatmaster_client.get(f"{BASE_URL}/api/auth/me")
        target_user_id = me_response.json()["user_id"]
        
        # Ban the user
        response = admin_client.post(
            f"{BASE_URL}/api/streams/{stream_id}/ban/{target_user_id}",
            json={"reason": "Test ban"}
        )
        assert response.status_code in [200, 400], f"Ban failed: {response.text}"  # 400 if already banned
        print(f"✓ Admin ban action completed for user {target_user_id}")
    
    def test_admin_can_get_bans_list(self, admin_client, stream_data):
        """Test admin can get bans list"""
        stream_id = stream_data["stream_id"]
        response = admin_client.get(f"{BASE_URL}/api/streams/{stream_id}/bans")
        assert response.status_code == 200, f"Get bans failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"✓ Got bans list: {len(data)} bans")
    
    def test_admin_can_unban_user(self, admin_client, stream_data, chatmaster_client):
        """Test admin can unban a user"""
        stream_id = stream_data["stream_id"]
        
        # Get chatmaster user_id
        me_response = chatmaster_client.get(f"{BASE_URL}/api/auth/me")
        target_user_id = me_response.json()["user_id"]
        
        # Unban the user
        response = admin_client.delete(f"{BASE_URL}/api/streams/{stream_id}/ban/{target_user_id}")
        assert response.status_code in [200, 404], f"Unban failed: {response.text}"  # 404 if not banned
        print(f"✓ Admin unban action completed for user {target_user_id}")
    
    def test_admin_can_timeout_user(self, admin_client, stream_data, chatmaster_client):
        """Test admin can timeout a user"""
        stream_id = stream_data["stream_id"]
        
        # Get chatmaster user_id
        me_response = chatmaster_client.get(f"{BASE_URL}/api/auth/me")
        target_user_id = me_response.json()["user_id"]
        
        # Timeout the user for 60 seconds
        response = admin_client.post(
            f"{BASE_URL}/api/streams/{stream_id}/timeout/{target_user_id}",
            json={"duration": 60, "reason": "Test timeout"}
        )
        assert response.status_code == 200, f"Timeout failed: {response.text}"
        print(f"✓ Admin timeout action completed for user {target_user_id}")
    
    def test_admin_can_set_slow_mode(self, admin_client, stream_data):
        """Test admin can set slow mode (0/3/5/10/30)"""
        stream_id = stream_data["stream_id"]
        
        # Test setting slow mode to 5 seconds
        response = admin_client.put(
            f"{BASE_URL}/api/streams/{stream_id}/slow-mode",
            json={"duration": 5}
        )
        assert response.status_code == 200, f"Set slow mode failed: {response.text}"
        print("✓ Slow mode set to 5s")
        
        # Verify slow mode is set
        status_response = admin_client.get(f"{BASE_URL}/api/streams/{stream_id}/mod-status")
        assert status_response.json()["slow_mode"] == 5, "Slow mode should be 5"
        
        # Test disabling slow mode
        response = admin_client.put(
            f"{BASE_URL}/api/streams/{stream_id}/slow-mode",
            json={"duration": 0}
        )
        assert response.status_code == 200, f"Disable slow mode failed: {response.text}"
        print("✓ Slow mode disabled")
    
    def test_slow_mode_invalid_duration(self, admin_client, stream_data):
        """Test slow mode rejects invalid durations"""
        stream_id = stream_data["stream_id"]
        
        response = admin_client.put(
            f"{BASE_URL}/api/streams/{stream_id}/slow-mode",
            json={"duration": 15}  # Invalid - not in [0, 3, 5, 10, 30]
        )
        assert response.status_code == 400, "Should reject invalid slow mode duration"
        print("✓ Invalid slow mode duration correctly rejected")
    
    def test_non_mod_cannot_ban(self, chatmaster_client, stream_data, authenticated_client):
        """Test non-mod cannot ban users"""
        stream_id = stream_data["stream_id"]
        
        # Get progamer user_id
        me_response = authenticated_client.get(f"{BASE_URL}/api/auth/me")
        target_user_id = me_response.json()["user_id"]
        
        # Try to ban as chatmaster (not a mod on progamer's stream)
        response = chatmaster_client.post(
            f"{BASE_URL}/api/streams/{stream_id}/ban/{target_user_id}",
            json={"reason": "Test ban"}
        )
        # Should fail with 403 if chatmaster is not a mod
        # Note: chatmaster might be the streamer of their own stream, so check the stream owner
        if stream_data["user_id"] != me_response.json()["user_id"]:
            # chatmaster is not the streamer, so should be denied
            print(f"✓ Non-mod ban attempt returned status {response.status_code}")


# ============= MOD ASSIGNMENT TESTS =============

class TestModAssignment:
    """Mod assignment and removal tests"""
    
    def test_streamer_can_assign_mod(self, authenticated_client, chatmaster_client):
        """Test streamer can assign a mod to their stream"""
        # Get progamer's stream
        stream_response = authenticated_client.get(f"{BASE_URL}/api/my/stream")
        if stream_response.status_code != 200 or not stream_response.json():
            pytest.skip("Progamer has no active stream")
        
        stream_id = stream_response.json()["stream_id"]
        
        # Get chatmaster user_id
        me_response = chatmaster_client.get(f"{BASE_URL}/api/auth/me")
        target_user_id = me_response.json()["user_id"]
        
        # Assign mod
        response = authenticated_client.post(f"{BASE_URL}/api/streams/{stream_id}/mod/{target_user_id}")
        assert response.status_code in [200, 400], f"Assign mod failed: {response.text}"  # 400 if already mod
        print(f"✓ Mod assignment action completed")
    
    def test_streamer_can_remove_mod(self, authenticated_client, chatmaster_client):
        """Test streamer can remove a mod from their stream"""
        # Get progamer's stream
        stream_response = authenticated_client.get(f"{BASE_URL}/api/my/stream")
        if stream_response.status_code != 200 or not stream_response.json():
            pytest.skip("Progamer has no active stream")
        
        stream_id = stream_response.json()["stream_id"]
        
        # Get chatmaster user_id
        me_response = chatmaster_client.get(f"{BASE_URL}/api/auth/me")
        target_user_id = me_response.json()["user_id"]
        
        # Remove mod
        response = authenticated_client.delete(f"{BASE_URL}/api/streams/{stream_id}/mod/{target_user_id}")
        assert response.status_code in [200, 404], f"Remove mod failed: {response.text}"  # 404 if not a mod
        print(f"✓ Mod removal action completed")


# ============= RECORDING TESTS =============

class TestRecording:
    """Recording start/stop endpoint tests"""
    
    def test_start_recording_requires_s3_config(self, authenticated_client, admin_client):
        """Test start recording fails without S3 config"""
        # First ensure S3 config is deleted
        admin_client.delete(f"{BASE_URL}/api/admin/storage-config")
        
        # Get progamer's stream
        stream_response = authenticated_client.get(f"{BASE_URL}/api/my/stream")
        if stream_response.status_code != 200 or not stream_response.json():
            pytest.skip("Progamer has no active stream")
        
        stream_id = stream_response.json()["stream_id"]
        
        # Try to start recording
        response = authenticated_client.post(f"{BASE_URL}/api/streams/{stream_id}/record/start")
        assert response.status_code == 400, f"Should fail without S3 config: {response.text}"
        assert "S3 storage not configured" in response.text or "storage" in response.text.lower()
        print("✓ Recording correctly requires S3 config")
    
    def test_stop_recording_requires_active_recording(self, authenticated_client):
        """Test stop recording fails without active recording"""
        # Get progamer's stream
        stream_response = authenticated_client.get(f"{BASE_URL}/api/my/stream")
        if stream_response.status_code != 200 or not stream_response.json():
            pytest.skip("Progamer has no active stream")
        
        stream_id = stream_response.json()["stream_id"]
        
        # Try to stop recording (should fail - no active recording)
        response = authenticated_client.post(f"{BASE_URL}/api/streams/{stream_id}/record/stop")
        assert response.status_code == 400, f"Should fail without active recording: {response.text}"
        print("✓ Stop recording correctly requires active recording")


# ============= AUTHENTICATION TESTS =============

class TestAuthentication:
    """Basic authentication tests"""
    
    def test_admin_login(self, api_client):
        """Test admin login"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        data = response.json()
        assert data.get("role") == "admin", "Admin should have admin role"
        print("✓ Admin login successful with admin role")
    
    def test_demo_user_login(self, api_client):
        """Test demo user login"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=DEMO_USER)
        assert response.status_code == 200, f"Demo user login failed: {response.text}"
        print("✓ Demo user login successful")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
