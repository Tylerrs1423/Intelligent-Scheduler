"""
Priority-based scoring functions for slot evaluation.
"""

from datetime import datetime
from ..core.time_slot import CleanTimeSlot
def calculate_priority_score(schedulable_object) -> float:
    """
    Map priority to score: Low: 0.3, Medium: 0.6, High: 1.0, Very High: 1.5+
    """
    if schedulable_object.priority == 1:
        return 0.3  # Low priority
    elif schedulable_object.priority == 2:
        return 0.6  # Medium priority
    elif schedulable_object.priority == 3:
        return 0.8  # Medium-high priority
    elif schedulable_object.priority == 4:
        return 1.0  # High priority
    elif schedulable_object.priority == 5:
        return 1.2  # Very high priority
    elif schedulable_object.priority == 6:
        return 1.5  # Extremely high priority
    else:
        return 0.5  # Default


def calculate_task_selection_priority(schedulable_object) -> float:
    """
    Calculate task selection priority combining priority, urgency, and frequency.
    Higher score = higher priority for task selection order.
    """
    # Base priority score (0.3 - 1.0)
    priority_score = calculate_priority_score(schedulable_object)
    
    # Urgency score based on deadline proximity
    urgency_score = calculate_deadline_urgency_score(schedulable_object)
    
    # Frequency bonus for recurring tasks
    frequency_score = calculate_frequency_score(schedulable_object)
    
    # Combine scores with weights
    # Priority is most important (50%), then urgency (40%), then frequency (10%)
    total_score = (
        (0.5 * priority_score) +
        (0.4 * urgency_score) +
        (0.1 * frequency_score)
    )
    
    return total_score


def calculate_deadline_urgency_score(schedulable_object) -> float:
    """
    Calculate urgency score based on deadline proximity (0.0 - 1.0).
    Higher score = closer to deadline = more urgent.
    """
    deadline_datetime = schedulable_object.deadline
    if not deadline_datetime:
        return 0.0  # No urgency if no deadline
    
    now = datetime.now()
    hours_until_deadline = (deadline_datetime - now).total_seconds() / 3600
    
    # If deadline has passed, very high urgency
    if hours_until_deadline < 0:
        return 1.0
    
    # Calculate urgency based on hours until deadline
    if hours_until_deadline <= 24:  # 1 day or less
        # Very urgent: exponential decay
        urgency_score = 1.0 - (hours_until_deadline / 24.0) ** 2
        return max(0.8, urgency_score)
    elif hours_until_deadline <= 48:  # 2 days or less
        # Urgent: linear decay
        urgency_score = 0.8 - (hours_until_deadline - 24.0) / 24.0 * 0.3
        return max(0.5, urgency_score)
    elif hours_until_deadline <= 72:  # 3 days or less
        # Moderately urgent
        urgency_score = 0.5 - (hours_until_deadline - 48.0) / 24.0 * 0.2
        return max(0.3, urgency_score)
    elif hours_until_deadline <= 168:  # 1 week or less
        # Somewhat urgent
        urgency_score = 0.3 - (hours_until_deadline - 72.0) / 96.0 * 0.1
        return max(0.2, urgency_score)
    else:
        # Not urgent
        urgency_score = 0.2 - (hours_until_deadline - 168.0) / 168.0 * 0.1
        return max(0.1, urgency_score)


def calculate_frequency_score(schedulable_object) -> float:
    """
    Calculate frequency score for recurring tasks (0.0 - 1.0).
    Higher score = more frequent = higher priority.
    """
    if not schedulable_object.recurrence_rule:
        return 0.0  # Not recurring
    
    # Parse recurrence rule to determine frequency
    if "FREQ=DAILY" in schedulable_object.recurrence_rule:
        return 1.0  # Daily tasks get highest frequency score
    elif "FREQ=WEEKLY" in schedulable_object.recurrence_rule:
        return 0.8  # Weekly tasks get high frequency score
    elif "FREQ=MONTHLY" in schedulable_object.recurrence_rule:
        return 0.6  # Monthly tasks get medium frequency score
    elif "FREQ=YEARLY" in schedulable_object.recurrence_rule:
        return 0.4  # Yearly tasks get low frequency score
    else:
        return 0.5  # Unknown frequency, default medium 