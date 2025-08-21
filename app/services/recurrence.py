"""
Recurrence utilities using dateutil.rrule for handling RRULE patterns
RRULE is the primary engine for all recurrence patterns (RFC 5545 standard)
"""

from datetime import datetime, timedelta
from typing import List, Optional
from dateutil import rrule
from app.models import Quest, SchedulingFlexibility
from sqlalchemy.orm import Session


def expand_recurring_quest(quest: Quest, start_date: datetime, end_date: datetime) -> List[Quest]:
    """
    Expand a recurring quest into multiple instances using RRULE
    
    Args:
        quest: The quest to expand
        start_date: Start date for expansion
        end_date: End date for expansion
    
    Returns:
        List of Quest instances
    """
    # If no recurrence rule, return the quest as-is if it falls within the date range
    if not quest.recurrence_rule:
        # For non-recurring tasks, check if they fall within the date range
        # This would be based on their deadline or other date fields
        return [quest]
    
    try:
        # Parse RRULE string using dateutil
        rule = rrule.rrulestr(quest.recurrence_rule, dtstart=start_date)
        
        # Get all occurrences between start_date and end_date
        occurrences = rule.between(start_date, end_date, inc=True)
        
        instances = []
        for i, occurrence in enumerate(occurrences):
            instance = create_quest_instance(quest, occurrence, i + 1)
            instances.append(instance)
        
        return instances
        
    except Exception as e:
        print(f"RRULE parsing failed: {e}")
        # If RRULE parsing fails, return empty list
        return []


def create_quest_instance(quest: Quest, occurrence_date: datetime, instance_number: int) -> Quest:
    """
    Create a quest instance from a recurring quest
    
    Note: The scheduling_flexibility field is preserved from the original quest.
    - FIXED: Cannot be moved at all
    - STRICT: Cannot be moved to different days, but can move time within same day
    - WINDOW: Must be within preferred time window
    - FLEXIBLE: Can be moved anywhere
    """
    # Create a unique, in-memory id for the instance to avoid collisions during scheduling
    # Use a negative composite id so it won't collide with DB-generated positives
    if getattr(quest, 'id', None) is not None:
        instance_id = -(quest.id * 10000 + instance_number)
    else:
        instance_id = -instance_number

    return Quest(
        id=instance_id,
        title=quest.title,
        description=quest.description,
        xp_reward=quest.xp_reward,
        quest_type=quest.quest_type,
        difficulty=quest.difficulty,
        owner_id=quest.owner_id,
        theme_tags=quest.theme_tags,
        
        # Scheduling fields
        priority=quest.priority,
        # For FIXED events, use occurrence_date as deadline (needed for scheduling)
        # For other events, preserve original deadline (None for gym workouts)
        deadline=occurrence_date if quest.scheduling_flexibility == SchedulingFlexibility.FIXED else quest.deadline,
        preferred_time_of_day=quest.preferred_time_of_day,
        duration_minutes=quest.duration_minutes,
        
        # Chunking fields
        chunk_index=quest.chunk_index,
        chunk_count=quest.chunk_count,
        is_chunked=quest.is_chunked,
        base_title=quest.base_title,
        
        # Recurrence field (preserve for day constraint checking)
        recurrence_rule=quest.recurrence_rule,
        recurrence_parent_id=getattr(quest, 'id', None),
        
        # Buffer fields
        buffer_before=quest.buffer_before,
        buffer_after=quest.buffer_after,
        
        # Scheduling flexibility
        scheduling_flexibility=quest.scheduling_flexibility,
        
        # Time window constraints
        expected_start=quest.expected_start,
        expected_end=quest.expected_end,
        soft_start=quest.soft_start,
        soft_end=quest.soft_end,
        hard_start=quest.hard_start,
        hard_end=quest.hard_end,
        
        # Status
        status=quest.status,
        sent_out_at=quest.sent_out_at,
        time_limit_minutes=quest.time_limit_minutes,
        repeatable=False,
        is_main_daily_quest=quest.is_main_daily_quest,
        template_id=quest.template_id
    )


# --- Sync utilities ---

# Fields that are safe/useful to sync from the parent to all recurrence children.
_DEFAULT_SYNC_FIELDS = [
    # Presentation / meta
    "title",
    "description",
    "xp_reward",
    "theme_tags",
    # Scheduling core
    "priority",
    "preferred_time_of_day",
    "duration_minutes",
    "buffer_before",
    "buffer_after",
    "scheduling_flexibility",
    # Time windows
    "expected_start",
    "expected_end",
    "soft_start",
    "soft_end",
    "hard_start",
    "hard_end",
    # Overrides
    "allow_time_deviation",
    "allow_urgent_override",
    "allow_same_day_recurring",
]


