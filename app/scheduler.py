"""
Quest Scheduler for AI Foco
Handles quest generation, scheduling, and triggering
"""

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, time
from sqlalchemy.orm import Session
from typing import Optional
import random

from .database import SessionLocal
from .models import User, Quest, QuestStatus, QuestType
from .quest_generator import generate_quest, generate_daily_quest

# Global scheduler instance
scheduler = BackgroundScheduler()

def start_scheduler():
    """Start the background scheduler"""
    if not scheduler.running:
        scheduler.start()

def stop_scheduler():
    """Stop the background scheduler"""
    if scheduler.running:
        scheduler.shutdown()

def schedule_daily_quest(user_id: int, quest_time: time):
    """
    Schedule a daily quest for a user at their preferred time.
    Removes any existing daily quest job for this user.
    """
    job_id = f"daily_quest_{user_id}"
    
    # Remove any existing job for this user
    try:
        scheduler.remove_job(job_id=job_id, jobstore=None, raise_exception=False)
    except:
        pass
    
    # Schedule new daily quest job
    scheduler.add_job(
        func=generate_daily_quest_for_user,
        trigger=CronTrigger(hour=quest_time.hour, minute=quest_time.minute),
        args=[user_id],
        id=job_id,
        replace_existing=True,
        name=f"Daily Quest for User {user_id}"
    )

def generate_daily_quest_for_user(user_id: int):
    """Generate a daily quest for a specific user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        # Check if user already has a pending daily quest for today
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start.replace(hour=23, minute=59, second=59, microsecond=999999)
        
        existing_daily = db.query(Quest).filter(
            Quest.owner_id == user_id,
            Quest.quest_type == QuestType.DAILY,
            Quest.status == QuestStatus.PENDING,
            Quest.created_at >= today_start,
            Quest.created_at <= today_end
        ).first()
        
        if existing_daily:
            return  # Already has a daily quest for today
        
        # Generate daily quest using the new function
        generate_daily_quest(user_id, db)
        
    except Exception as e:
        print(f"Error generating daily quest for user {user_id}: {e}")
    finally:
        db.close()

def schedule_random_quest(user_id: int, start_hour: int, end_hour: int, quest_type: str = "hidden"):
    """
    Schedule a random quest within the user's awake window.
    
    Args:
        user_id: User ID
        start_hour: Start of awake window (0-23)
        end_hour: End of awake window (0-23)
        quest_type: Type of quest to generate
    """
    job_id = f"random_quest_{user_id}_{quest_type}"
    
    # Remove any existing random quest job for this user and type
    try:
        scheduler.remove_job(job_id=job_id, jobstore=None, raise_exception=False)
    except:
        pass
    
    # Generate random time within awake window
    random_hour = random.randint(start_hour, end_hour - 1)
    random_minute = random.randint(0, 59)
    
    # Schedule random quest
    scheduler.add_job(
        func=trigger_random_quest,
        trigger=CronTrigger(hour=random_hour, minute=random_minute),
        args=[user_id, quest_type],
        id=job_id,
        replace_existing=True,
        name=f"Random {quest_type.title()} Quest for User {user_id}"
    )

def trigger_random_quest(user_id: int, quest_type: str):
    """Trigger a random quest for a user"""
    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return
        
        # Generate quest based on type
        now = datetime.utcnow()
        if quest_type == "hidden":
            quest = Quest(
                title="Hidden Discovery",
                description="You've discovered a hidden quest!",
                quest_type=QuestType.HIDDEN,
                xp_reward=random.randint(50, 150),
                owner_id=user_id,
                status=QuestStatus.PENDING,
                created_at=now,
                earliest_acceptance=now,
                earliest_completion=now
            )
        elif quest_type == "penalty":
            quest = Quest(
                title="Penalty Challenge",
                description="You must complete this penalty quest!",
                quest_type=QuestType.PENALTY,
                xp_reward=random.randint(25, 75),
                owner_id=user_id,
                status=QuestStatus.PENDING,
                created_at=now,
                earliest_acceptance=now,
                earliest_completion=now
            )
        else:
            quest = Quest(
                title="Random Challenge",
                description="A random quest has appeared!",
                quest_type=QuestType.REGULAR,
                xp_reward=random.randint(30, 100),
                owner_id=user_id,
                status=QuestStatus.PENDING,
                created_at=now,
                earliest_acceptance=now,
                earliest_completion=now
            )
        
        db.add(quest)
        db.commit()
        
    except Exception as e:
        print(f"Error triggering random quest for user {user_id}: {e}")
    finally:
        db.close()

def trigger_penalty_quest(user_id: int, reason: str, xp_penalty: int = 50):
    """
    Immediately trigger a penalty quest for a user.
    This can be called when a user fails a quest or violates rules.
    """
    db = SessionLocal()
    try:
        now = datetime.utcnow()
        quest = Quest(
            title="Penalty Quest",
            description=f"Penalty: {reason}",
            quest_type=QuestType.PENALTY,
            xp_reward=xp_penalty,
            owner_id=user_id,
            status=QuestStatus.PENDING,
            created_at=now,
            earliest_acceptance=now,
            earliest_completion=now
        )
        
        db.add(quest)
        db.commit()
        
    except Exception as e:
        print(f"Error triggering penalty quest for user {user_id}: {e}")
    finally:
        db.close()

def update_user_schedule(user_id: int, daily_quest_time: Optional[time] = None, 
                        awake_start: Optional[int] = None, awake_end: Optional[int] = None):
    """
    Update a user's quest schedule when they change their preferences.
    
    Args:
        user_id: User ID
        daily_quest_time: New daily quest time
        awake_start: Start of awake window (0-23)
        awake_end: End of awake window (0-23)
    """
    if daily_quest_time:
        schedule_daily_quest(user_id, daily_quest_time)
    
    if awake_start is not None and awake_end is not None:
        # Reschedule random quests within new awake window
        schedule_random_quest(user_id, awake_start, awake_end, "hidden")
        schedule_random_quest(user_id, awake_start, awake_end, "penalty")

def get_user_scheduled_jobs(user_id: int):
    """Get all scheduled jobs for a user"""
    jobs = []
    for job in scheduler.get_jobs():
        if str(user_id) in job.id:
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
                "trigger": str(job.trigger)
            })
    return jobs

def remove_user_jobs(user_id: int):
    """Remove all scheduled jobs for a user (e.g., when user is deleted)"""
    jobs_to_remove = []
    for job in scheduler.get_jobs():
        if str(user_id) in job.id:
            jobs_to_remove.append(job.id)
    
    for job_id in jobs_to_remove:
        try:
            scheduler.remove_job(job_id)
        except:
            pass 