"""
Utility functions for slot management and manipulation.
"""

from datetime import datetime, timedelta
from typing import List
from ..core.time_slot import CleanTimeSlot, AVAILABLE


def merge_adjacent_available_slots(slots: List[CleanTimeSlot]):
    """Merge adjacent available slots to keep the scheduler clean"""
    i = 0
    while i < len(slots) - 1:
        current = slots[i]
        next_slot = slots[i + 1]
        
        if (current.occupant == AVAILABLE and 
            next_slot.occupant == AVAILABLE and
            current.end == next_slot.start and
            current.end.date() == next_slot.start.date()):  # Only merge if they're actually adjacent in time AND on the same day
            
            # Merge the slots
            merged_slot = CleanTimeSlot(
                current.start,
                next_slot.end
            )
            
            # Replace both slots with merged slot
            slots[i] = merged_slot
            slots.pop(i + 1)
        else:
            i += 1


def get_available_slots(slots: List[CleanTimeSlot], min_duration: timedelta) -> List[CleanTimeSlot]:
    """Get all available slots that can fit the minimum duration"""
    available = []
    for slot in slots:
        if (slot.occupant == AVAILABLE and 
            slot.duration() >= min_duration):
            available.append(slot)
    return available


def replace_slot(old_slot: CleanTimeSlot, new_slots: List[CleanTimeSlot], slots: List[CleanTimeSlot]):
    """Replace an old slot with new slots in the slots list"""
    try:
        index = slots.index(old_slot)
        # Remove the old slot
        slots.pop(index)
        # Insert new slots at the same position
        for i, new_slot in enumerate(new_slots):
            slots.insert(index + i, new_slot)
        # Sort to maintain chronological order
        slots.sort()
    except ValueError:
        # Old slot not found, just append new slots
        slots.extend(new_slots)
        slots.sort()


def move_event_slots(event_slots: List[CleanTimeSlot], new_start_time: datetime, all_slots: List[CleanTimeSlot]) -> bool:
    """Move event slots to a new start time"""
    if not event_slots:
        return False
    
    # Calculate the current duration and offset
    current_start = event_slots[0].start
    current_end = event_slots[-1].end
    duration = current_end - current_start
    offset = new_start_time - current_start
    
    # Check if the new position is available
    new_end_time = new_start_time + duration
    
    # Simple check: ensure the new time range doesn't conflict with existing slots
    for slot in all_slots:
        if slot.occupant and slot not in event_slots:
            if (new_start_time < slot.end and new_end_time > slot.start):
                return False  # Conflict detected
    
    # Move all slots for this event
    for slot in event_slots:
        slot.start += offset
        slot.end += offset
    
    # Re-sort slots
    all_slots.sort()
    
    return True


def get_sleep_info(sleep_start, sleep_end, slots: List[CleanTimeSlot]) -> dict:
    """Get information about sleep blocking"""
    if not sleep_start or not sleep_end:
        return {
            "sleep_blocking_enabled": False,
            "message": "No sleep time configured"
        }
    
    if sleep_start > sleep_end:
        sleep_type = "crosses_midnight"
        sleep_duration = "overnight"
    else:
        sleep_type = "same_day"
        sleep_duration = "daytime"
    
    return {
        "sleep_blocking_enabled": True,
        "sleep_start": sleep_start.strftime("%I:%M %p"),
        "sleep_end": sleep_end.strftime("%I:%M %p"),
        "sleep_type": sleep_type,
        "sleep_duration": sleep_duration,
        "available_slots": len(slots)
    }


def format_scheduler_repr(slots: List[CleanTimeSlot], sleep_start=None, sleep_end=None) -> str:
    """Format scheduler representation string"""
    sleep_info = get_sleep_info(sleep_start, sleep_end, slots)
    if sleep_info["sleep_blocking_enabled"]:
        return f"CleanScheduler({len(slots)} slots, sleep: {sleep_info['sleep_start']}-{sleep_info['sleep_end']})"
    else:
        return f"CleanScheduler({len(slots)} slots, no sleep blocking)"


def find_slot_by_event_id(event_id: int, slots: List[CleanTimeSlot]) -> List[CleanTimeSlot]:
    """Find all slots for a specific event ID"""
    event_slots = []
    for slot in slots:
        if (slot.occupant and 
            hasattr(slot.occupant, 'id') and 
            slot.occupant.id == event_id):
            event_slots.append(slot)
    return event_slots


def remove_event_slots(event_id: int, slots: List[CleanTimeSlot]):
    """Remove all slots for a specific event ID"""
    slots_to_remove = []
    for slot in slots:
        if (slot.occupant and 
            hasattr(slot.occupant, 'id') and 
            slot.occupant.id == event_id):
            slots_to_remove.append(slot)
    
    # Remove the slots
    for slot in slots_to_remove:
        slots.remove(slot)
        # Replace with available slot
        available_slot = CleanTimeSlot(slot.start, slot.end, AVAILABLE)
        slots.append(available_slot)
    
    # Sort and merge adjacent available slots
    slots.sort()
    merge_adjacent_available_slots(slots) 