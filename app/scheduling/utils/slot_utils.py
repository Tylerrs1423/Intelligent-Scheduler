"""
Event-specific utility functions for slot manipulation.
"""

from datetime import datetime, timedelta
from typing import List
from ..core.time_slot import CleanTimeSlot, AVAILABLE


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
    
    # Sort slots
    slots.sort()
    
    # Note: merge_adjacent_available_slots is now a method of CleanScheduler
    # This function should be called from within the scheduler context 