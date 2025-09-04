"""
Main scheduler class that orchestrates all scheduling operations.
"""

from datetime import datetime, timedelta, time
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from .time_slot import CleanTimeSlot, AVAILABLE, RESERVED
from ..scoring.slot_scoring import calculate_slot_score
from ..algorithms.displacement import displace_lower_priority_tasks

from ..constraints.time_constraints import is_slot_allowed, is_same_day_recurring_allowed
from ..utils.slot_utils import (
    merge_adjacent_available_slots, get_available_slots, replace_slot,
    move_event_slots, get_sleep_info, format_scheduler_repr,
    find_slot_by_event_id, remove_event_slots
)
from app.models import Quest

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
    def load_fixed_events(self, db: Session):
        """Load fixed events into the scheduler."""
        from app.models import Event, SchedulingFlexibility
        events = db.query(Event).filter(Event.scheduling_flexibility == SchedulingFlexibility.FIXED).all()
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

    def schedule_task_with_buffers(self, quest: Quest, duration: timedelta, exact_start_time: datetime = None, exact_end_time: datetime = None) -> List[CleanTimeSlot]:
        """
        Main coordinator method for scheduling tasks with buffers.
        Delegates to specialized helper methods based on scheduling type.
        """
        # Get buffer configuration
        buffer_before, buffer_after = self._get_buffer_configuration(quest)
        
        # Determine scheduling strategy and get optimal slot
        if exact_start_time:
            optimal_candidate, containing_slot = self._handle_exact_time_scheduling(
                quest, duration, exact_start_time, exact_end_time, buffer_before, buffer_after
            )
            if not optimal_candidate:
                return []
        else:
            optimal_candidate, available_slot = self._handle_flexible_scheduling(
                quest, duration, buffer_before, buffer_after
            )
            if not optimal_candidate:
                return []
        
        # Schedule the task and update scheduler
        new_slots = self._schedule_in_slot(quest, duration, optimal_candidate, buffer_before, buffer_after)
        self._update_scheduler_slots(optimal_candidate, new_slots, exact_start_time, containing_slot, available_slot)
        
        return new_slots

    def schedule_task_at_exact_time(self, quest: Quest, exact_start_time: datetime, duration: timedelta, exact_end_time: datetime = None) -> List[CleanTimeSlot]:
        """Schedule a task at an exact time (optionally specifying an exact end time)."""
        return self.schedule_task_with_buffers(quest, duration, exact_start_time, exact_end_time)

# ================================
# SCHEDULING HELPER METHODS
# ================================

    def _get_buffer_configuration(self, quest: Quest) -> tuple[int, int]:
        """Extract buffer configuration from quest."""
        buffer_before = getattr(quest, 'buffer_before', 0) or 0
        buffer_after = getattr(quest, 'buffer_after', 0) or 0
        return buffer_before, buffer_after

    def _handle_exact_time_scheduling(self, quest: Quest, duration: timedelta, exact_start_time: datetime, 
                                    exact_end_time: datetime, buffer_before: int, buffer_after: int) -> tuple[Optional[CleanTimeSlot], Optional[CleanTimeSlot]]:
        """Handle exact time scheduling logic."""
        # Adjust duration if exact end time provided
        if exact_end_time and exact_end_time > exact_start_time:
            duration = exact_end_time - exact_start_time
        
        # Calculate buffer-inclusive time window
        buffer_before_start = exact_start_time - timedelta(minutes=buffer_before)
        task_start = exact_start_time
        task_end = task_start + duration
        buffer_after_end = task_end + timedelta(minutes=buffer_after)
        
        # Find containing slot
        containing_slot = self._find_containing_available_slot(buffer_before_start, buffer_after_end)
        if not containing_slot:
            return None, None
        
        # Create optimal candidate
        optimal_candidate = CleanTimeSlot(buffer_before_start, buffer_after_end, AVAILABLE)
        return optimal_candidate, containing_slot

    def _handle_flexible_scheduling(self, quest: Quest, duration: timedelta, buffer_before: int, buffer_after: int) -> tuple[Optional[CleanTimeSlot], Optional[CleanTimeSlot]]:
        """Handle flexible scheduling logic."""
        total_duration = duration + timedelta(minutes=buffer_before + buffer_after)
        
        # Find optimal slot
        optimal_candidate = self._find_optimal_slot(quest, total_duration)
        if not optimal_candidate:
            optimal_candidate = self._try_displacement_scheduling(quest, total_duration)
            if not optimal_candidate:
                return None, None
        
        # Find containing available slot
        available_slot = self._find_containing_available_slot(optimal_candidate.start, optimal_candidate.end)
        if not available_slot:
            return None, None
        
        return optimal_candidate, available_slot

    def _find_containing_available_slot(self, start_time: datetime, end_time: datetime) -> Optional[CleanTimeSlot]:
        """Find an available slot that contains the given time range."""
        for slot in self.slots:
            if (slot.occupant == AVAILABLE and
                slot.start <= start_time and
                slot.end >= end_time):
                return slot
        return None

    def _try_displacement_scheduling(self, quest: Quest, total_duration: timedelta) -> Optional[CleanTimeSlot]:
        """Try to displace lower priority tasks to make room."""
        return displace_lower_priority_tasks(
            quest, total_duration, self.slots,
            self._find_optimal_slot, merge_adjacent_available_slots,
            self.schedule_task_with_buffers
        )

    def _update_scheduler_slots(self, optimal_candidate: CleanTimeSlot, new_slots: List[CleanTimeSlot], 
                               exact_start_time: bool, containing_slot: Optional[CleanTimeSlot], 
                               available_slot: Optional[CleanTimeSlot]):
        """Update scheduler slots after scheduling."""
        if exact_start_time:
            self._update_slots_for_exact_time(containing_slot, optimal_candidate, new_slots)
        else:
            replace_slot(available_slot, new_slots, self.slots)

    def _update_slots_for_exact_time(self, containing_slot: CleanTimeSlot, optimal_candidate: CleanTimeSlot, 
                                    new_slots: List[CleanTimeSlot]):
        """Update slots for exact time scheduling, preserving available fragments."""
        full_replacement: List[CleanTimeSlot] = []
        
        # Preceding available fragment
        if containing_slot.start < optimal_candidate.start:
            pre_fragment = CleanTimeSlot(containing_slot.start, optimal_candidate.start, AVAILABLE)
            full_replacement.append(pre_fragment)
        
        # Scheduled slots (buffers/task)
        full_replacement.extend(new_slots)
        
        # Trailing available fragment
        if optimal_candidate.end < containing_slot.end:
            post_fragment = CleanTimeSlot(optimal_candidate.end, containing_slot.end, AVAILABLE)
            full_replacement.append(post_fragment)
        
        replace_slot(containing_slot, full_replacement, self.slots)