def sync_recurrence_children(
    db: Session,
    parent_quest: Quest,
    fields: list[str] | None = None,
    exclude_fields: list[str] | None = None,
) -> int:
    """
    Sync selected fields from a parent quest (series definition) to all of its
    recurrence children (instances) in the database.

    Returns the number of children updated.

    Notes:
    - This does NOT change child-specific state like status/completion timestamps.
    - If you changed the RRULE, consider re-expanding (delete & regenerate children)
      rather than syncing, since day/time semantics may differ.
    """
    fields_to_sync = set(fields or _DEFAULT_SYNC_FIELDS)
    if exclude_fields:
        fields_to_sync.difference_update(exclude_fields)

    # Never sync these identifiers/state fields
    forbidden = {
        "id",
        "owner_id",
        "recurrence_parent_id",
        "parent_quest_id",
        "status",
        "completed_at",
        "sent_out_at",
        "is_main_daily_quest",
        "chunk_index",
        "chunk_count",
        "is_chunked",
        "base_title",
        "chunk_duration_minutes",
        "chunk_preference",
        "chunk_size_preference",
        "chunk_strategy",
        "deadline",  # children may have their own computed deadlines (e.g., FIXED)
    }
    fields_to_sync.difference_update(forbidden)

    children: list[Quest] = (
        db.query(Quest).filter(Quest.recurrence_parent_id == parent_quest.id).all()
    )

    for child in children:
        for attr in fields_to_sync:
            if hasattr(parent_quest, attr):
                setattr(child, attr, getattr(parent_quest, attr))

    if children:
        db.commit()

    return len(children)


# Convenience functions for common RRULE patterns
def create_daily_rrule(interval: int = 1, count: Optional[int] = None, until: Optional[datetime] = None) -> str:
    """Create RRULE for daily recurrence"""
    return create_rrule_string("DAILY", interval=interval, count=count, until=until)


def create_weekly_rrule(byday: Optional[List[str]] = None, interval: int = 1, count: Optional[int] = None, until: Optional[datetime] = None) -> str:
    """Create RRULE for weekly recurrence"""
    return create_rrule_string("WEEKLY", interval=interval, count=count, until=until, byday=byday)


def create_monthly_rrule(bymonthday: Optional[List[int]] = None, interval: int = 1, count: Optional[int] = None, until: Optional[datetime] = None) -> str:
    """Create RRULE for monthly recurrence"""
    return create_rrule_string("MONTHLY", interval=interval, count=count, until=until, bymonthday=bymonthday)


def create_rrule_string(freq: str, interval: int = 1, count: Optional[int] = None, 
                       until: Optional[datetime] = None, byday: Optional[List[str]] = None,
                       bymonthday: Optional[List[int]] = None, bymonth: Optional[List[int]] = None) -> str:
    """
    Create an RRULE string for any pattern
    
    Examples:
        create_rrule_string("DAILY", interval=3)  # Every 3 days
        create_rrule_string("WEEKLY", byday=["MO", "WE", "FR"])  # Mon, Wed, Fri
        create_rrule_string("MONTHLY", bymonthday=[1, 15])  # 1st and 15th of month
        create_rrule_string("DAILY", count=10)  # Daily for 10 occurrences
        create_rrule_string("WEEKLY", until=datetime(2024, 12, 31))  # Weekly until Dec 31, 2024
    """
    parts = [f"FREQ={freq}"]
    
    if interval > 1:
        parts.append(f"INTERVAL={interval}")
    
    if count:
        parts.append(f"COUNT={count}")
    
    if until:
        parts.append(f"UNTIL={until.strftime('%Y%m%dT%H%M%SZ')}")
    
    if byday:
        parts.append(f"BYDAY={','.join(byday)}")
    
    if bymonthday:
        parts.append(f"BYMONTHDAY={','.join(map(str, bymonthday))}")
    
    if bymonth:
        parts.append(f"BYMONTH={','.join(map(str, bymonth))}")
    
    return ";".join(parts)


# Common RRULE patterns for easy use
COMMON_RRULES = {
    "daily": "FREQ=DAILY",
    "weekly": "FREQ=WEEKLY",
    "monthly": "FREQ=MONTHLY",
    "weekdays": "FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR",
    "weekends": "FREQ=WEEKLY;BYDAY=SA,SU",
    "monday_wednesday_friday": "FREQ=WEEKLY;BYDAY=MO,WE,FR",
    "first_of_month": "FREQ=MONTHLY;BYMONTHDAY=1",
    "fifteenth_of_month": "FREQ=MONTHLY;BYMONTHDAY=15",
    "first_and_fifteenth": "FREQ=MONTHLY;BYMONTHDAY=1,15",
    "every_three_days": "FREQ=DAILY;INTERVAL=3",
    "every_two_weeks": "FREQ=WEEKLY;INTERVAL=2",
    "every_three_months": "FREQ=MONTHLY;INTERVAL=3",
}


