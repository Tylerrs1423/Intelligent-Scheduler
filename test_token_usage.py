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

def test_leveling_flow():
    print("Testing leveling flow...")
    print("Logging in...")
    login_data = {
        "username": "testuser",
        "password": "testpassword"
    }
    response = requests.post(f"{BASE_URL}/users/login", json=login_data)

    if response.status_code != 200:
        print(f"Login failed: {response.status_code} {response.text}")
        return
    
    print("Login successful")
    print(response.json())
    
    token = response.json()["access_token"]

    create_quest_data = {
        "title": "Test Quest",
        "description": "This is a test quest",
        "reward": 100,
        
    }
    
if __name__ == "__main__":
    test_jwt_flow() 