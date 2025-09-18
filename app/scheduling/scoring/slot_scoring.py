"""
Main slot scoring aggregator that combines all domain-specific scoring functions.
"""

from typing import List
from ..core.time_slot import CleanTimeSlot

from .time_scoring import calculate_time_preference_score, calculate_earlier_bonus, calculate_urgency_score
from .priority_scoring import calculate_priority_score
from .workload_scoring import calculate_daily_workload_bonus, calculate_weekly_balance_score


def calculate_slot_score(schedulable_object, slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> float:
    """
    Calculate the overall score for a schedulable_object-slot combination.
    This is the main scoring function that aggregates all domain-specific scores.
    """
    # Time preference score (0.0 - 100.0)
    time_match = calculate_time_preference_score(schedulable_object, slot)
    
    # Priority score (0.3 - 1.5)
    priority_score = calculate_priority_score(schedulable_object)
    
    # Earlier bonus (0.0 - 0.1)
    earlier_bonus = calculate_earlier_bonus(schedulable_object, slot)
    
    # Urgency score (0.0 - 10.0)
    urgency_score = calculate_urgency_score(schedulable_object, slot)
    
    # Workload scores
    daily_workload = calculate_daily_workload_bonus(schedulable_object, slot, slots)
    weekly_balance = calculate_weekly_balance_score(schedulable_object, slot, slots)
    
    # Combine scores with weights
    total_score = (
        (1000.0 * time_match) +      # Time preference dominates
        (10.0 * priority_score) +    # Priority is important
        (5.0 * urgency_score) +      # Urgency matters
        (2.0 * daily_workload) +     # Daily workload limits
        (1.5 * weekly_balance) +     # Weekly balance
        (1.0 * earlier_bonus)        # Small bonus for early scheduling
    )
    
    return total_score 