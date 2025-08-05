"""
Difficulty-based scoring functions for slot evaluation.
"""

from datetime import date
from typing import List
from ..core.time_slot import CleanTimeSlot
from app.models import Quest, TaskDifficulty


def calculate_difficulty_workload_balance(quest: Quest, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate difficulty-based workload balancing score.
    Penalizes clustering of difficult tasks on the same day.
    Higher score = better distribution of difficulty across the week.
    """
    # Get the difficulty level of the current quest
    quest_difficulty = get_quest_difficulty_score(quest)
    
    # Get the target day for this slot
    target_date = slot.start.date()
    
    # Calculate current difficulty load for the target day
    current_day_difficulty = get_day_difficulty_load(target_date, slots)
    
    # Calculate average difficulty across all days
    avg_difficulty = get_average_difficulty_across_week(slots)
    
    # Calculate difficulty variance across the week
    difficulty_variance = get_difficulty_variance_across_week(slots)
    
    # Score based on how well this placement balances difficulty
    if current_day_difficulty + quest_difficulty <= avg_difficulty * 1.2:
        # Good: This placement keeps the day below 120% of average
        return 1.0
    elif current_day_difficulty + quest_difficulty <= avg_difficulty * 1.5:
        # Acceptable: This placement keeps the day below 150% of average
        return 0.7
    elif current_day_difficulty + quest_difficulty <= avg_difficulty * 2.0:
        # Poor: This placement puts the day above 200% of average
        return 0.3
    else:
        # Very poor: This placement creates a very difficult day
        return 0.1


def get_quest_difficulty_score(quest: Quest) -> float:
    """
    Get difficulty score for a quest based on its difficulty level and duration.
    Higher score = more difficult.
    """
    # Base difficulty from TaskDifficulty enum
    base_difficulty = 0.5  # Default medium difficulty
    
    if hasattr(quest, 'difficulty'):
        if quest.difficulty == TaskDifficulty.EASY:
            base_difficulty = 0.3
        elif quest.difficulty == TaskDifficulty.MEDIUM:
            base_difficulty = 0.6
        elif quest.difficulty == TaskDifficulty.HARD:
            base_difficulty = 1.0
        elif quest.difficulty == TaskDifficulty.VERY_HARD:
            base_difficulty = 1.5
    
    # Factor in duration (longer tasks are more mentally taxing)
    duration_hours = quest.duration_minutes / 60.0
    duration_factor = min(1.5, duration_hours / 2.0)  # Cap at 1.5x for very long tasks
    
    # Factor in priority (higher priority tasks are more stressful)
    priority_factor = quest.priority / 5.0  # Normalize to 0-1 range
    
    # Calculate final difficulty score
    difficulty_score = base_difficulty * (1.0 + duration_factor * 0.3 + priority_factor * 0.2)
    
    return min(2.0, difficulty_score)  # Cap at 2.0


def get_day_difficulty_load(target_date: date, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate the total difficulty load for a specific day.
    """
    total_difficulty = 0.0
    
    for slot in slots:
        if (slot.occupant and 
            hasattr(slot.occupant, 'id') and 
            slot.start.date() == target_date):
            # This is a scheduled task on the target day
            total_difficulty += get_quest_difficulty_score(slot.occupant)
    
    return total_difficulty


def get_average_difficulty_across_week(slots: List[CleanTimeSlot]) -> float:
    """
    Calculate the average difficulty load across all days in the scheduling window.
    """
    total_difficulty = 0.0
    days_with_tasks = 0
    
    # Get all unique dates in the scheduling window
    dates_in_window = set()
    for slot in slots:
        if slot.start:
            dates_in_window.add(slot.start.date())
    
    for date in dates_in_window:
        day_difficulty = get_day_difficulty_load(date, slots)
        if day_difficulty > 0:
            total_difficulty += day_difficulty
            days_with_tasks += 1
    
    if days_with_tasks == 0:
        return 0.0
    
    return total_difficulty / days_with_tasks


def get_difficulty_variance_across_week(slots: List[CleanTimeSlot]) -> float:
    """
    Calculate the variance in difficulty across the week.
    Higher variance = more uneven distribution.
    """
    avg_difficulty = get_average_difficulty_across_week(slots)
    if avg_difficulty == 0:
        return 0.0
    
    total_variance = 0.0
    days_with_tasks = 0
    
    # Get all unique dates in the scheduling window
    dates_in_window = set()
    for slot in slots:
        if slot.start:
            dates_in_window.add(slot.start.date())
    
    for date in dates_in_window:
        day_difficulty = get_day_difficulty_load(date, slots)
        if day_difficulty > 0:
            variance = ((day_difficulty - avg_difficulty) ** 2)
            total_variance += variance
            days_with_tasks += 1
    
    if days_with_tasks == 0:
        return 0.0
    
    return total_variance / days_with_tasks 