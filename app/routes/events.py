import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Tuple, Optional, Any, Dict
from datetime import datetime, timedelta, time
from ..database import get_db
from ..models import User, Quest, Event, QuestStatus, SourceType, PreferredTimeOfDay, TaskDifficulty
from ..schemas import EventOut
from ..auth import get_current_user
from copy import deepcopy
from bisect import bisect_left, insort

router = APIRouter(tags=["events"])
logger = logging.getLogger(__name__)

# --- Cleaner TimeSlot System ---

class CleanTimeSlot:
    """
    A cleaner TimeSlot system where each slot represents exactly one thing:
    - A task (with occupant)
    - A buffer zone (with is_buffer=True)
    - Available time (with occupant=None and is_buffer=False)
    """
    def __init__(self, start: datetime, end: datetime, occupant: Any = None, is_buffer: bool = False, is_flexible: bool = False):
        self.start = start
        self.end = end
        self.occupant = occupant
        self.is_buffer = is_buffer
        self.is_flexible = is_flexible

    def duration(self) -> timedelta:
        return self.end - self.start

    def __lt__(self, other):
        return self.start < other.start

    def __repr__(self):
        if self.is_buffer:
            return f"BufferSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')})"
        elif self.occupant:
            occupant_name = getattr(self.occupant, 'title', str(self.occupant))
            return f"TaskSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')}, {occupant_name})"
        else:
            return f"AvailableSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')})"

