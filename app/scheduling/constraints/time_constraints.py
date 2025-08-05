"""
Time-related constraint checking functions.
"""

from datetime import datetime, timedelta
from typing import List
from ..core.time_slot import CleanTimeSlot
from ..scoring.time_scoring import calculate_time_preference_score
from app.models import Quest, SchedulingFlexibility


def is_slot_allowed(quest: Quest, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> bool:
    """
    Check if a slot is allowed for this quest based on strict rules.
    """
    # Rule 1: Check absolute deadline (hard constraint)
    if quest.deadline:
        # Calculate when the task would finish
        task_duration = timedelta(minutes=quest.duration_minutes or 60)
        task_end_time = slot.start + task_duration
        
        # If the task finishes after the absolute deadline, it's not allowed
        if task_end_time > quest.deadline:
            print(f"      ❌ Slot rejected: absolute deadline constraint (finishes at {task_end_time}, deadline {quest.deadline})")
            return False
    
    # Rule 2: Check scheduling flexibility constraints
    if hasattr(quest, 'scheduling_flexibility'):
        if quest.scheduling_flexibility == SchedulingFlexibility.FIXED:
            # FIXED tasks must be scheduled at their exact hard_start time
            if hasattr(quest, 'hard_start') and quest.hard_start:
                # Check if slot starts at the exact hard_start time
                slot_start_time = slot.start.time()
                slot_end_time = slot.end.time()
                if slot_start_time != quest.hard_start or slot_end_time != quest.hard_end:
                    print(f"      ❌ Slot rejected: FIXED scheduling constraint (slot starts at {slot_start_time}, hard_start {quest.hard_start})")
                    return False
            else:
                print(f"      ❌ Slot rejected: FIXED scheduling constraint but no hard_start specified")
                return False
        
        elif quest.scheduling_flexibility == SchedulingFlexibility.WINDOW:
            # WINDOW tasks must be within their preferred time window AND on the correct day
            
            # First, check hard time constraints (hard_start and hard_end)
            slot_start_time = slot.start.time()
            slot_end_time = slot.end.time()
            
            print(f"      🔍 WINDOW constraint check for '{quest.title}': slot {slot_start_time}-{slot_end_time}, hard {quest.hard_start}-{quest.hard_end}")
            
            if quest.hard_start and slot_start_time < quest.hard_start:
                print(f"      ❌ Slot rejected: WINDOW hard start constraint (slot starts at {slot_start_time}, hard_start {quest.hard_start})")
                return False
            
            if quest.hard_end and slot_end_time > quest.hard_end:
                print(f"      ❌ Slot rejected: WINDOW hard end constraint (slot ends at {slot_end_time}, hard_end {quest.hard_end})")
                return False
            
            # Check time preference score
            time_preference_score = calculate_time_preference_score(quest, slot)
            if time_preference_score < 0.1:  # Must be at least within hard window (0.1 score)
                print(f"      ❌ Slot rejected: WINDOW scheduling constraint (time preference score {time_preference_score} < 0.1)")
                return False
            
            # STRICT DAY CONSTRAINT: WINDOW tasks must be on their designated recurrence days
            if quest.recurrence_rule:
                # Parse the recurrence rule to get the allowed days
                try:
                    from dateutil import rrule
                    rule = rrule.rrulestr(quest.recurrence_rule, dtstart=slot.start)
                    
                    # Get the day of week for the slot
                    slot_day = slot.start.weekday()  # Monday=0, Tuesday=1, etc.
                    
                    # Convert to RRULE day format (MO=0, TU=1, etc.)
                    day_names = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
                    slot_day_name = day_names[slot_day]
                    
                    # Check if this day is allowed in the recurrence rule
                    if 'BYDAY=' in quest.recurrence_rule:
                        allowed_days = quest.recurrence_rule.split('BYDAY=')[1].split(';')[0].split(',')
                        print(f"      🔍 WINDOW day constraint check for '{quest.title}' (ID: {getattr(quest, 'id', 'None')}): slot day {slot_day_name}, recurrence rule '{quest.recurrence_rule}', allowed days {allowed_days}")
                        if slot_day_name not in allowed_days:
                            print(f"      ❌ Slot rejected: WINDOW day constraint (slot day {slot_day_name}, allowed days {allowed_days})")
                            return False
                    else:
                        print(f"      ❌ Slot rejected: WINDOW day constraint (no BYDAY in recurrence rule)")
                        return False
                        
                except Exception as e:
                    print(f"      ❌ Slot rejected: WINDOW day constraint (error parsing recurrence: {e})")
                    return False
        
        elif quest.scheduling_flexibility == SchedulingFlexibility.STRICT:
            # STRICT tasks must stay on the same day as their designated date
            # This is handled by the recurrence service expanding them correctly
            pass
    
    # Rule 3: Check time preference for non-constrained tasks (hard limit)
    if not hasattr(quest, 'scheduling_flexibility') or quest.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
        time_preference_score = calculate_time_preference_score(quest, slot)
        if time_preference_score < 0:  # Negative score means disqualified
            print(f"      ❌ Slot rejected: time preference score {time_preference_score} < 0")
            return False
    
    # Rule 4: Check for same-day recurring tasks (unless allowed)
    if not is_same_day_recurring_allowed(quest, slot, slots):
        print(f"      ❌ Slot rejected: same-day recurring constraint")
        return False
    
    return True


def is_same_day_recurring_allowed(quest: Quest, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> bool:
    """
    Check if a recurring task can be scheduled on the same day as another instance.
    Returns True if allowed, False if not allowed.
    """
    # If explicitly allowed, return True
    if hasattr(quest, 'allow_same_day_recurring') and quest.allow_same_day_recurring:
        return True
    
    # Check if there are other instances of the same task on the same day
    slot_date = slot.start.date()
    for s in slots:
        if (s.occupant and 
            hasattr(s.occupant, 'id') and  # Check if it's a Quest object
            s.occupant.id != quest.id and 
            hasattr(s.occupant, 'title') and  # Check if it has a title
            s.occupant.title == quest.title and
            s.start.date() == slot_date):
            return False  # Same task already scheduled on this day
    
    return True


def should_allow_time_deviation(quest: Quest) -> bool:
    """
    Determine if a quest should allow time deviation from preferred time.
    """
    # Check if explicitly set
    if hasattr(quest, 'allow_time_deviation'):
        return quest.allow_time_deviation
    
    # Default based on scheduling flexibility
    if hasattr(quest, 'scheduling_flexibility'):
        if quest.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
            return True
        elif quest.scheduling_flexibility == SchedulingFlexibility.STRICT:
            return False
        elif quest.scheduling_flexibility == SchedulingFlexibility.WINDOW:
            return False
        elif quest.scheduling_flexibility == SchedulingFlexibility.FIXED:
            return False
    
    # Default to False for safety
    return False 