"""
Workload-based scoring functions for slot evaluation.
"""

from datetime import datetime, timedelta
from typing import List
from ..core.time_slot import CleanTimeSlot


def calculate_daily_workload_bonus(schedulable_object, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate bonus for respecting daily workload limits.
    Hard limit: Cannot exceed daily maximum.
    """
    slot_date = slot.start.date()
    
    # Calculate current daily workload
    daily_workload_hours = 0
    for s in slots:
        if (s.occupant and 
            hasattr(s.occupant, 'id') and  # Check if it's a Quest object
            s.occupant.id != schedulable_object.id and
            s.start.date() == slot_date):
            # Add task duration to daily workload
            if hasattr(s.occupant, 'duration_minutes') and s.occupant.duration_minutes:
                daily_workload_hours += s.occupant.duration_minutes / 60
            else:
                daily_workload_hours += s.duration().total_seconds() / 3600
    
    # Add current task duration
    schedulable_object_duration_hours = schedulable_object.duration_minutes / 60 if schedulable_object.duration_minutes else 1
    
    # Hard daily limit: 8 hours of focused work per day
    daily_limit_hours = 8.0
    
    # HARD LIMIT: Cannot exceed daily maximum
    if daily_workload_hours + schedulable_object_duration_hours > daily_limit_hours:
        return -1000.0  # Very strong penalty - effectively disqualifies the slot
    
    # Bonus for staying well under the limit
    if daily_workload_hours + schedulable_object_duration_hours <= daily_limit_hours * 0.8:  # Under 80% of limit
        return 0.2  # Small bonus for not overloading the day
    else:
        return 0.0  # Neutral score when approaching the limit


def calculate_weekly_balance_score(schedulable_object, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate weekly balance score: encourage placing tasks on days with lower difficulty and workload.
    Looks at the full Monday-Sunday week, not just current day forward.
    """
    slot_date = slot.start.date()
    
    # Find the Monday of the current week (always start from Monday)
    week_start = slot_date - timedelta(days=slot_date.weekday())
    week_end = week_start + timedelta(days=7)
    
    # Calculate workload and difficulty for each day of the week
    weekly_scores = {}
    for i in range(7):
        day_date = week_start + timedelta(days=i)
        weekly_scores[day_date] = {
            'workload_hours': 0,
            'difficulty_score': 0,
            'task_count': 0
        }
    
    # Add existing tasks to weekly scores
    for s in slots:
        if (s.occupant and 
            hasattr(s.occupant, 'id') and
            s.occupant.id != schedulable_object.id and
            week_start <= s.start.date() < week_end):
            
            day_date = s.start.date()
            
            # Add workload hours
            if hasattr(s.occupant, 'duration_minutes') and s.occupant.duration_minutes:
                weekly_scores[day_date]['workload_hours'] += s.occupant.duration_minutes / 60
            else:
                weekly_scores[day_date]['workload_hours'] += s.duration().total_seconds() / 3600
            
            # Add difficulty score (using actual difficulty field)
            if hasattr(s.occupant, 'difficulty'):
                # Convert QuestDifficulty enum to numeric score
                difficulty_value = get_schedulable_object_difficulty_score(s.occupant)
                weekly_scores[day_date]['difficulty_score'] += difficulty_value
            
            weekly_scores[day_date]['task_count'] += 1
    
    # Add current task to the target day
    schedulable_object_duration_hours = schedulable_object.duration_minutes / 60 if schedulable_object.duration_minutes else 1
    weekly_scores[slot_date]['workload_hours'] += schedulable_object_duration_hours
    weekly_scores[slot_date]['difficulty_score'] += get_schedulable_object_difficulty_score(schedulable_object)
    weekly_scores[slot_date]['task_count'] += 1
    
    # Calculate combined score for each day (lower = better)
    day_scores = {}
    for day_date, data in weekly_scores.items():
        # Normalize workload (0-8 hours = 0-1 score)
        workload_score = min(data['workload_hours'] / 8.0, 1.0)
        
        # Normalize difficulty (0-20 difficulty = 0-1 score, assuming max 5 tasks * 4 priority)
        difficulty_score = min(data['difficulty_score'] / 20.0, 1.0)
        
        # Combined score: average of workload and difficulty
        day_scores[day_date] = (workload_score + difficulty_score) / 2
    
    # Get the score for the target day (lower is better)
    target_day_score = day_scores[slot_date]
    
    # Convert to bonus/penalty: lower day score = higher bonus
    # 0.0 day score = +0.5 bonus, 1.0 day score = -0.2 penalty
    weekly_balance_bonus = 0.5 - (target_day_score * 0.7)
    
    return weekly_balance_bonus


def calculate_workload_density_score(schedulable_object, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate workload density: 1 - (num_tasks_scheduled_on_day / max_daily_capacity)
    Rewards open days
    """
    slot_date = slot.start.date()
    
    # Count tasks already scheduled on this day
    num_tasks_on_day = 0
    for s in slots:
        if (s.occupant and 
            hasattr(s.occupant, 'id') and  # Check if it's a Quest object
            s.occupant.id != schedulable_object.id and
            s.start.date() == slot_date):
            num_tasks_on_day += 1
    
    # Add current task
    num_tasks_on_day += 1
    
    # Set maximum daily capacity (8 hours of focused work)
    max_daily_capacity = 8.0
    
    # Calculate density
    density = num_tasks_on_day / max_daily_capacity
    
    # Return reverse density to reward open days
    return max(0.0, 1.0 - density)


def calculate_spacing_bonus(schedulable_object, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate spacing bonus for recurring tasks
    For daily tasks: prioritize exactly 24 hours apart (same time each day)
    For weekly tasks: score higher if well-spaced from other instances
    """
    if not schedulable_object.recurrence_rule:
        return 0.0  # Not a recurring task
    
    # Check if this is a daily recurring task
    is_daily = "FREQ=DAILY" in schedulable_object.recurrence_rule
    
    # Find other instances of the same task type
    similar_tasks = []
    for s in slots:
        if (s.occupant and 
            hasattr(s.occupant, 'id') and  # Check if it's a Quest object
            s.occupant.id != schedulable_object.id and 
            hasattr(s.occupant, 'title') and  # Check if it has a title
            s.occupant.title == schedulable_object.title):
            similar_tasks.append(s)
    
    if not similar_tasks:
        return 0.5  # No other instances, moderate bonus
    
    # For daily tasks: prioritize exactly 24 hours apart (same time each day)
    if is_daily:
        # Find the most recent instance
        most_recent = max(similar_tasks, key=lambda s: s.start)
        
        # Calculate time difference in hours
        time_diff_hours = abs((slot.start - most_recent.start).total_seconds() / 3600)
        
        # Perfect 24-hour spacing gets maximum bonus
        if 23.5 <= time_diff_hours <= 24.5:  # Allow 30-minute tolerance
            return 1.0  # Perfect daily spacing
        elif 22 <= time_diff_hours <= 26:  # Allow 2-hour tolerance
            return 0.7  # Good daily spacing
        elif 20 <= time_diff_hours <= 28:  # Allow 4-hour tolerance
            return 0.3  # Acceptable daily spacing
        else:
            return 0.0  # Poor daily spacing
    
    # For weekly tasks: use the original spacing logic
    else:
        # Calculate minimum distance to other instances
        min_distance = float('inf')
        for task_slot in similar_tasks:
            distance = abs((slot.start - task_slot.start).total_seconds() / 3600)  # hours
            min_distance = min(min_distance, distance)
        
        # Score based on spacing
        if min_distance >= 24:
            return 1.0  # Well spaced (24+ hours)
        elif min_distance >= 12:
            return 0.7  # Moderately spaced (12+ hours)
        elif min_distance >= 6:
            return 0.3  # Somewhat spaced (6+ hours)
        else:
            return 0.0  # Too close


def calculate_automatic_buffer_bonus(schedulable_object, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate bonus for automatic buffer time based on task difficulty and length.
    Ensures adequate breaks between demanding tasks.
    """
    # Calculate task difficulty score (1-5 scale)
    difficulty_score = schedulable_object.priority  # Using priority as difficulty proxy
    
    # Calculate task length in hours
    task_length_hours = schedulable_object.duration_minutes / 60 if schedulable_object.duration_minutes else 1
    
    # Calculate required buffer time based on difficulty and length
    required_buffer_minutes = 0
    
    # Base buffer on task length
    if task_length_hours >= 4:
        required_buffer_minutes = 30  # 30 min buffer for 4+ hour tasks
    elif task_length_hours >= 2:
        required_buffer_minutes = 20  # 20 min buffer for 2+ hour tasks
    elif task_length_hours >= 1:
        required_buffer_minutes = 15  # 15 min buffer for 1+ hour tasks
    else:
        required_buffer_minutes = 10  # 10 min buffer for short tasks
    
    # Increase buffer for high-difficulty tasks
    if difficulty_score >= 4:
        required_buffer_minutes += 15  # Extra 15 min for high-priority tasks
    elif difficulty_score >= 3:
        required_buffer_minutes += 10  # Extra 10 min for medium-high priority tasks
    
    # Check if there's adequate buffer time before this slot
    buffer_start = slot.start - timedelta(minutes=required_buffer_minutes)
    
    # Look for tasks that end too close to our buffer start
    for s in slots:
        if (s.occupant and 
            hasattr(s.occupant, 'id') and  # Check if it's a Quest object
            s.occupant.id != schedulable_object.id and
            s.end > buffer_start):
            # Task ends too close, not enough buffer
            return -0.3  # Penalty for insufficient buffer
    
    return 0.2  # Bonus for adequate buffer time


def get_schedulable_object_difficulty_score(schedulable_object) -> float:
    """
    Convert Quest difficulty to numeric score.
    """
    if hasattr(schedulable_object, 'difficulty') and schedulable_object.difficulty:
        # Map QuestDifficulty enum to numeric values
        difficulty_map = {
            'EASY': 1.0,
            'MEDIUM': 2.0,
            'HARD': 3.0,
            'EXPERT': 4.0
        }
        return difficulty_map.get(schedulable_object.difficulty.value, 2.0)
    else:
        # Fallback to priority as difficulty proxy
        return schedulable_object.priority 