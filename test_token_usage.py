#!/usr/bin/env python3
"""
Test script to demonstrate JWT token usage with your FastAPI application.
This shows the complete flow from login to using protected endpoints and refreshing tokens.
"""

import requests
import json
import time

# API base URL
BASE_URL = "http://localhost:8000"

def test_jwt_flow():
    print("🔐 Testing JWT Token Flow with Refresh Tokens\n")
    
    # Step 1: Register a user (if needed)
    print("1️⃣ Registering a test user...")
    register_data = {
        "username": "testuser",
        "email": "test@example.com", 
        "password": "testpassword123"
    }
    
    try:
        response = requests.put(f"{BASE_URL}/users/register", json=register_data)
        if response.status_code == 200:
            print("✅ User registered successfully")
        elif response.status_code == 409:
            print("ℹ️  User already exists, continuing...")
        else:
            print(f"❌ Registration failed: {response.text}")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to server. Make sure your FastAPI app is running!")
        print("   Run: uvicorn app.main:app --reload")
        return
    
    # Step 2: Login to get tokens
    print("\n2️⃣ Logging in to get JWT tokens...")
    login_data = {
        "username": "testuser",
        "password": "testpassword123"
    }
    
    response = requests.post(f"{BASE_URL}/users/login", data=login_data)  # Using form data for OAuth2
    if response.status_code == 200:
        token_data = response.json()
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        print(f"✅ Login successful!")
        print(f"🔑 Access Token: {access_token[:50]}...")
        print(f"🔄 Refresh Token: {refresh_token[:50]}...")
    else:
        print(f"❌ Login failed: {response.text}")
        return
    
    # Step 3: Use access token to access protected route
    print("\n3️⃣ Using access token to access protected route...")
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    response = requests.get(f"{BASE_URL}/protected/", headers=headers)
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Protected route accessed successfully!")
        print(f"📄 Response: {result}")
    else:
        print(f"❌ Failed to access protected route: {response.text}")
    
    # Step 4: Test /me endpoint
    print("\n4️⃣ Testing /me endpoint...")
    response = requests.get(f"{BASE_URL}/protected/me", headers=headers)
    if response.status_code == 200:
        result = response.json()
        print(f"✅ /me endpoint works!")
        print(f"📄 Response: {result}")
    else:
        print(f"❌ /me endpoint failed: {response.text}")
    
    # Step 5: Test refresh token functionality
    print("\n5️⃣ Testing refresh token functionality...")
    refresh_data = {
        "refresh_token": refresh_token
    }
    
    response = requests.post(f"{BASE_URL}/users/refresh", json=refresh_data)
    if response.status_code == 200:
        refresh_result = response.json()
        new_access_token = refresh_result["access_token"]
        print(f"✅ Token refreshed successfully!")
        print(f"🆕 New Access Token: {new_access_token[:50]}...")
        
        # Test the new access token
        print("\n6️⃣ Testing new access token...")
        headers = {
            "Authorization": f"Bearer {new_access_token}"
        }
        
        response = requests.get(f"{BASE_URL}/protected/", headers=headers)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ New access token works!")
            print(f"📄 Response: {result}")
        else:
            print(f"❌ New access token failed: {response.text}")
    else:
        print(f"❌ Token refresh failed: {response.text}")
    
    # Step 7: Try without token (should fail)
    print("\n7️⃣ Testing without token (should fail)...")
    response = requests.get(f"{BASE_URL}/protected/")
    if response.status_code == 401:
        print("✅ Correctly rejected request without token")
    else:
        print(f"❌ Unexpected response: {response.status_code}")
    
    # Step 8: Try with invalid token (should fail)
    print("\n8️⃣ Testing with invalid token (should fail)...")
    headers = {
        "Authorization": "Bearer invalid_token_here"
    }
    response = requests.get(f"{BASE_URL}/protected/", headers=headers)
    if response.status_code == 401:
        print("✅ Correctly rejected request with invalid token")
    else:
        print(f"❌ Unexpected response: {response.status_code}")
    
    # Step 9: Test health endpoint
    print("\n9️⃣ Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    if response.status_code == 200:
        result = response.json()
        print(f"✅ Health check passed!")
        print(f"📄 Response: {result}")
    else:
        print(f"❌ Health check failed: {response.text}")
    
    print("\n🎉 JWT token flow with refresh tokens test completed!")

if __name__ == "__main__":
    test_jwt_flow() 