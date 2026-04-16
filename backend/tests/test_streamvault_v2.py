#!/usr/bin/env python3
"""
StreamVault API Tests - Iteration 2
Tests for: LiveKit tokens, WebSocket chat, VOD system, notifications, subscriptions (5 tiers), stream key
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


@pytest.fixture(scope="module")
def api_client():
    """Shared requests session"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    return session


@pytest.fixture(scope="module")
def authenticated_client(api_client):
    """Session with auth cookie from demo user login"""
    response = api_client.post(f"{BASE_URL}/api/auth/login", json=DEMO_USER)
    if response.status_code != 200:
        pytest.skip("Authentication failed - skipping authenticated tests")
    return api_client


@pytest.fixture(scope="module")
def admin_client(api_client):
    """Session with admin auth"""
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    response = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
    if response.status_code != 200:
        pytest.skip("Admin authentication failed")
    return session


# ============= AUTHENTICATION TESTS =============

class TestAuthentication:
    """Authentication endpoint tests"""
    
    def test_demo_user_login(self, api_client):
        """Test demo user login with progamer@demo.com"""
        response = api_client.post(f"{BASE_URL}/api/auth/login", json=DEMO_USER)
        assert response.status_code == 200, f"Login failed: {response.text}"
        data = response.json()
        assert "user_id" in data or "user" in data, "Response should contain user data"
        print(f"Login successful for {DEMO_USER['email']}")
    
    def test_admin_login(self, api_client):
        """Test admin login"""
        session = requests.Session()
        response = session.post(f"{BASE_URL}/api/auth/login", json=ADMIN_USER)
        assert response.status_code == 200, f"Admin login failed: {response.text}"
        print("Admin login successful")
    
    def test_get_current_user(self, authenticated_client):
        """Test /auth/me endpoint returns user with stream_key"""
        response = authenticated_client.get(f"{BASE_URL}/api/auth/me")
        assert response.status_code == 200, f"Get current user failed: {response.text}"
        data = response.json()
        assert "user_id" in data, "Response should contain user_id"
        assert "stream_key" in data, "Response should contain stream_key (NEW FEATURE)"
        assert data["stream_key"] is not None, "stream_key should not be None"
        print(f"User has stream_key: {data['stream_key'][:20]}...")


# ============= LIVEKIT TOKEN TESTS =============

class TestLiveKitTokens:
    """LiveKit token generation endpoint tests"""
    
    def test_viewer_token_generation(self, api_client):
        """Test /api/livekit/token/viewer endpoint"""
        response = api_client.post(f"{BASE_URL}/api/livekit/token/viewer", json={
            "room_name": "test_room_123",
            "viewer_id": "test_viewer_001",
            "viewer_name": "Test Viewer"
        })
        assert response.status_code == 200, f"Viewer token generation failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "server_url" in data, "Response should contain server_url"
        assert len(data["token"]) > 50, "Token should be a valid JWT"
        print(f"Viewer token generated, server_url: {data['server_url']}")
    
    def test_streamer_token_generation(self, authenticated_client):
        """Test /api/livekit/token/streamer endpoint (requires auth)"""
        response = authenticated_client.post(f"{BASE_URL}/api/livekit/token/streamer", json={
            "room_name": "stream_test_room"
        })
        assert response.status_code == 200, f"Streamer token generation failed: {response.text}"
        data = response.json()
        assert "token" in data, "Response should contain token"
        assert "server_url" in data, "Response should contain server_url"
        print(f"Streamer token generated successfully")
    
    def test_viewer_token_missing_room(self, api_client):
        """Test viewer token fails without room_name"""
        response = api_client.post(f"{BASE_URL}/api/livekit/token/viewer", json={})
        assert response.status_code == 400, "Should fail without room_name"


# ============= SUBSCRIPTION TIERS TESTS =============