# ================================
# SLOT FINDING & OPTIMIZATION
# ================================

    def _find_optimal_slot(self, quest: Quest, total_duration: timedelta) -> Optional[CleanTimeSlot]:
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
            elif slot.occupant not in (AVAILABLE, RESERVED):
                occupant_name = getattr(slot.occupant, 'title', str(slot.occupant))
                print(f"      ⛔ Slot {slot.start.strftime('%Y-%m-%d %H:%M')} - {slot.end.strftime('%H:%M')} is occupied by '{occupant_name}' (priority: {getattr(slot.occupant, 'priority', '?')})")
        
        if not available_slots:
            return None
        
        # Generate candidate slots for each available slot
        all_candidates = []
        for available_slot in available_slots:
            candidates = self._generate_candidate_slots(available_slot, quest, total_duration)
            all_candidates.extend(candidates)
        
        if not all_candidates:
            return None
        
        # Check each candidate slot with strict rules
        allowed_candidates = []
        for candidate in all_candidates:
            if is_slot_allowed(quest, candidate, self.slots):
                allowed_candidates.append(candidate)
        
        if not allowed_candidates:
            return None
        
        # Score each allowed candidate slot using the weighted formula
        scored_candidates = []
        for candidate in allowed_candidates:
            score = calculate_slot_score(quest, candidate, self.slots)
            scored_candidates.append((score, candidate))
            if "Gym Workout" in quest.title:
                print(f"      🏅 Candidate slot: {candidate.start.strftime('%H:%M')} - {candidate.end.strftime('%H:%M')}, score={score}")
        
        # Sort by score (highest first) and return the best candidate
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        if scored_candidates and "Gym Workout" in quest.title:
            best = scored_candidates[0][1]
            print(f"      🥇 PICKED slot: {best.start.strftime('%H:%M')} - {best.end.strftime('%H:%M')}, score={scored_candidates[0][0]}")
        return scored_candidates[0][1]

    def _generate_candidate_slots(self, available_slot: CleanTimeSlot, quest: Quest, total_duration: timedelta, interval_minutes: int = 5) -> List[CleanTimeSlot]:
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

    def _schedule_in_slot(self, quest: Quest, duration: timedelta, slot: CleanTimeSlot, buffer_before: int, buffer_after: int) -> List[CleanTimeSlot]:
        """Schedule a task in a specific slot with buffers."""
        return self._schedule_regular_task(quest, duration, slot, buffer_before, buffer_after)

    def _schedule_regular_task(self, quest: Quest, duration: timedelta, slot: CleanTimeSlot, buffer_before: int, buffer_after: int) -> List[CleanTimeSlot]:
        """Schedule a regular task with buffers."""
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
        task_slot = CleanTimeSlot(task_start, task_end, quest)
        new_slots.append(task_slot)
        
        # Create buffer after (if any)
        if buffer_after > 0:
            buffer_start = task_end
            buffer_end = task_end + timedelta(minutes=buffer_after)
            buffer_slot = CleanTimeSlot(buffer_start, buffer_end, "BUFFER")
            new_slots.append(buffer_slot)
        
        # Track this event's slots
        if hasattr(quest, 'id') and quest.id:
            if quest.id not in self.event_slots:
                self.event_slots[quest.id] = []
            self.event_slots[quest.id].extend(new_slots)
        
        return new_slots



# ================================
# EVENT MANAGEMENT & TRACKING
# ================================

    def remove_event(self, event_id: int):
        """Remove an event and all its associated slots."""
        remove_event_slots(event_id, self.slots)
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

    def get_available_slots(self, min_duration: timedelta) -> List[CleanTimeSlot]:
        """Get all available slots that can fit the minimum duration."""
        return get_available_slots(self.slots, min_duration)

    def get_sleep_info(self) -> dict:
        """Get information about sleep blocking."""
        return get_sleep_info(self.sleep_start, self.sleep_end, self.slots)

    def __repr__(self):
        return format_scheduler_repr(self.slots, self.sleep_start, self.sleep_end) 