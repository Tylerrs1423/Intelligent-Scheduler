"""
Persistent scheduler service that maintains user schedulers in memory.
"""

from datetime import datetime, timedelta, time
from typing import Dict, Optional
from sqlalchemy.orm import Session
from ..models import User, Event, SchedulingFlexibility
from ..scheduling.core.scheduler import CleanScheduler
from ..scheduling.core.time_slot import CleanTimeSlot
from ..database import get_db

class SchedulerService:
    """Service to manage persistent schedulers for users."""
    
    def __init__(self):
        # In-memory storage of user schedulers
        self.user_schedulers: Dict[int, CleanScheduler] = {}
        # Default scheduling window (can be configurable)
        self.default_window_days = 30
    
    def initialize_all_schedulers(self, db: Session):
        """Initialize schedulers for all users on startup."""
        users = db.query(User).all()
        for user in users:
            if user.sleep_start and user.sleep_end:
                self._create_scheduler_for_user(user.id, user.sleep_start, user.sleep_end, db)
    
    def get_scheduler(self, user_id: int) -> Optional[CleanScheduler]:
        """Get existing scheduler for user without creating one."""
        return self.user_schedulers.get(user_id)
    
    def get_or_create_scheduler(self, user_id: int, db: Session) -> Optional[CleanScheduler]:
        """Get existing scheduler or create new one for user."""
        print(f"🔍 SCHEDULER DEBUG: get_or_create_scheduler called for user_id={user_id}")
        print(f"🔍 SCHEDULER DEBUG: Current user_schedulers keys: {list(self.user_schedulers.keys())}")
        print(f"🔍 SCHEDULER DEBUG: Scheduler service instance id: {id(self)}")
        
        if user_id not in self.user_schedulers:
            print(f"🔍 SCHEDULER DEBUG: Creating new scheduler for user_id={user_id}")
            # Get user sleep preferences
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.sleep_start or not user.sleep_end:
                print(f"🔍 SCHEDULER DEBUG: User {user_id} has no sleep preferences")
                return None  # User must set sleep preferences first
            
            self._create_scheduler_for_user(user_id, user.sleep_start, user.sleep_end, db)
            print(f"🔍 SCHEDULER DEBUG: Created scheduler for user_id={user_id}")
        else:
            print(f"🔍 SCHEDULER DEBUG: Using existing scheduler for user_id={user_id}")
        
        return self.user_schedulers[user_id]
    
    def _create_scheduler_for_user(self, user_id: int, sleep_start: time, sleep_end: time, db: Session):
        """Create scheduler for user with sleep preferences."""
        # Create scheduler with 14-day window from start of current week
        now = datetime.utcnow()
        # Start from beginning of current week (Sunday)
        days_since_sunday = now.weekday() + 1  # Monday=0, so Sunday=6, add 1 to get days since Sunday
        window_start = now - timedelta(days=days_since_sunday)
        window_start = window_start.replace(hour=0, minute=0, second=0, microsecond=0)
        # End 14 days from start of week
        window_end = window_start + timedelta(days=14)
        
        scheduler = CleanScheduler(
            window_start=window_start,
            window_end=window_end,
            user_sleep_start=sleep_start,
            user_sleep_end=sleep_end
        )
        
        # Load existing events using the scheduler's built-in method
        scheduler.load_fixed_events(db, user_id)
        
        self.user_schedulers[user_id] = scheduler
    
    
    def update_sleep_preferences(self, user_id: int, sleep_start: time, sleep_end: time, db: Session):
        """Update user sleep preferences and recreate scheduler."""
        # Update user in database
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.sleep_start = sleep_start
            user.sleep_end = sleep_end
            db.commit()
        
        # Recreate scheduler with new sleep preferences
        if user_id in self.user_schedulers:
            del self.user_schedulers[user_id]
        
        # Create new scheduler
        self._create_scheduler_for_user(user_id, sleep_start, sleep_end, db)
    
    def add_event_to_scheduler(self, user_id: int, event: Event, db: Session) -> bool:
        """Add event to user's scheduler using the existing CleanScheduler logic."""
        print(f"🔍 EVENT DEBUG: add_event_to_scheduler called for user_id={user_id}, event_id={event.id}")
        print(f"🔍 EVENT DEBUG: Scheduler service instance id: {id(self)}")
        print(f"🔍 EVENT DEBUG: Current user_schedulers keys: {list(self.user_schedulers.keys())}")
        
        scheduler = self.get_or_create_scheduler(user_id, db)
        if not scheduler:
            print(f"🔍 EVENT DEBUG: No scheduler found for user_id={user_id}")
            return False  # User needs to set sleep preferences first
        
        # Create a scheduling object with default preferences + event data
        class SchedulingObject:
            def __init__(self, event):
                # Event data
                self.id = event.id
                self.title = event.title
                self.description = event.description
                self.priority = event.priority
                self.buffer_before = event.buffer_before or 0
                self.buffer_after = event.buffer_after or 0
                self.scheduling_flexibility = event.scheduling_flexibility
                
                # Default scheduling preferences (can be made configurable later)
                self.preferred_time_of_day = "no_preference"
                self.allow_time_deviation = True
                self.allow_urgent_override = False
                self.allow_same_day_recurring = False
                self.deadline = None
                # For flexible events, duration should be provided
                # For fixed events, we can calculate from start/end times
                if event.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
                    # Flexible events should have duration specified
                    self.duration_minutes = event.min_duration or 60  # Default to 1 hour if not specified
                else:
                    # Fixed events can calculate duration from start/end times
                    duration = event.end_time - event.start_time
                    self.duration_minutes = int(duration.total_seconds() / 60)
                
                # Additional attributes that scoring functions expect
                self.expected_start = None
                self.expected_end = None
                self.soft_start = event.soft_start
                self.soft_end = event.soft_end
                self.hard_start = event.hard_start
                self.hard_end = event.hard_end
                self.allowed_days = event.allowed_days
                self.min_duration = event.min_duration
                self.max_duration = event.max_duration
                self.difficulty = None  # Events don't have difficulty
                self.recurrence_rule = event.recurrence_rule
        
        scheduling_obj = SchedulingObject(event)
        duration = event.end_time - event.start_time
        
        # Use the existing scheduler logic
        print(f"🔍 SCHEDULING DEBUG: Attempting to schedule event with flexibility={event.scheduling_flexibility}")
        print(f"🔍 SCHEDULING DEBUG: Event time: {event.start_time} to {event.end_time}")
        print(f"🔍 SCHEDULING DEBUG: Duration: {duration}")
        
        if event.scheduling_flexibility == SchedulingFlexibility.FIXED:
            # For fixed events, try to schedule at exact time
            print(f"🔍 SCHEDULING DEBUG: Using fixed scheduling")
            scheduled_slots = scheduler.schedule_task_at_exact_time(
                scheduling_obj, event.start_time, duration, event.end_time
            )
        else:
            # For flexible events, let scheduler find optimal time
            print(f"🔍 SCHEDULING DEBUG: Using flexible scheduling")
            scheduled_slots = scheduler.schedule_task_with_buffers(scheduling_obj, duration)
        
        success = len(scheduled_slots) > 0
        print(f"🔍 SCHEDULING DEBUG: Scheduling result: {success}, scheduled_slots count: {len(scheduled_slots)}")
        
        if success:
            print(f"🔍 SCHEDULING DEBUG: Event successfully scheduled!")
            # Let's also check how many slots we have now
            print(f"🔍 SCHEDULING DEBUG: Total slots after scheduling: {len(scheduler.slots)}")
        else:
            print(f"🔍 SCHEDULING DEBUG: Event scheduling failed!")
        
        return success
    
    def get_scheduler_slots(self, user_id: int, db: Session) -> Optional[list]:
        """Get all slots from user's scheduler."""
        scheduler = self.get_scheduler(user_id)
        if not scheduler:
            # Try to create one if it doesn't exist
            scheduler = self.get_or_create_scheduler(user_id, db)
            if not scheduler:
                return None
        return scheduler.slots
    
    def remove_scheduler(self, user_id: int):
        """Remove user's scheduler from memory."""
        if user_id in self.user_schedulers:
            del self.user_schedulers[user_id]
    
    def refresh_scheduler(self, user_id: int, db: Session):
        """Refresh scheduler by recreating it and loading existing events."""
        print(f"🔍 REFRESH DEBUG: Refreshing scheduler for user {user_id}")
        if user_id in self.user_schedulers:
            del self.user_schedulers[user_id]
        
        # Recreate scheduler
        scheduler = self.get_or_create_scheduler(user_id, db)
        return scheduler
    

# Global scheduler service instance
scheduler_service = SchedulerService()
