"""
Displacement algorithms for moving lower priority tasks to make room for higher priority ones.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from itertools import combinations
from ..core.time_slot import CleanTimeSlot, AVAILABLE
from ..scoring.time_scoring import calculate_time_preference_score
from app.models import Quest, SchedulingFlexibility


def displace_lower_priority_tasks(quest: Quest, required_duration: timedelta, slots: List[CleanTimeSlot], 
                                 find_optimal_slot_func, merge_slots_func, schedule_task_func) -> Optional[CleanTimeSlot]:
    """
    Comprehensive displacement system that evaluates single and multi-event displacements using scoring.
    Returns the optimal slot after displacement, or None if no effective displacement possible.
    """
    if not quest.priority:
        return None
    
    quest_priority = quest.priority
    
    # Find all displaceable tasks
    displaceable_tasks = []
    for slot in slots:
        if (slot.occupant and 
            hasattr(slot.occupant, 'priority') and 
            slot.occupant.priority and 
            slot.occupant.priority < quest_priority):
            
            # Skip tasks after deadline
            if quest.deadline and slot.start > quest.deadline:
                continue
            
            # Skip FIXED tasks
            if (hasattr(slot.occupant, 'scheduling_flexibility') and 
                slot.occupant.scheduling_flexibility == SchedulingFlexibility.FIXED):
                continue
            
            displaceable_tasks.append(slot)
    
    if not displaceable_tasks:
        return None
    
    # Sort by priority (lowest first) and duration (shortest first)
    displaceable_tasks.sort(key=lambda s: (s.occupant.priority, (s.end - s.start)))
    
    # Evaluate all possible displacement combinations
    best_displacement = None
    best_score = float('-inf')
    
    print(f"      🔍 Evaluating displacement for '{quest.title}' (priority {quest.priority})")
    print(f"      📊 Found {len(displaceable_tasks)} displaceable tasks")
    
    # Try single displacement first
    for slot in displaceable_tasks:
        score = evaluate_single_displacement(quest, slot, required_duration, slots, 
                                           find_optimal_slot_func, merge_slots_func)
        print(f"      📈 Single displacement score for '{slot.occupant.title}': {score}")
        if score > best_score:
            best_score = score
            best_displacement = ([slot], score)
            print(f"      ✅ New best single displacement: {slot.occupant.title} (score: {score})")
    
    # Try multi-event displacements (up to 3 tasks)
    for num_tasks in range(2, min(4, len(displaceable_tasks) + 1)):
        print(f"      🔄 Evaluating {num_tasks}-task displacements...")
        # Generate combinations of num_tasks
        for task_combination in combinations(displaceable_tasks, num_tasks):
            score = evaluate_multi_displacement(quest, list(task_combination), required_duration, slots,
                                              find_optimal_slot_func, merge_slots_func)
            task_names = [slot.occupant.title for slot in task_combination]
            print(f"      📈 Multi displacement score for {task_names}: {score}")
            if score > best_score:
                best_score = score
                best_displacement = (list(task_combination), score)
                print(f"      ✅ New best multi displacement: {task_names} (score: {score})")
    
    # If we found a good displacement, perform it
    if best_displacement and best_score > 0:  # Only displace if score is positive
        slots_to_displace, score = best_displacement
        return perform_comprehensive_displacement(quest, slots_to_displace, required_duration, slots,
                                                find_optimal_slot_func, merge_slots_func, schedule_task_func)
    
    return None


def evaluate_single_displacement(quest: Quest, slot_to_displace: CleanTimeSlot, required_duration: timedelta,
                               slots: List[CleanTimeSlot], find_optimal_slot_func, merge_slots_func) -> float:
    """Evaluate the score for displacing a single task."""
    displaced_task = slot_to_displace.occupant
    
    # Check if there's enough time around this slot
    total_available_time = find_available_time_around_slot(slot_to_displace, slots)
    if total_available_time < required_duration:
        return float('-inf')  # Not enough time
    
    # Find the optimal slot that would be created
    # Temporarily remove the task to test
    original_occupant = slot_to_displace.occupant
    slot_to_displace.occupant = AVAILABLE
    merge_slots_func(slots)
        
    optimal_slot = find_optimal_slot_func(quest, required_duration)
    
    # Restore the task
    slot_to_displace.occupant = original_occupant
    merge_slots_func(slots)
        
    if not optimal_slot:
        return float('-inf')
    
    # Calculate displacement score
    displacement_score = calculate_displacement_score(quest, optimal_slot, displaced_task, slot_to_displace)
    
    # Add reschedulability penalty
    reschedule_penalty = calculate_reschedule_difficulty(displaced_task)
    
    total_score = displacement_score - reschedule_penalty
    print(f"         📊 Displacement score: {displacement_score}, Reschedule penalty: {reschedule_penalty}, Total: {total_score}")
    
    return total_score


def evaluate_multi_displacement(quest: Quest, slots_to_displace: List[CleanTimeSlot], required_duration: timedelta,
                              slots: List[CleanTimeSlot], find_optimal_slot_func, merge_slots_func) -> float:
    """Evaluate the score for displacing multiple tasks."""
    displaced_tasks = [slot.occupant for slot in slots_to_displace]
    
    # Check if there's enough total time
    total_available_time = sum(slot.duration().total_seconds() / 60 for slot in slots_to_displace)  # Convert to minutes
    required_minutes = required_duration.total_seconds() / 60
    if total_available_time < required_minutes:
        return float('-inf')
    
    # Temporarily remove all tasks to test
    original_occupants = []
    for slot in slots_to_displace:
        original_occupants.append(slot.occupant)
        slot.occupant = AVAILABLE
    
    merge_slots_func(slots)
    
    optimal_slot = find_optimal_slot_func(quest, required_duration)
    
    # Restore all tasks
    for slot, occupant in zip(slots_to_displace, original_occupants):
        slot.occupant = occupant
    merge_slots_func(slots)
    
    if not optimal_slot:
        return float('-inf')
    
    # Calculate base displacement score (sum of individual scores)
    total_displacement_score = 0
    total_reschedule_penalty = 0
    
    for slot, task in zip(slots_to_displace, displaced_tasks):
        individual_score = calculate_displacement_score(quest, optimal_slot, task, slot)
        total_displacement_score += individual_score
        total_reschedule_penalty += calculate_reschedule_difficulty(task)
    
    # Multi-displacement penalty (displacing multiple tasks is harder)
    multi_penalty = len(slots_to_displace) * 0.5
    
    return total_displacement_score - total_reschedule_penalty - multi_penalty


def calculate_reschedule_difficulty(task: Quest) -> float:
    """Calculate how difficult it would be to reschedule a task."""
    difficulty = 0.0
    
    # Scheduling flexibility penalty (REDUCED PENALTIES)
    if hasattr(task, 'scheduling_flexibility'):
        if task.scheduling_flexibility == SchedulingFlexibility.WINDOW:
            difficulty += 0.5  # Reduced from 2.0
        elif task.scheduling_flexibility == SchedulingFlexibility.STRICT:
            difficulty += 0.3  # Reduced from 1.5
        elif task.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
            difficulty += 0.1  # Reduced from 0.5
    
    # Duration penalty (REDUCED PENALTIES)
    if task.duration_minutes:
        hours = task.duration_minutes / 60
        if hours >= 4:
            difficulty += 0.5  # Reduced from 2.0
        elif hours >= 2:
            difficulty += 0.3  # Reduced from 1.0
        elif hours >= 1:
            difficulty += 0.1  # Reduced from 0.5
    
    # Deadline urgency penalty (REDUCED PENALTIES)
    if task.deadline:
        days_until_deadline = (task.deadline - datetime.now()).days
        if days_until_deadline <= 1:
            difficulty += 0.5  # Reduced from 3.0
        elif days_until_deadline <= 3:
            difficulty += 0.3  # Reduced from 2.0
        elif days_until_deadline <= 7:
            difficulty += 0.1  # Reduced from 1.0
    
    return difficulty


def perform_comprehensive_displacement(quest: Quest, slots_to_displace: List[CleanTimeSlot], required_duration: timedelta,
                                     slots: List[CleanTimeSlot], find_optimal_slot_func, merge_slots_func, 
                                     schedule_task_func) -> Optional[CleanTimeSlot]:
    """Actually perform the displacement and return the optimal slot."""
    displaced_tasks = []
    
    # Remove all tasks to be displaced
    for slot in slots_to_displace:
        displaced_tasks.append((slot, slot.occupant))
        slot.occupant = AVAILABLE
    
    # Merge adjacent slots
    merge_slots_func()
    
    # Find the optimal slot for the new quest
    optimal_slot = find_optimal_slot_func(quest, required_duration)
    if not optimal_slot:
        # Restore displaced tasks if we can't find a slot
        for slot, task in displaced_tasks:
            slot.occupant = task
        merge_slots_func()
        return None
    
    # Reserve the optimal slot by temporarily marking it as occupied
    original_optimal_occupant = optimal_slot.occupant
    optimal_slot.occupant = "RESERVED"
    
    # Reschedule all displaced tasks
    failed_reschedules = []
    for slot, displaced_task in displaced_tasks:
        print(f'      🔄 Rescheduling displaced task: {displaced_task.title} (original slot: {slot.start.strftime("%Y-%m-%d %H:%M")}-{slot.end.strftime("%H:%M")})')
        displaced_duration = timedelta(minutes=displaced_task.duration_minutes or 60)
        reschedule_result = schedule_task_func(displaced_task, displaced_duration)
        if reschedule_result:
            for res in reschedule_result:
                print(f'         ↪️  Rescheduled to: {res.start.strftime("%Y-%m-%d %H:%M")}-{res.end.strftime("%H:%M")})')
        else:
            print(f'         ❌ Failed to reschedule: {displaced_task.title}')
        if not reschedule_result:
            failed_reschedules.append((slot, displaced_task))
        
    # Restore the optimal slot
    optimal_slot.occupant = original_optimal_occupant
    
    # If any tasks failed to reschedule, restore them to their original slots
    for slot, task in failed_reschedules:
        slot.occupant = task
    merge_slots_func()
    
    print(f'      ✅ Displacement successful: {len(displaced_tasks)} tasks displaced, {len(failed_reschedules)} failed to reschedule')
    return optimal_slot


def find_available_time_around_slot(task_slot: CleanTimeSlot, slots: List[CleanTimeSlot]) -> timedelta:
    """
    Find the total available time around a task slot (including the task's own duration).
    This uses the same logic as the working method in metaheuristic.py.
    """
    # Start with the task's own duration
    total_available = task_slot.duration()
    
    # Look for AVAILABLE slots that are adjacent to this task
    for slot in slots:
        if slot.occupant == AVAILABLE:
            # Check if this available slot is adjacent to the task
            if slot.end <= task_slot.start:
                # Available slot ends before task starts
                adjacent_time = task_slot.start - slot.end
                total_available += adjacent_time
            elif slot.start >= task_slot.end:
                # Available slot starts after task ends
                adjacent_time = slot.start - task_slot.end
                total_available += adjacent_time
    
    # If no AVAILABLE slots found, calculate available time based on day boundaries
    if total_available == task_slot.duration():  # Only the task's own duration
        # Find the day boundaries for this task
        day_start = task_slot.start.replace(hour=7, minute=0, second=0, microsecond=0)  # 7 AM
        day_end = task_slot.start.replace(hour=22, minute=0, second=0, microsecond=0)   # 10 PM
        
        # Calculate available time before and after the task
        available_before = task_slot.start - day_start
        available_after = day_end - task_slot.end
        
        if available_before > timedelta(0):
            total_available += available_before
        if available_after > timedelta(0):
            total_available += available_after
    
    return total_available


def calculate_displacement_score(new_quest: Quest, new_slot: CleanTimeSlot, 
                               displaced_task: Quest, original_slot: CleanTimeSlot) -> float:
    """
    Calculate the score for a displacement decision.
    Higher score = better displacement choice.
    """
    # Base score: priority difference (higher is better) - INCREASED WEIGHT
    priority_diff = (new_quest.priority - displaced_task.priority) * 5  # Increased from 2 to 5
    
    # Time preference bonus for new task
    time_pref_bonus = calculate_time_preference_score(new_quest, new_slot)
    
    # Deadline urgency penalty for displaced task (REDUCED PENALTIES)
    deadline_penalty = 0
    if displaced_task.deadline:
        days_until_deadline = (displaced_task.deadline - datetime.now()).days
        if days_until_deadline <= 1:
            deadline_penalty = -1.0  # Reduced from -3.0
        elif days_until_deadline <= 3:
            deadline_penalty = -0.5  # Reduced from -2.0
        elif days_until_deadline <= 7:
            deadline_penalty = -0.2  # Reduced from -1.0
    
    # Scheduling flexibility penalty (REDUCED PENALTIES)
    flexibility_penalty = 0
    if hasattr(displaced_task, 'scheduling_flexibility'):
        if displaced_task.scheduling_flexibility == SchedulingFlexibility.FIXED:
            flexibility_penalty = -2.0  # Reduced from -5.0
        elif displaced_task.scheduling_flexibility == SchedulingFlexibility.WINDOW:
            flexibility_penalty = -0.5  # Reduced from -2.0
        elif displaced_task.scheduling_flexibility == SchedulingFlexibility.STRICT:
            flexibility_penalty = -0.3  # Reduced from -1.5
        elif displaced_task.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
            flexibility_penalty = -0.1  # Reduced from -0.5
    
    # Duration penalty (REDUCED PENALTIES)
    duration_penalty = 0
    if displaced_task.duration_minutes:
        hours = displaced_task.duration_minutes / 60
        if hours >= 4:
            duration_penalty = -0.5  # Reduced from -2.0
        elif hours >= 2:
            duration_penalty = -0.3  # Reduced from -1.0
        elif hours >= 1:
            duration_penalty = -0.1  # Reduced from -0.5
        # Short tasks get no penalty
    
    # Current slot quality bonus (if displaced task is in a poor slot, less penalty)
    current_slot_quality = calculate_time_preference_score(displaced_task, original_slot)
    slot_quality_bonus = current_slot_quality * 0.5  # Reduce penalty if current slot is poor
    
    # Add a small positive base score to encourage displacement when beneficial
    base_score = 0.1
    
    total_score = (priority_diff + time_pref_bonus + deadline_penalty + 
                  flexibility_penalty + duration_penalty + slot_quality_bonus + base_score)
    
    return total_score 