def can_move_quest_to_day(quest: Quest, target_day: datetime) -> bool:
    """
    Check if a quest can be moved to a different day based on its scheduling flexibility
    
    Args:
        quest: The quest to check
        target_day: The target day to move to
        
    Returns:
        bool: True if the quest can be moved, False if it cannot be moved
    """
    if not hasattr(quest, 'scheduling_flexibility'):
        # Default to flexible if no scheduling flexibility specified
        return True
    
    if quest.scheduling_flexibility == SchedulingFlexibility.FIXED:
        # FIXED quests cannot be moved at all
        return False
    elif quest.scheduling_flexibility == SchedulingFlexibility.STRICT:
        # STRICT quests cannot be moved to different days
        return False
    elif quest.scheduling_flexibility == SchedulingFlexibility.WINDOW:
        # WINDOW quests can be moved to any day but must stay within time window
        return True
    elif quest.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
        # FLEXIBLE quests can be moved anywhere
        return True
    else:
        # Default to flexible
        return True


def get_quest_time_constraints(quest: Quest) -> dict:
    """
    Get the time constraints for a quest in a format useful for AI scheduling
    
    Args:
        quest: The quest to analyze
        
    Returns:
        dict: Time constraints with the following structure:
        {
            "soft_start": time(9, 0),      # Preferred start time
            "soft_end": time(17, 0),       # Preferred end time  
            "hard_start": time(8, 0),      # Must start after this time
            "hard_end": time(18, 0),       # Must end before this time
            "duration_minutes": 60,         # Quest duration
            "buffer_before": 15,           # Buffer before quest
            "buffer_after": 15,            # Buffer after quest
            "total_duration_minutes": 90   # Quest + buffers
        }
    """
    from datetime import time
    
    constraints = {
        "soft_start": quest.soft_start,
        "soft_end": quest.soft_end,
        "hard_start": quest.hard_start,
        "hard_end": quest.hard_end,
        "duration_minutes": quest.duration_minutes or 60,
        "buffer_before": quest.buffer_before or 0,
        "buffer_after": quest.buffer_after or 0,
    }
    
    # Calculate total duration including buffers
    total_duration = (quest.duration_minutes or 60) + (quest.buffer_before or 0) + (quest.buffer_after or 0)
    constraints["total_duration_minutes"] = total_duration
    
    return constraints


def is_time_within_constraints(quest: Quest, start_time: datetime, end_time: datetime) -> dict:
    """
    Check if a proposed time slot fits within the quest's time constraints
    
    Args:
        quest: The quest to check
        start_time: Proposed start time
        end_time: Proposed end time
        
    Returns:
        dict: Result with constraints check:
        {
            "fits_hard_constraints": bool,  # Must be True for scheduling
            "fits_soft_constraints": bool,  # Preferred but not required
            "violations": list,             # List of constraint violations
            "score": float                  # 0.0 to 1.0 score for soft constraints
        }
    """
    from datetime import time
    
    result = {
        "fits_hard_constraints": True,
        "fits_soft_constraints": True,
        "violations": [],
        "score": 1.0
    }
    
    start_time_of_day = start_time.time()
    end_time_of_day = end_time.time()
    
    # Check hard constraints (must be satisfied)
    if quest.hard_start and start_time_of_day < quest.hard_start:
        result["fits_hard_constraints"] = False
        result["violations"].append(f"Start time {start_time_of_day} is before hard start {quest.hard_start}")
    
    if quest.hard_end and end_time_of_day > quest.hard_end:
        result["fits_hard_constraints"] = False
        result["violations"].append(f"End time {end_time_of_day} is after hard end {quest.hard_end}")
    
    # Check soft constraints (preferred but not required)
    soft_violations = 0
    total_soft_checks = 0
    
    if quest.soft_start:
        total_soft_checks += 1
        if start_time_of_day < quest.soft_start:
            result["fits_soft_constraints"] = False
            soft_violations += 1
    
    if quest.soft_end:
        total_soft_checks += 1
        if end_time_of_day > quest.soft_end:
            result["fits_soft_constraints"] = False
            soft_violations += 1
    
    # Calculate score based on soft constraint violations
    if total_soft_checks > 0:
        result["score"] = 1.0 - (soft_violations / total_soft_checks)
    
    return result 