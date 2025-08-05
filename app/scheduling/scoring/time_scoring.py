"""
Time-based scoring functions for slot evaluation.
"""

from datetime import datetime, time
from typing import Optional
from ..core.time_slot import CleanTimeSlot
from app.models import Quest, SchedulingFlexibility, PreferredTimeOfDay


def calculate_time_preference_score(quest: Quest, slot: CleanTimeSlot) -> float:
    """
    Calculate score for time preferences with 3-tier scoring system:
    1. Expected window (highest score): exact expected_start to expected_end
    2. Soft window (medium score): soft_start to soft_end  
    3. Hard window (low score): hard_start to hard_end
    4. Outside hard window: reject (0.0)
    
    Also considers preferred_time_of_day as a separate scoring component.
    """
    slot_start_time = slot.start.time()
    slot_end_time = slot.end.time()
    
    # Convert times to minutes for easier comparison
    slot_start_minutes = slot_start_time.hour * 60 + slot_start_time.minute
    slot_end_minutes = slot_end_time.hour * 60 + slot_end_time.minute
    
    # Handle FIXED flexibility with hard_start and hard_end constraints
    if quest.scheduling_flexibility == SchedulingFlexibility.FIXED:
        if quest.hard_start and quest.hard_end:
            # Check if slot exactly matches the hard_start and hard_end times
            if slot_start_time == quest.hard_start and slot_end_time == quest.hard_end:
                return 1.0  # Perfect score for exact match
            else:
                return 0.0  # Reject if not exact match
    
    # 3-tier time window scoring system
    time_window_score = 0.0
    
    # Check if we have any time window constraints
    has_time_constraints = (quest.expected_start or quest.expected_end or 
                          quest.soft_start or quest.soft_end or 
                          quest.hard_start or quest.hard_end)
    
    if has_time_constraints:
        # Convert constraint times to minutes
        expected_start_minutes = (quest.expected_start.hour * 60 + quest.expected_start.minute) if quest.expected_start else None
        expected_end_minutes = (quest.expected_end.hour * 60 + quest.expected_end.minute) if quest.expected_end else None
        soft_start_minutes = (quest.soft_start.hour * 60 + quest.soft_start.minute) if quest.soft_start else None
        soft_end_minutes = (quest.soft_end.hour * 60 + quest.soft_end.minute) if quest.soft_end else None
        hard_start_minutes = (quest.hard_start.hour * 60 + quest.hard_start.minute) if quest.hard_start else None
        hard_end_minutes = (quest.hard_end.hour * 60 + quest.hard_end.minute) if quest.hard_end else None
        
        # Check if slot is within hard window (must pass this)
        if hard_start_minutes is not None and slot_start_minutes < hard_start_minutes:
            return 0.0  # Reject - starts too early
        if hard_end_minutes is not None and slot_end_minutes > hard_end_minutes:
            return 0.0  # Reject - ends too late
        
        # 3-tier scoring - check BOTH start and end times
        if (expected_start_minutes is not None and expected_end_minutes is not None and
            slot_start_minutes >= expected_start_minutes and slot_end_minutes <= expected_end_minutes):
            time_window_score = 100.0  # ⭐⭐⭐ Perfect - within expected window
        elif (soft_start_minutes is not None and soft_end_minutes is not None and
              slot_start_minutes >= soft_start_minutes and slot_end_minutes <= soft_end_minutes):
            time_window_score = 0.5  # ⭐⭐ Good - within soft window
        elif (hard_start_minutes is not None and hard_end_minutes is not None and
              slot_start_minutes >= hard_start_minutes and slot_end_minutes <= hard_end_minutes):
            time_window_score = 0.1  # ⭐ Acceptable - within hard window
        else:
            time_window_score = 0.0  # ❌ Reject - outside all windows
    
    # Handle WINDOW flexibility - must have time window constraints
    if quest.scheduling_flexibility == SchedulingFlexibility.WINDOW:
        if not has_time_constraints:
            return 0.0  # WINDOW tasks must have time constraints
        print(f"      🎯 TIME PREFERENCE: '{quest.title}' slot {slot.start.time()}-{slot.end.time()} = {time_window_score}")
        print(f"         📊 DEBUG: expected={expected_start_minutes}-{expected_end_minutes}, soft={soft_start_minutes}-{soft_end_minutes}, hard={hard_start_minutes}-{hard_end_minutes}")
        print(f"         📊 DEBUG: slot_start={slot_start_minutes}, slot_end={slot_end_minutes}")
        return time_window_score  # Use the 3-tier score directly
    
    # For other flexibility types, combine time window score with time of day preference
    time_of_day_score = 0.5  # Default neutral score
    
    if quest.preferred_time_of_day and quest.preferred_time_of_day != PreferredTimeOfDay.NO_PREFERENCE:
        slot_start_hour = slot.start.hour
        
        # Check if we should allow deviation from preferred time
        allow_deviation = quest.allow_time_deviation or quest.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE
        
        if quest.preferred_time_of_day == PreferredTimeOfDay.MORNING:
            if 6 <= slot_start_hour < 12:
                time_of_day_score = 1.0
            elif allow_deviation and (5 <= slot_start_hour < 14):
                time_of_day_score = 0.7
            else:
                time_of_day_score = 0.3
        elif quest.preferred_time_of_day == PreferredTimeOfDay.AFTERNOON:
            if 12 <= slot_start_hour < 18:
                time_of_day_score = 1.0
            elif allow_deviation and (10 <= slot_start_hour < 20):
                time_of_day_score = 0.7
            else:
                time_of_day_score = 0.3
        elif quest.preferred_time_of_day == PreferredTimeOfDay.EVENING:
            if 18 <= slot_start_hour < 23:
                time_of_day_score = 1.0
            elif allow_deviation and (16 <= slot_start_hour < 24):
                time_of_day_score = 0.7
            else:
                time_of_day_score = 0.3
    
    # Combine scores: if we have time window constraints, prioritize them
    if has_time_constraints:
        return time_window_score
    else:
        return time_of_day_score


def calculate_earlier_bonus(quest: Quest, slot: CleanTimeSlot) -> float:
    """
    Calculate bonus for scheduling tasks earlier in the day.
    Only applies to tasks with deadlines.
    """
    if not quest.deadline:
        return 0.0  # No deadline, no early bonus
    
    # Calculate how many days until deadline
    days_until_deadline = (quest.deadline.date() - slot.start.date()).days
    
    if days_until_deadline <= 0:
        return 0.0  # Already at or past deadline
    
    # Bonus decreases as we get closer to deadline
    # More bonus for scheduling earlier when deadline is far away
    if days_until_deadline >= 7:
        return 0.1  # Small bonus for scheduling early when deadline is far
    elif days_until_deadline >= 3:
        return 0.05  # Smaller bonus for medium-term deadlines
    else:
        return 0.0  # No bonus when deadline is close


def calculate_urgency_score(quest: Quest, slot: CleanTimeSlot) -> float:
    """
    Calculate urgency score based on deadline proximity.
    """
    if not quest.deadline:
        return 0.0  # No deadline, no urgency
    
    # Calculate how many days until deadline
    days_until_deadline = (quest.deadline.date() - slot.start.date()).days
    
    if days_until_deadline <= 0:
        return 10.0  # High urgency - deadline passed or today
    elif days_until_deadline == 1:
        return 5.0   # Very high urgency - tomorrow
    elif days_until_deadline <= 3:
        return 2.0   # High urgency - within 3 days
    elif days_until_deadline <= 7:
        return 1.0   # Medium urgency - within a week
    else:
        return 0.5   # Low urgency - more than a week away 