#!/usr/bin/env python3
"""
Test script for daily quest functionality with custom tasks
"""

import requests
import json
from datetime import datetime

# API base URL
BASE_URL = "http://localhost:8000"

def test_daily_quest_functionality():
    """Test the complete daily quest functionality"""
    
    print("=== Testing Daily Quest Functionality ===\n")
    
    # 1. Create a test user
    print("1. Creating test user...")
    user_data = {
        "username": "testuser_daily",
        "email": "testdaily@example.com",
        "password": "testpass123"
    }
    
   
    
    # 2. Login to get access token
    print("\n2. Logging in...")
    login_data = {
        "username": user_data["username"],
        "password": user_data["password"]
    }
    
    response = requests.post(f"{BASE_URL}/users/login", json=login_data)
    if response.status_code == 200:
        tokens = response.json()
        access_token = tokens["access_token"]
        print("✓ Login successful")
    else:
        print(f"✗ Login failed: {response.text}")
        return
    
    headers = {"Authorization": f"Bearer {access_token}"}
    
    # 3. Set custom daily quest tasks
    print("\n3. Setting custom daily quest tasks...")
    daily_tasks = {
        "tasks": [
            {
                "title": "Swimming Laps",
                "description": "Complete 50 swimming laps"
            },
            {
                "title": "Meditation",
                "description": "Meditate for 15 minutes"
            },
            {
                "title": "Push-ups",
                "description": "Do 100 push-ups"
            },
            {
                "title": "Reading",
                "description": "Read for 30 minutes"
            }
        ]
    }
    
    response = requests.put(f"{BASE_URL}/users/me/daily-quest-tasks", 
                          json=daily_tasks, headers=headers)
    if response.status_code == 200:
        saved_tasks = response.json()
        print("✓ Daily quest tasks set successfully")
        print("Tasks:")
        for i, task in enumerate(saved_tasks["tasks"], 1):
            print(f"  {i}. {task['title']}: {task['description']}")
    else:
        print(f"✗ Failed to set daily quest tasks: {response.text}")
        return
    
    # 4. Get current daily quest tasks
    print("\n4. Getting current daily quest tasks...")
    response = requests.get(f"{BASE_URL}/users/me/daily-quest-tasks", headers=headers)
    if response.status_code == 200:
        current_tasks = response.json()
        print("✓ Retrieved daily quest tasks")
        print("Current tasks:")
        for i, task in enumerate(current_tasks["tasks"], 1):
            print(f"  {i}. {task['title']}: {task['description']}")
    else:
        print(f"✗ Failed to get daily quest tasks: {response.text}")
    
    # 5. Set daily quest time preference
    print("\n5. Setting daily quest time preference...")
    time_preference = {
        "daily_quest_time": "2024-01-01T08:00:00"  # 8 AM with proper datetime format
    }
    
    response = requests.put(f"{BASE_URL}/users/me", json=time_preference, headers=headers)
    if response.status_code == 200:
        updated_user = response.json()
        print(f"✓ Daily quest time set to: {updated_user['daily_quest_time']}")
    else:
        print(f"✗ Failed to set daily quest time: {response.text}")
    
    # 6. Get user stats
    print("\n6. Getting user stats...")
    response = requests.get(f"{BASE_URL}/users/me/stats", headers=headers)
    if response.status_code == 200:
        stats = response.json()
        print("✓ User stats retrieved")
        print(f"  Level: {stats['user_info']['level']}")
        print(f"  XP: {stats['user_info']['xp']}")
        print(f"  Daily quests completed: {stats['quest_statistics']['quest_types']['daily']}")
    else:
        print(f"✗ Failed to get user stats: {response.text}")
    
    print("\n=== Test Complete ===")
    print("\nThe daily quest system now supports:")
    print("• Custom daily quest tasks (up to 4 tasks)")
    print("• User-configurable daily quest time")
    print("• Automatic daily quest generation with custom tasks")
    print("• Task format: title + description")
    print("\nExample daily quest would contain:")
    print("1. Swimming Laps: Complete 50 swimming laps")
    print("2. Meditation: Meditate for 15 minutes") 
    print("3. Push-ups: Do 100 push-ups")
    print("4. Reading: Read for 30 minutes")

if __name__ == "__main__":
    test_daily_quest_functionality() 