class CleanScheduler:
    """
    A cleaner scheduler that creates separate TimeSlots for tasks and buffers.
    This makes moving and deleting much simpler.
    """
    def __init__(self, window_start: datetime, window_end: datetime, user_sleep_start: time = None, user_sleep_end: time = None):
        self.window_start = window_start
        self.window_end = window_end
        self.sleep_start = user_sleep_start
        self.sleep_end = user_sleep_end
        
        # Create slots that exclude sleep time
        self.slots = self._create_slots_excluding_sleep()
        self.event_slots: Dict[int, List[CleanTimeSlot]] = {}  # Track all slots for each event

    def _create_slots_excluding_sleep(self) -> List[CleanTimeSlot]:
        """Create available time slots excluding sleep time"""
        if not self.sleep_start or not self.sleep_end:
            # No sleep time set, use full window
            return [CleanTimeSlot(self.window_start, self.window_end)]
        
        slots = []
        
        # Handle sleep time that crosses midnight
        if self.sleep_start > self.sleep_end:
            # Sleep crosses midnight (e.g., 11 PM to 7 AM)
            # Available: 7 AM to 11 PM
            for day in self._get_days_in_window():
                day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                # Available slot: sleep_end to sleep_start
                available_start = day_start.replace(hour=self.sleep_end.hour, minute=self.sleep_end.minute)
                available_end = day_start.replace(hour=self.sleep_start.hour, minute=self.sleep_start.minute)
                
                if available_start < available_end:
                    slots.append(CleanTimeSlot(available_start, available_end))
        else:
            # Normal sleep (same day, e.g., 10 PM to 6 AM)
            # Available: 6 AM to 10 PM
            for day in self._get_days_in_window():
                day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                # Available slot 1: day_start to sleep_start
                available_start_1 = day_start
                available_end_1 = day_start.replace(hour=self.sleep_start.hour, minute=self.sleep_start.minute)
                
                # Available slot 2: sleep_end to day_end
                available_start_2 = day_start.replace(hour=self.sleep_end.hour, minute=self.sleep_end.minute)
                available_end_2 = day_end
                
                if available_start_1 < available_end_1:
                    slots.append(CleanTimeSlot(available_start_1, available_end_1))
                if available_start_2 < available_end_2:
                    slots.append(CleanTimeSlot(available_start_2, available_end_2))
        
        return slots

    def _get_days_in_window(self) -> List[datetime]:
        """Get all days within the scheduling window"""
        days = []
        current_day = self.window_start.replace(hour=0, minute=0, second=0, microsecond=0)
        end_day = self.window_end.replace(hour=0, minute=0, second=0, microsecond=0)
        
        while current_day <= end_day:
            days.append(current_day)
            current_day += timedelta(days=1)
        
        return days

    def schedule_task_with_buffers(self, quest: Quest, duration: timedelta, exact_start_time: datetime = None) -> List[CleanTimeSlot]:
        """
        Schedule a task with buffers, creating separate slots for each component.
        If exact_start_time is provided, schedule at that exact time.
        Otherwise, find the first available slot.
        Returns list of created slots (task + buffers).
        """
        buffer_before = getattr(quest, 'buffer_before', 0)
        buffer_after = getattr(quest, 'buffer_after', 0)
        
        if exact_start_time:
            # Schedule at exact time
            # Calculate all times
            buffer_before_start = exact_start_time - timedelta(minutes=buffer_before)
            task_start = exact_start_time
            task_end = task_start + duration
            buffer_after_end = task_end + timedelta(minutes=buffer_after)
            
            # Check if the entire time range (including buffers) is available
            for slot in self.slots:
                if (slot.occupant is None and 
                    not slot.is_buffer and 
                    slot.start <= buffer_before_start and 
                    slot.end >= buffer_after_end):
                    
                    # Found a slot that can accommodate the entire task + buffers
                    available_slot = slot
                    break
            else:
                return []  # No available slot that can fit the entire range
        else:
            # Find available slot that can fit the entire task + buffers
            total_duration = duration + timedelta(minutes=buffer_before + buffer_after)
            available_slot = None
            
            for slot in self.slots:
                if (slot.occupant is None and 
                    not slot.is_buffer and 
                    slot.duration() >= total_duration):
                    available_slot = slot
                    break
            
            if not available_slot:
                return []  # No available slot
            
            # Calculate times for first available slot
            task_start = available_slot.start + timedelta(minutes=buffer_before)
            task_end = task_start + duration
            buffer_before_start = available_slot.start
            buffer_after_end = task_end + timedelta(minutes=buffer_after)
        
        # Create new slots
        new_slots = []
        
        # 1. Buffer before (if any)
        if buffer_before > 0:
            buffer_before_slot = CleanTimeSlot(
                buffer_before_start,
                task_start,
                is_buffer=True
            )
            new_slots.append(buffer_before_slot)
        
        # 2. Task slot
        task_slot = CleanTimeSlot(
            task_start,
            task_end,
            occupant=quest
        )
        new_slots.append(task_slot)
        
        # 3. Buffer after (if any)
        if buffer_after > 0:
            buffer_after_slot = CleanTimeSlot(
                task_end,
                buffer_after_end,
                is_buffer=True
            )
            new_slots.append(buffer_after_slot)
        
        # 4. Remaining available time before the task (only if exact time)
        if exact_start_time and available_slot.start < buffer_before_start:
            before_slot = CleanTimeSlot(
                available_slot.start,
                buffer_before_start
            )
            new_slots.append(before_slot)
        
        # 5. Remaining available time after the task
        if buffer_after_end < available_slot.end:
            after_slot = CleanTimeSlot(
                buffer_after_end,
                available_slot.end
            )
            new_slots.append(after_slot)
        
        # Update the scheduler
        self._replace_slot(available_slot, new_slots)
        
        # Track slots for this event
        self.event_slots[quest.id] = new_slots
        
        return new_slots

    def schedule_task_at_exact_time(self, quest: Quest, exact_start_time: datetime, duration: timedelta) -> List[CleanTimeSlot]:
        """
        Schedule a task at an exact time, creating separate slots for each component.
        Returns list of created slots (task + buffers).
        """
        buffer_before = getattr(quest, 'buffer_before', 0)
        buffer_after = getattr(quest, 'buffer_after', 0)
        
        # Calculate all times
        buffer_before_start = exact_start_time - timedelta(minutes=buffer_before)
        task_start = exact_start_time
        task_end = task_start + duration
        buffer_after_end = task_end + timedelta(minutes=buffer_after)
        
        # Check if the entire time range (including buffers) is available
        for slot in self.slots:
            if (slot.occupant is None and 
                not slot.is_buffer and 
                slot.start <= buffer_before_start and 
                slot.end >= buffer_after_end):
                
                # Found a slot that can accommodate the entire task + buffers
                available_slot = slot
                break
        else:
            return []  # No available slot that can fit the entire range
        
        # Create new slots
        new_slots = []
        
        # 1. Buffer before (if any)
        if buffer_before > 0:
            buffer_before_slot = CleanTimeSlot(
                buffer_before_start,
                task_start,
                is_buffer=True
            )
            new_slots.append(buffer_before_slot)
        
        # 2. Task slot
        task_slot = CleanTimeSlot(
            task_start,
            task_end,
            occupant=quest
        )
        new_slots.append(task_slot)
        
        # 3. Buffer after (if any)
        if buffer_after > 0:
            buffer_after_slot = CleanTimeSlot(
                task_end,
                buffer_after_end,
                is_buffer=True
            )
            new_slots.append(buffer_after_slot)
        
        # 4. Remaining available time before the task
        if available_slot.start < buffer_before_start:
            before_slot = CleanTimeSlot(
                available_slot.start,
                buffer_before_start
            )
            new_slots.append(before_slot)
        
        # 5. Remaining available time after the task
        if buffer_after_end < available_slot.end:
            after_slot = CleanTimeSlot(
                buffer_after_end,
                available_slot.end
            )
            new_slots.append(after_slot)
        
        # Update the scheduler
        self._replace_slot(available_slot, new_slots)
        
        # Track slots for this event
        self.event_slots[quest.id] = new_slots
        
        return new_slots

    def _replace_slot(self, old_slot: CleanTimeSlot, new_slots: List[CleanTimeSlot]):
        """Replace one slot with multiple new slots"""
        slot_index = self.slots.index(old_slot)
        self.slots.pop(slot_index)
        
        # Insert new slots in order
        for i, new_slot in enumerate(new_slots):
            self.slots.insert(slot_index + i, new_slot)
        
        # Keep slots sorted
        self.slots.sort()

    def remove_event(self, event_id: int):
        """Remove an event and all its associated slots (task + buffers)"""
        if event_id not in self.event_slots:
            return
        
        slots_to_remove = self.event_slots[event_id]
        
        # Find the slots to remove
        slots_to_remove_indices = []
        for slot in slots_to_remove:
            try:
                index = self.slots.index(slot)
                slots_to_remove_indices.append(index)
            except ValueError:
                continue  # Slot already removed
        
        # Remove slots in reverse order to maintain indices
        for index in sorted(slots_to_remove_indices, reverse=True):
            self.slots.pop(index)
        
        # Merge adjacent available slots
        self._merge_adjacent_available_slots()
        
        # Remove from tracking
        del self.event_slots[event_id]

    def _merge_adjacent_available_slots(self):
        """Merge adjacent available slots to keep the scheduler clean"""
        i = 0
        while i < len(self.slots) - 1:
            current = self.slots[i]
            next_slot = self.slots[i + 1]
            
            if (current.occupant is None and 
                not current.is_buffer and
                next_slot.occupant is None and 
                not next_slot.is_buffer):
                
                # Merge the slots
                merged_slot = CleanTimeSlot(
                    current.start,
                    next_slot.end
                )
                
                # Replace both slots with merged slot
                self.slots[i] = merged_slot
                self.slots.pop(i + 1)
            else:
                i += 1

    def move_event(self, event_id: int, new_start_time: datetime):
        """Move an event to a new start time"""
        if event_id not in self.event_slots:
            return False
        
        event_slots = self.event_slots[event_id]
        
        # Calculate the current duration and offset
        current_start = event_slots[0].start
        current_end = event_slots[-1].end
        duration = current_end - current_start
        offset = new_start_time - current_start
        
        # Check if the new position is available
        new_end_time = new_start_time + duration
        
        # Simple check: ensure the new time range doesn't conflict with existing slots
        for slot in self.slots:
            if slot.occupant and slot.occupant.id != event_id:
                if (new_start_time < slot.end and new_end_time > slot.start):
                    return False  # Conflict detected
        
        # Move all slots for this event
        for slot in event_slots:
            slot.start += offset
            slot.end += offset
        
        # Re-sort slots
        self.slots.sort()
        
        return True

    def get_available_slots(self, min_duration: timedelta) -> List[CleanTimeSlot]:
        """Get all available slots that can fit the minimum duration"""
        available = []
        for slot in self.slots:
            if (slot.occupant is None and 
                not slot.is_buffer and 
                slot.duration() >= min_duration):
                available.append(slot)
        return available

    def get_sleep_info(self) -> dict:
        """Get information about sleep blocking"""
        if not self.sleep_start or not self.sleep_end:
            return {
                "sleep_blocking_enabled": False,
                "message": "No sleep time configured"
            }
        
        if self.sleep_start > self.sleep_end:
            sleep_type = "crosses_midnight"
            sleep_duration = "overnight"
        else:
            sleep_type = "same_day"
            sleep_duration = "daytime"
        
        return {
            "sleep_blocking_enabled": True,
            "sleep_start": self.sleep_start.strftime("%I:%M %p"),
            "sleep_end": self.sleep_end.strftime("%I:%M %p"),
            "sleep_type": sleep_type,
            "sleep_duration": sleep_duration,
            "available_slots": len(self.slots)
        }

    def __repr__(self):
        sleep_info = self.get_sleep_info()
        if sleep_info["sleep_blocking_enabled"]:
            return f"CleanScheduler({len(self.slots)} slots, sleep: {sleep_info['sleep_start']}-{sleep_info['sleep_end']})"
        else:
            return f"CleanScheduler({len(self.slots)} slots, no sleep blocking)"