class TestSubscriptionTiers:
    """Subscription tiers endpoint tests"""
    
    def test_get_subscription_tiers(self, api_client):
        """Test /api/subscriptions/tiers returns 5 tiers"""
        response = api_client.get(f"{BASE_URL}/api/subscriptions/tiers")
        assert response.status_code == 200, f"Get tiers failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) == 5, f"Should have 5 tiers, got {len(data)}"
        
        # Verify tier amounts
        expected_amounts = [4.99, 9.99, 24.99, 49.99, 100.00]
        actual_amounts = sorted([tier["amount"] for tier in data])
        assert actual_amounts == expected_amounts, f"Tier amounts mismatch: {actual_amounts}"
        
        # Verify tier IDs
        tier_ids = [tier["tier_id"] for tier in data]
        for i in range(1, 6):
            assert f"tier{i}" in tier_ids, f"tier{i} should exist"
        
        print(f"5 subscription tiers verified: {expected_amounts}")
    
    def test_subscription_tier_details(self, api_client):
        """Test each tier has required fields"""
        response = api_client.get(f"{BASE_URL}/api/subscriptions/tiers")
        data = response.json()
        
        for tier in data:
            assert "tier_id" in tier, "Tier should have tier_id"
            assert "name" in tier, "Tier should have name"
            assert "amount" in tier, "Tier should have amount"
            assert "perks" in tier, "Tier should have perks"


# ============= NOTIFICATION TESTS =============

class TestNotifications:
    """Notification endpoint tests"""
    
    def test_get_notifications(self, authenticated_client):
        """Test /api/notifications endpoint"""
        response = authenticated_client.get(f"{BASE_URL}/api/notifications")
        assert response.status_code == 200, f"Get notifications failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Got {len(data)} notifications")
    
    def test_get_unread_count(self, authenticated_client):
        """Test /api/notifications/unread-count endpoint"""
        response = authenticated_client.get(f"{BASE_URL}/api/notifications/unread-count")
        assert response.status_code == 200, f"Get unread count failed: {response.text}"
        data = response.json()
        assert "count" in data, "Response should contain count"
        assert isinstance(data["count"], int), "Count should be an integer"
        print(f"Unread notifications: {data['count']}")
    
    def test_mark_all_read(self, authenticated_client):
        """Test /api/notifications/read-all endpoint"""
        response = authenticated_client.put(f"{BASE_URL}/api/notifications/read-all", json={})
        assert response.status_code == 200, f"Mark all read failed: {response.text}"
        
        # Verify count is now 0
        count_response = authenticated_client.get(f"{BASE_URL}/api/notifications/unread-count")
        assert count_response.json()["count"] == 0, "Unread count should be 0 after marking all read"


# ============= VOD TESTS =============

class TestVODs:
    """VOD (past streams) endpoint tests"""
    
    def test_get_vods(self, api_client):
        """Test /api/vods endpoint"""
        response = api_client.get(f"{BASE_URL}/api/vods")
        assert response.status_code == 200, f"Get VODs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Got {len(data)} VODs")
    
    def test_get_user_vods(self, api_client):
        """Test /api/users/{username}/vods endpoint"""
        response = api_client.get(f"{BASE_URL}/api/users/progamer/vods")
        assert response.status_code == 200, f"Get user VODs failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"


# ============= STREAM TESTS =============

class TestStreams:
    """Stream endpoint tests"""
    
    def test_get_live_streams(self, api_client):
        """Test /api/streams endpoint"""
        response = api_client.get(f"{BASE_URL}/api/streams")
        assert response.status_code == 200, f"Get streams failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one stream"
        print(f"Got {len(data)} live streams")
        return data
    
    def test_get_stream_by_id(self, api_client):
        """Test /api/streams/{stream_id} endpoint"""
        # First get a stream
        streams_response = api_client.get(f"{BASE_URL}/api/streams")
        streams = streams_response.json()
        if not streams:
            pytest.skip("No streams available")
        
        stream_id = streams[0]["stream_id"]
        response = api_client.get(f"{BASE_URL}/api/streams/{stream_id}")
        assert response.status_code == 200, f"Get stream failed: {response.text}"
        data = response.json()
        assert data["stream_id"] == stream_id
        print(f"Stream details: {data['title']}")
    
    def test_get_stream_chat(self, api_client):
        """Test /api/streams/{stream_id}/chat endpoint"""
        streams_response = api_client.get(f"{BASE_URL}/api/streams")
        streams = streams_response.json()
        if not streams:
            pytest.skip("No streams available")
        
        stream_id = streams[0]["stream_id"]
        response = api_client.get(f"{BASE_URL}/api/streams/{stream_id}/chat")
        assert response.status_code == 200, f"Get chat failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        print(f"Got {len(data)} chat messages")


