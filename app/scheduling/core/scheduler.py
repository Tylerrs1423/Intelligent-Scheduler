"""
Main scheduler class that orchestrates all scheduling operations.
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from .time_slot import CleanTimeSlot, AVAILABLE, RESERVED
from ..scoring.slot_scoring import calculate_slot_score

from ..constraints.time_constraints import is_slot_allowed
from ..utils.slot_utils import (
    move_event_slots, remove_event_slots
)

# ================================
# INITIALIZATION & SETUP
# ================================

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

# ================================
# EVENT LOADING & SETUP
# ================================

    #load fixed events into the scheduler from database
    def load_fixed_events(self, db: Session, user_id: int):
        """Load fixed events into the scheduler for a specific user."""
        from app.models import Event
        from app.schemas import SchedulingFlexibility
        events = db.query(Event).filter(
            Event.scheduling_flexibility == SchedulingFlexibility.FIXED,
            Event.user_id == user_id
        ).all()
        for event in events:
            duration = event.end_time - event.start_time
            buffer_before = getattr(event, 'buffer_before', 0) or 0
            buffer_after = getattr(event, 'buffer_after', 0) or 0
            
            # Create a slot for the fixed event
            buffer_start = event.start_time - timedelta(minutes=buffer_before)
            buffer_end = event.end_time + timedelta(minutes=buffer_after)
            slot = CleanTimeSlot(buffer_start, buffer_end, AVAILABLE)
            
            self._schedule_in_slot(event, duration, slot, buffer_before, buffer_after)




# ================================
# CORE SCHEDULING LOGIC
# ================================

    def schedule_task_with_buffers(self, schedulable_object, duration: timedelta, exact_start_time: datetime = None, exact_end_time: datetime = None) -> List[CleanTimeSlot]:
        """
        Main coordinator method for scheduling tasks with buffers.
        Delegates to specialized helper methods based on scheduling type.
        """
        # Get buffer configuration
        buffer_before, buffer_after = self._get_buffer_configuration(schedulable_object)
        
        # Determine scheduling strategy and get optimal slot
        if exact_start_time:
            optimal_candidate, original_slot = self._handle_exact_time_scheduling(
                schedulable_object, duration, exact_start_time, exact_end_time, buffer_before, buffer_after
            )
            if not optimal_candidate:
                return []
        else:
            optimal_candidate, original_slot = self._handle_flexible_scheduling(
                schedulable_object, duration, buffer_before, buffer_after
            )
            if not optimal_candidate:
                return []
        
        # Schedule the task and update scheduler
        new_slots = self._schedule_in_slot(schedulable_object, duration, optimal_candidate, buffer_before, buffer_after)
        
        # Update scheduler slots - both flexible and fixed events preserve fragments
        self._update_slots_with_fragments(original_slot, optimal_candidate, new_slots)
        
        return new_slots


# ================================
# SCHEDULING HELPER METHODS
# ================================

    def _get_buffer_configuration(self, schedulable_object) -> tuple[int, int]:
        """Extract buffer configuration from schedulable object."""
        buffer_before = getattr(schedulable_object, 'buffer_before', 0) or 0
        buffer_after = getattr(schedulable_object, 'buffer_after', 0) or 0
        return buffer_before, buffer_after

    def _handle_exact_time_scheduling(self, schedulable_object, duration: timedelta, exact_start_time: datetime, 
                                    exact_end_time: datetime, buffer_before: int, buffer_after: int) -> tuple[Optional[CleanTimeSlot], Optional[CleanTimeSlot]]:
        """Handle exact time scheduling logic."""
        # Calculate buffer-inclusive time window
        buffer_before_start = exact_start_time - timedelta(minutes=buffer_before)
        task_start = exact_start_time
        
        # Use exact end time directly if provided, otherwise calculate from duration
        if exact_end_time and exact_end_time > exact_start_time:
            task_end = exact_end_time
        else:
            task_end = task_start + duration
        
        buffer_after_end = task_end + timedelta(minutes=buffer_after)
        
        # Find containing slot
        original_slot = self._find_containing_available_slot(buffer_before_start, buffer_after_end)
        if not original_slot:
            return None, None
        
        # Create optimal candidate
        optimal_candidate = CleanTimeSlot(buffer_before_start, buffer_after_end, AVAILABLE)
        return optimal_candidate, original_slot

    def _handle_flexible_scheduling(self, schedulable_object, duration: timedelta, buffer_before: int, buffer_after: int) -> tuple[Optional[CleanTimeSlot], Optional[CleanTimeSlot]]:
        """Handle flexible scheduling logic."""
        total_duration = duration + timedelta(minutes=buffer_before + buffer_after)
        
        # Find optimal slot
        optimal_candidate = self._find_optimal_slot(schedulable_object, total_duration)
        if not optimal_candidate:
            return None, None
        
        # Find containing available slot
        original_slot = self._find_containing_available_slot(optimal_candidate.start, optimal_candidate.end)
        if not original_slot:
            return None, None
        
        return optimal_candidate, original_slot

    def _find_containing_available_slot(self, start_time: datetime, end_time: datetime) -> Optional[CleanTimeSlot]:
        """Find an available slot that contains the given time range."""
        for slot in self.slots:
            if (slot.occupant == AVAILABLE and
                slot.start <= start_time and
                slot.end >= end_time):
                return slot
        return None



    def _update_slots_with_fragments(self, original_slot: CleanTimeSlot, optimal_candidate: CleanTimeSlot, 
                                    new_slots: List[CleanTimeSlot]):
        """Update slots preserving available fragments for both exact and flexible scheduling."""
        full_replacement: List[CleanTimeSlot] = []
        
        # Preceding available fragment
        if original_slot.start < optimal_candidate.start:
            pre_fragment = CleanTimeSlot(original_slot.start, optimal_candidate.start, AVAILABLE)
            full_replacement.append(pre_fragment)
        
        # Scheduled slots (buffers/task)
        full_replacement.extend(new_slots)
        
        # Trailing available fragment
        if optimal_candidate.end < original_slot.end:
            post_fragment = CleanTimeSlot(optimal_candidate.end, original_slot.end, AVAILABLE)
            full_replacement.append(post_fragment)
        
        self.replace_slot(original_slot, full_replacement, self.slots)

# ================================
# SLOT FINDING & OPTIMIZATION
# ================================

    def _find_optimal_slot(self, schedulable_object, total_duration: timedelta) -> Optional[CleanTimeSlot]:
        """
        Find the optimal time slot for a quest using the weighted scoring formula.
        Now tests candidate positions within large available slots.
        """
        available_slots = []
        
        # Find all available slots that can fit the task (duration check only)
        for slot in self.slots:
            if (slot.occupant == AVAILABLE and 
                slot.occupant != RESERVED and
                slot.duration() >= total_duration):
                    available_slots.append(slot)
        
        if not available_slots:
            return None
        
        # Generate candidate slots for each available slot
        all_candidates = []
        for available_slot in available_slots:
            candidates = self._generate_candidate_slots(available_slot, schedulable_object, total_duration)
            all_candidates.extend(candidates)
        
        if not all_candidates:
            return None
        
        # Check each candidate slot with strict rules
        allowed_candidates = []
        for candidate in all_candidates:
            if is_slot_allowed(schedulable_object, candidate, self.slots):
                allowed_candidates.append(candidate)
        
        if not allowed_candidates:
            return None
        
        # Score each allowed candidate slot using the weighted formula
        scored_candidates = []
        for candidate in allowed_candidates:
            score = calculate_slot_score(schedulable_object, candidate, self.slots)
            scored_candidates.append((score, candidate))
        
        # Sort by score (highest first) and return the best candidate
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        return scored_candidates[0][1]

    def _generate_candidate_slots(self, available_slot: CleanTimeSlot, schedulable_object, total_duration: timedelta, interval_minutes: int = 5) -> List[CleanTimeSlot]:
        """
        Generate candidate slots at fixed intervals within a large available time block.
        This allows testing different start times within the same available period.
        """
        candidates = []
        
        # Start time for first candidate
        current_start = available_slot.start
        
        # End time for the entire available slot
        slot_end = available_slot.end
        
        # Generate candidates until we can't fit the task anymore
        while current_start + total_duration <= slot_end:
            # Create a candidate slot that starts at current_start
            candidate = CleanTimeSlot(
                start=current_start,
                end=current_start + total_duration,
                occupant=AVAILABLE
            )
            candidates.append(candidate)
            
            # Move to next interval
            current_start += timedelta(minutes=interval_minutes)
        
        return candidates



# ================================
# TASK SCHEDULING & BUFFERING
# ================================

    def _schedule_in_slot(self, schedulable_object, duration: timedelta, slot: CleanTimeSlot, buffer_before: int, buffer_after: int) -> List[CleanTimeSlot]:
        """Schedule a task in a specific slot with buffers."""
        new_slots = []
        
        # Create buffer before (if any)
        if buffer_before > 0:
            buffer_start = slot.start
            buffer_end = slot.start + timedelta(minutes=buffer_before)
            buffer_slot = CleanTimeSlot(buffer_start, buffer_end, "BUFFER")
            new_slots.append(buffer_slot)
        
        # Create task slot
        task_start = slot.start + timedelta(minutes=buffer_before)
        task_end = task_start + duration
        task_slot = CleanTimeSlot(task_start, task_end, schedulable_object)
        new_slots.append(task_slot)
        
        # Create buffer after (if any)
        if buffer_after > 0:
            buffer_start = task_end
            buffer_end = task_end + timedelta(minutes=buffer_after)
            buffer_slot = CleanTimeSlot(buffer_start, buffer_end, "BUFFER")
            new_slots.append(buffer_slot)
        
        # Track this event's slots
        if hasattr(schedulable_object, 'id') and schedulable_object.id:
            if schedulable_object.id not in self.event_slots:
                self.event_slots[schedulable_object.id] = []
            self.event_slots[schedulable_object.id].extend(new_slots)
        
        return new_slots



# ================================
# SLOT MANAGEMENT UTILITIES
# ================================

    def replace_slot(self, old_slot: CleanTimeSlot, new_slots: List[CleanTimeSlot], slots: List[CleanTimeSlot]):
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

    def merge_adjacent_available_slots(self, slots: List[CleanTimeSlot]):
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

    def get_available_slots(self, slots: List[CleanTimeSlot], min_duration: timedelta) -> List[CleanTimeSlot]:
        """Get all available slots that can fit the minimum duration"""
        available = []
        for slot in slots:
            if (slot.occupant == AVAILABLE and 
                slot.duration() >= min_duration):
                available.append(slot)
        return available

    def get_sleep_info(self, sleep_start, sleep_end, slots: List[CleanTimeSlot]) -> dict:
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

    def format_scheduler_repr(self, slots: List[CleanTimeSlot], sleep_start=None, sleep_end=None) -> str:
        """Format scheduler representation string"""
        sleep_info = self.get_sleep_info(sleep_start, sleep_end, slots)
        if sleep_info["sleep_blocking_enabled"]:
            return f"CleanScheduler({len(slots)} slots, sleep: {sleep_info['sleep_start']}-{sleep_info['sleep_end']})"
        else:
            return f"CleanScheduler({len(slots)} slots, no sleep blocking)"

# ================================
# EVENT MANAGEMENT & TRACKING
# ================================

    def remove_event(self, event_id: int):
        """Remove an event and all its associated slots."""
        remove_event_slots(event_id, self.slots)
        # Merge adjacent available slots after removal
        self.merge_adjacent_available_slots(self.slots)
        if event_id in self.event_slots:
            del self.event_slots[event_id]

    def move_event(self, event_id: int, new_start_time: datetime):
        """Move an event to a new start time."""
        if event_id not in self.event_slots:
            return False
        
        event_slots = self.event_slots[event_id]
        return move_event_slots(event_slots, new_start_time, self.slots)

# ================================
# UTILITY & QUERY METHODS
# ================================



    def __repr__(self):
        return self.format_scheduler_repr(self.slots, self.sleep_start, self.sleep_end) 