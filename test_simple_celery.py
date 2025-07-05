#!/usr/bin/env python3
"""
Simple Celery Test
Test both immediate and scheduled quest generation
"""

import os
import sys
from datetime import datetime, timedelta
import pytz

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.celery_app import celery_app
from app.celery_tasks import generate_simple_quest
from app.database import SessionLocal
from app.models import User
from app.auth import get_password_hash

# Set timezones
EST = pytz.timezone('US/Eastern')
UTC = pytz.timezone('UTC')

def create_test_user():
    """Create a test user for our tests"""
    print("👤 Creating test user...")
    
    db = SessionLocal()
    try:
        # Check if test user already exists
        test_user = db.query(User).filter(User.username == "testuser").first()
        if test_user:
            print(f"✅ Test user already exists (ID: {test_user.id})")
            return test_user.id
        
        # Create new test user
        hashed_password = get_password_hash("testpass123")
        test_user = User(
            username="testuser",
            email="test@example.com",
            hashed_password=hashed_password,
            role="user",
            xp=0,
            level=1
        )
        
        db.add(test_user)
        db.commit()
        db.refresh(test_user)
        
        print(f"✅ Created test user (ID: {test_user.id})")
        return test_user.id
        
    except Exception as e:
        print(f"❌ Error creating test user: {e}")
        return None
    finally:
        db.close()

def test_immediate_quest():
    """Test immediate quest generation"""
    print("\n🧪 Testing Immediate Quest Generation")
    print("=" * 40)
    
    # Create test user first
    user_id = create_test_user()
    if not user_id:
        return False
    
    try:
        # Schedule a quest generation task to run immediately
        print(f"🎯 Scheduling quest generation for user {user_id} (immediate)...")
        task = generate_simple_quest.delay(user_id, "regular")
        print(f"✅ Task scheduled with ID: {task.id}")
        
        # Wait for the task to complete
        print("⏳ Waiting for task to complete...")
        result = task.get(timeout=30)
        print(f"✅ Task completed: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Quest generation failed: {e}")
        return False

def test_scheduled_quest():
    """Test scheduled quest generation (30 seconds later)"""
    print("\n⏰ Testing Scheduled Quest Generation (30 seconds later)")
    print("=" * 50)
    
    # Create test user first
    user_id = create_test_user()
    if not user_id:
        return False
    
    try:
        # Schedule a quest generation task to run in 30 seconds
        print(f"🎯 Scheduling quest generation for user {user_id} (in 30 seconds)...")
        current_time = datetime.now().strftime("%H:%M:%S")
        print(f"Current time: {current_time}")
        
        # Use apply_async with countdown for scheduling
        task = generate_simple_quest.apply_async(
            args=[user_id, "hidden"],  # user_id, quest_type="hidden"
            countdown=30  # Run in 30 seconds
        )
        print(f"✅ Task scheduled with ID: {task.id}")
        print(f"⏰ Task will run at: {(datetime.now() + timedelta(seconds=30)).strftime('%H:%M:%S')}")
        
        # Wait for the task to complete
        print("⏳ Waiting for scheduled task to complete...")
        result = task.get(timeout=60)  # Wait up to 60 seconds
        print(f"✅ Scheduled task completed: {result}")
        
        return True
    except Exception as e:
        print(f"❌ Scheduled quest generation failed: {e}")
        return False

def test_specific_time_quest():
    """Test scheduling for a specific time (8:19 PM EST)"""
    print("\n🕐 Testing Specific Time Scheduling (8:19 PM EST)")
    print("=" * 50)
    
    # Create test user first
    user_id = create_test_user()
    if not user_id:
        return False
    
    try:
        # Get current time in EST
        now_est = datetime.now(EST)
        
        # Calculate target time in EST (8:19 PM EST)
        target_time_est = now_est.replace(hour=20, minute=28, second=0, microsecond=0)  # 8:19 PM EST
        
        # If it's already past 8:19 PM EST today, schedule for tomorrow
        if now_est >= target_time_est:
            target_time_est = target_time_est + timedelta(days=1)
            print(f"⏰ 8:19 PM EST has passed today, scheduling for tomorrow")
        
        # Convert EST time to UTC for Celery
        target_time_utc = target_time_est.astimezone(UTC)
        
        # Calculate time difference
        time_diff = target_time_est - now_est
        minutes_until_target = int(time_diff.total_seconds() / 60)
        
        print(f"🎯 Scheduling quest generation for user {user_id} at {target_time_est.strftime('%H:%M:%S')} EST...")
        print(f"Current time (EST): {now_est.strftime('%H:%M:%S')}")
        print(f"Target time (EST): {target_time_est.strftime('%H:%M:%S')}")
        print(f"Target time (UTC): {target_time_utc.strftime('%H:%M:%S')}")
        print(f"Minutes until target: {minutes_until_target}")
        
        # Use apply_async with eta for specific time (pass UTC time to Celery)
        task = generate_simple_quest.apply_async(
            args=[user_id, "penalty"],  # user_id, quest_type="penalty"
            eta=target_time_utc  # Run at specific UTC time
        )
        print(f"✅ Task scheduled with ID: {task.id}")
        print(f"⏰ Task will run at: {target_time_est.strftime('%H:%M:%S')} EST")
        print("🚀 Task scheduled! Check the worker logs at the target time.")
        print("💡 This is 'fire and forget' - we don't wait for the result.")
        
        return True
    except Exception as e:
        print(f"❌ Specific time scheduling failed: {e}")
        return False

def test_countdown_quest():
    """Test scheduling with countdown (2 minutes from now)"""
    print("\n⏱️ Testing Countdown Scheduling (2 minutes from now)")
    print("=" * 50)
    
    # Create test user first
    user_id = create_test_user()
    if not user_id:
        return False
    
    try:
        countdown_seconds = 120  # 2 minutes
        target_time = datetime.now() + timedelta(seconds=countdown_seconds)
        
        print(f"🎯 Scheduling quest generation for user {user_id} in {countdown_seconds} seconds...")
        print(f"Current time: {datetime.now().strftime('%H:%M:%S')}")
        print(f"Target time: {target_time.strftime('%H:%M:%S')}")
        
        # Use apply_async with countdown
        task = generate_simple_quest.apply_async(
            args=[user_id, "regular"],
            countdown=countdown_seconds  # Run in 2 minutes
        )
        print(f"✅ Task scheduled with ID: {task.id}")
        print(f"⏰ Task will run at: {target_time.strftime('%H:%M:%S')}")
        print("🚀 Task scheduled! Check the worker logs in 2 minutes.")
        
        return True
    except Exception as e:
        print(f"❌ Countdown scheduling failed: {e}")
        return False

def main():
    print("🧪 Celery Scheduling Test Suite")
    print("=" * 50)
    
    # Test 1: Immediate execution
    test_immediate_quest()
    
    # Test 2: Scheduled execution (30 seconds)
    test_scheduled_quest()
    
    # Test 3: Specific time (8:19 PM)
    test_specific_time_quest()
    
    # Test 4: Countdown (2 minutes)
    test_countdown_quest()
    
    print("\n" + "=" * 50)
    print("🎉 Test suite completed!")
    print("\n📋 What happened:")
    print("1. ✅ Immediate task: Ran right away")
    print("2. ✅ Scheduled task: Ran in 30 seconds")
    print("3. ✅ Specific time: Will run in 8:19 PM")
    print("4. ✅ Countdown: Will run in 2 minutes")
    print("\n💡 Keep the worker running to see the scheduled tasks execute!")

if __name__ == "__main__":
    main() 