# ============= FOLLOW TESTS =============

class TestFollowSystem:
    """Follow system tests - creates notification for target user"""
    
    def test_follow_user(self, authenticated_client):
        """Test following a user creates notification"""
        # Get a user to follow
        response = authenticated_client.get(f"{BASE_URL}/api/users/musicqueen")
        if response.status_code != 200:
            pytest.skip("User musicqueen not found")
        
        user_data = response.json()
        user_id = user_data.get("user_id")
        
        # Follow the user
        follow_response = authenticated_client.post(f"{BASE_URL}/api/users/{user_id}/follow", json={})
        # Could be 200 (success) or 400 (already following)
        assert follow_response.status_code in [200, 400], f"Follow failed: {follow_response.text}"
        print(f"Follow action completed for user {user_id}")


# ============= CATEGORY TESTS =============

class TestCategories:
    """Category endpoint tests"""
    
    def test_get_categories(self, api_client):
        """Test /api/categories endpoint"""
        response = api_client.get(f"{BASE_URL}/api/categories")
        assert response.status_code == 200, f"Get categories failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
        assert len(data) > 0, "Should have at least one category"
        print(f"Got {len(data)} categories")


# ============= SEARCH TESTS =============

class TestSearch:
    """Search functionality tests"""
    
    def test_search_streams(self, api_client):
        """Test search endpoint"""
        response = api_client.get(f"{BASE_URL}/api/search?q=live&type=streams")
        assert response.status_code == 200, f"Search failed: {response.text}"
        data = response.json()
        print(f"Search returned {len(data) if isinstance(data, list) else 'N/A'} results")


# ============= FEATURED CONTENT TESTS =============

class TestFeaturedContent:
    """Featured content tests"""
    
    def test_get_featured(self, api_client):
        """Test /api/featured endpoint"""
        response = api_client.get(f"{BASE_URL}/api/featured")
        assert response.status_code == 200, f"Get featured failed: {response.text}"


# ============= MY STREAM TESTS =============

class TestMyStream:
    """Dashboard stream tests"""
    
    def test_get_my_stream(self, authenticated_client):
        """Test /api/my/stream endpoint"""
        response = authenticated_client.get(f"{BASE_URL}/api/my/stream")
        # Could be 200 (has stream) or 404 (no stream)
        assert response.status_code in [200, 404], f"Get my stream failed: {response.text}"


# ============= SUBSCRIPTION STATUS TESTS =============

class TestSubscriptionStatus:
    """Subscription status tests"""
    
    def test_get_my_subscriptions(self, authenticated_client):
        """Test /api/subscriptions/my endpoint"""
        response = authenticated_client.get(f"{BASE_URL}/api/subscriptions/my")
        assert response.status_code == 200, f"Get my subscriptions failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
    
    def test_get_my_subscribers(self, authenticated_client):
        """Test /api/subscriptions/subscribers endpoint"""
        response = authenticated_client.get(f"{BASE_URL}/api/subscriptions/subscribers")
        assert response.status_code == 200, f"Get subscribers failed: {response.text}"
        data = response.json()
        assert isinstance(data, list), "Response should be a list"
    
    def test_check_subscription_status(self, authenticated_client):
        """Test /api/subscriptions/check/{streamer_id} endpoint"""
        # Get a user to check subscription for
        users_response = authenticated_client.get(f"{BASE_URL}/api/users/musicqueen")
        if users_response.status_code != 200:
            pytest.skip("User not found")
        
        user_id = users_response.json().get("user_id")
        response = authenticated_client.get(f"{BASE_URL}/api/subscriptions/check/{user_id}")
        assert response.status_code == 200, f"Check subscription failed: {response.text}"
        data = response.json()
        assert "subscribed" in data, "Response should contain subscribed field"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
