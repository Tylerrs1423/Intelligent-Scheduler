"""
Persistent scheduler service that maintains user schedulers in memory.
"""

from datetime import datetime, timedelta, time
from typing import Dict, Optional
from sqlalchemy.orm import Session
from ..scheduling.core.scheduler import CleanScheduler
from ..models import User, Event, SchedulingFlexibility
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
    
    def get_or_create_scheduler(self, user_id: int, db: Session) -> Optional[CleanScheduler]:
        """Get existing scheduler or create new one for user."""
        if user_id not in self.user_schedulers:
            # Get user sleep preferences
            user = db.query(User).filter(User.id == user_id).first()
            if not user or not user.sleep_start or not user.sleep_end:
                return None  # User must set sleep preferences first
            
            self._create_scheduler_for_user(user_id, user.sleep_start, user.sleep_end, db)
        
        return self.user_schedulers[user_id]
    
    def _create_scheduler_for_user(self, user_id: int, sleep_start: time, sleep_end: time, db: Session):
        """Create scheduler for user with sleep preferences."""
        # Create scheduler with default window
        window_start = datetime.utcnow()
        window_end = window_start + timedelta(days=self.default_window_days)
        
        scheduler = CleanScheduler(
            window_start=window_start,
            window_end=window_end,
            user_sleep_start=sleep_start,
            user_sleep_end=sleep_end
        )
        
        # Load existing events
        scheduler.load_fixed_events(db)
        
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
        """Add event to user's scheduler."""
        scheduler = self.get_or_create_scheduler(user_id, db)
        if not scheduler:
            return False  # User needs to set sleep preferences first
        
        # Convert Event to Quest-like object for scheduler
        from ..models import Quest, QuestStatus, QuestCategory, QuestType, QuestDifficulty
        
        quest = Quest(
            title=event.title,
            description=event.description,
            status=QuestStatus.PENDING,
            category=QuestCategory.WORK,
            quest_type=QuestType.SINGLE,
            difficulty=QuestDifficulty.MEDIUM,
            priority=event.priority,
            buffer_before=event.buffer_before,
            buffer_after=event.buffer_after,
            user_id=user_id
        )
        
        # Schedule the event
        duration = event.end_time - event.start_time
        
        if event.scheduling_flexibility == SchedulingFlexibility.FIXED:
            scheduled_slots = scheduler.schedule_task_at_exact_time(
                quest, event.start_time, duration, event.end_time
            )
        else:
            scheduled_slots = scheduler.schedule_task_with_buffers(quest, duration)
        
        return len(scheduled_slots) > 0
    
    def get_scheduler_slots(self, user_id: int, db: Session) -> Optional[list]:
        """Get all slots from user's scheduler."""
        scheduler = self.get_or_create_scheduler(user_id, db)
        if not scheduler:
            return None
        return scheduler.slots
    
    def remove_scheduler(self, user_id: int):
        """Remove user's scheduler from memory."""
        if user_id in self.user_schedulers:
            del self.user_schedulers[user_id]

# Global scheduler service instance
scheduler_service = SchedulerService()
