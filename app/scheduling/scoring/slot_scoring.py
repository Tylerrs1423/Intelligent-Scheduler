"""
Main slot scoring aggregator that combines all domain-specific scoring functions.
"""

from typing import List
from ..core.time_slot import CleanTimeSlot
from app.models import Quest
from .time_scoring import calculate_time_preference_score, calculate_earlier_bonus, calculate_urgency_score
from .priority_scoring import calculate_priority_score, calculate_task_selection_priority
from .workload_scoring import (
    calculate_daily_workload_bonus, 
    calculate_weekly_balance_score, 
    calculate_workload_density_score,
    calculate_spacing_bonus,
    calculate_automatic_buffer_bonus
)
from .difficulty_scoring import calculate_difficulty_workload_balance


def calculate_slot_score(quest: Quest, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate the overall score for a quest-slot combination.
    This is the main scoring function that aggregates all domain-specific scores.
    """
    # Time preference score (0.0 - 100.0)
    time_match = calculate_time_preference_score(quest, slot)
    
    # Priority score (0.3 - 1.5)
    priority_score = calculate_priority_score(quest)
    
    # Earlier bonus (0.0 - 0.1)
    earlier_bonus = calculate_earlier_bonus(quest, slot)
    
    # Urgency score (0.0 - 10.0)
    urgency_score = calculate_urgency_score(quest, slot)
    
    # Workload scores
    daily_workload = calculate_daily_workload_bonus(quest, slot, slots)
    weekly_balance = calculate_weekly_balance_score(quest, slot, slots)
    workload_density = calculate_workload_density_score(quest, slot, slots)
    spacing = calculate_spacing_bonus(quest, slot, slots)
    buffer_bonus = calculate_automatic_buffer_bonus(quest, slot, slots)
    
    # Difficulty balance score
    difficulty_balance = calculate_difficulty_workload_balance(quest, slot, slots)
    
    # Combine scores with weights
    # Time preference is most important (1000x weight)
    # Priority and urgency are secondary
    # Workload and difficulty balance are important for distribution
    # Earlier bonus is a small adjustment
    
    total_score = (
        (1000.0 * time_match) +      # Time preference dominates
        (10.0 * priority_score) +    # Priority is important
        (5.0 * urgency_score) +      # Urgency matters
        (2.0 * daily_workload) +     # Daily workload limits
        (1.5 * weekly_balance) +     # Weekly balance
        (1.0 * workload_density) +   # Workload density
        (1.0 * spacing) +            # Spacing for recurring tasks
        (0.5 * buffer_bonus) +       # Buffer time
        (1.0 * difficulty_balance) + # Difficulty balance
        (1.0 * earlier_bonus)        # Small bonus for early scheduling
    )
    
    # Debug output for specific quests
    if quest.title == "Gym Workout":
        print(f"      🎯 SLOT SCORE: '{quest.title}' slot {slot.start.time()}-{slot.end.time()}")
        print(f"         📊 Time match: {time_match:.2f}")
        print(f"         📊 Priority: {priority_score:.2f}")
        print(f"         📊 Urgency: {urgency_score:.2f}")
        print(f"         📊 Daily workload: {daily_workload:.2f}")
        print(f"         📊 Weekly balance: {weekly_balance:.2f}")
        print(f"         📊 Difficulty balance: {difficulty_balance:.2f}")
        print(f"         📊 Earlier bonus: {earlier_bonus:.2f}")
        print(f"         📊 TOTAL: {total_score:.2f}")
    
    return total_score 