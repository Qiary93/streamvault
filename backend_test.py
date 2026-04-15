#!/usr/bin/env python3

import requests
import sys
import json
from datetime import datetime

class StreamVaultAPITester:
    def __init__(self, base_url="https://stream-vault-137.preview.emergentagent.com"):
        self.base_url = base_url
        self.session = requests.Session()
        self.tests_run = 0
        self.tests_passed = 0
        self.admin_token = None
        self.user_token = None
        self.test_results = []

    def log_test(self, name, success, details=""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name} - {details}")
        
        self.test_results.append({
            "test": name,
            "success": success,
            "details": details
        })

    def run_test(self, name, method, endpoint, expected_status, data=None, headers=None):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        test_headers = {'Content-Type': 'application/json'}
        if headers:
            test_headers.update(headers)

        try:
            if method == 'GET':
                response = self.session.get(url, headers=test_headers)
            elif method == 'POST':
                response = self.session.post(url, json=data, headers=test_headers)
            elif method == 'PUT':
                response = self.session.put(url, json=data, headers=test_headers)
            elif method == 'DELETE':
                response = self.session.delete(url, headers=test_headers)

            success = response.status_code == expected_status
            details = f"Expected {expected_status}, got {response.status_code}"
            if not success and response.text:
                try:
                    error_data = response.json()
                    details += f" - {error_data.get('detail', response.text[:100])}"
                except:
                    details += f" - {response.text[:100]}"

            self.log_test(name, success, details if not success else "")
            return success, response.json() if success and response.text else {}

        except Exception as e:
            self.log_test(name, False, f"Exception: {str(e)}")
            return False, {}

    def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n🔐 Testing Authentication Endpoints...")
        
        # Test admin login
        success, response = self.run_test(
            "Admin Login",
            "POST",
            "api/auth/login",
            200,
            data={"email": "admin@streamvault.com", "password": "Admin123!"}
        )
        if success:
            # Extract token from cookies if available
            if 'access_token' in self.session.cookies:
                self.admin_token = self.session.cookies['access_token']

        # Test demo user login
        success, response = self.run_test(
            "Demo User Login",
            "POST", 
            "api/auth/login",
            200,
            data={"email": "progamer@demo.com", "password": "Demo123!"}
        )
        if success:
            if 'access_token' in self.session.cookies:
                self.user_token = self.session.cookies['access_token']

        # Test user registration
        test_email = f"test_{datetime.now().strftime('%H%M%S')}@test.com"
        success, response = self.run_test(
            "User Registration",
            "POST",
            "api/auth/register", 
            200,
            data={
                "email": test_email,
                "username": f"testuser_{datetime.now().strftime('%H%M%S')}",
                "password": "TestPass123!",
                "display_name": "Test User"
            }
        )

        # Test /auth/me endpoint
        self.run_test(
            "Get Current User",
            "GET",
            "api/auth/me",
            200
        )

        # Test logout
        self.run_test(
            "User Logout",
            "POST",
            "api/auth/logout",
            200
        )

    def test_stream_endpoints(self):
        """Test stream-related endpoints"""
        print("\n📺 Testing Stream Endpoints...")
        
        # Test get streams
        self.run_test(
            "Get Live Streams",
            "GET",
            "api/streams",
            200
        )

        # Test get featured content
        self.run_test(
            "Get Featured Content",
            "GET", 
            "api/featured",
            200
        )

        # Test get categories
        self.run_test(
            "Get Categories",
            "GET",
            "api/categories", 
            200
        )

        # Test search functionality
        self.run_test(
            "Search Streams",
            "GET",
            "api/search?q=gaming&type=streams",
            200
        )

    def test_user_endpoints(self):
        """Test user-related endpoints"""
        print("\n👤 Testing User Endpoints...")
        
        # Test get user profile
        self.run_test(
            "Get User Profile",
            "GET",
            "api/users/progamer",
            200
        )

    def test_chat_endpoints(self):
        """Test chat functionality"""
        print("\n💬 Testing Chat Endpoints...")
        
        # First get a stream ID
        success, streams_response = self.run_test(
            "Get Streams for Chat Test",
            "GET",
            "api/streams",
            200
        )
        
        if success and streams_response and len(streams_response) > 0:
            stream_id = streams_response[0].get('stream_id')
            if stream_id:
                # Test get chat messages
                self.run_test(
                    "Get Chat Messages",
                    "GET",
                    f"api/streams/{stream_id}/chat",
                    200
                )

    def test_donation_endpoints(self):
        """Test donation functionality"""
        print("\n💰 Testing Donation Endpoints...")
        
        # Test donation endpoints (these require auth, so might fail)
        self.run_test(
            "Get Received Donations",
            "GET",
            "api/donations/received",
            401  # Expected to fail without auth
        )

    def run_all_tests(self):
        """Run all API tests"""
        print("🚀 Starting StreamVault API Tests...")
        print(f"Testing against: {self.base_url}")
        
        self.test_auth_endpoints()
        self.test_stream_endpoints() 
        self.test_user_endpoints()
        self.test_chat_endpoints()
        self.test_donation_endpoints()
        
        # Print summary
        print(f"\n📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed")
            return 1

def main():
    tester = StreamVaultAPITester()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())