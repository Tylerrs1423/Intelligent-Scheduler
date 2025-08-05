import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Tuple, Optional, Any, Dict
from datetime import datetime, timedelta, time, date
from ..database import get_db
from ..models import User, Quest, Event, QuestStatus, SourceType, PreferredTimeOfDay, TaskDifficulty, SchedulingFlexibility
from ..schemas import EventOut
from ..auth import get_current_user
from copy import deepcopy
from bisect import bisect_left, insort
from itertools import combinations

router = APIRouter(tags=["events"])
logger = logging.getLogger(__name__)

# --- Cleaner TimeSlot System ---

# Special constants for slot types
BUFFER = "BUFFER"
AVAILABLE = "AVAILABLE"
RESERVED = "RESERVED"

class CleanTimeSlot:
    """
    A cleaner TimeSlot system where each slot represents exactly one thing:
    - A task (with occupant=Quest object)
    - A buffer zone (with occupant=BUFFER)
    - Available time (with occupant=AVAILABLE)
    """
    def __init__(self, start: datetime, end: datetime, occupant: Any = AVAILABLE, is_flexible: bool = False):
        self.start = start
        self.end = end
        self.occupant = occupant
        self.is_flexible = is_flexible

    def duration(self) -> timedelta:
        return self.end - self.start

    def __lt__(self, other):
        return self.start < other.start

    def __repr__(self):
        if self.occupant == BUFFER:
            return f"BufferSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')})"
        elif self.occupant == AVAILABLE:
            return f"AvailableSlot({self.start.strftime('%I:%M %p')} - {self.end.strftime('%I:%M %p')})"
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
        Schedule a quest with automatic buffers before and after.
        If exact_start_time is provided, schedule at that exact time.
        Otherwise, find the optimal slot based on priority and deadline.
        
        If the task is too long for available slots, it will be automatically chunked.
        """
        # Check if this task should be chunked
        if self._should_chunk_task(quest, duration):
            return self._schedule_chunked_task(quest, duration, exact_start_time)
        
        # Get buffer times, defaulting to 0 if None
        buffer_before = getattr(quest, 'buffer_before', 0) or 0
        buffer_after = getattr(quest, 'buffer_after', 0) or 0
        
        if exact_start_time:
            # Schedule at exact time
            # Calculate all times
            buffer_before_start = exact_start_time - timedelta(minutes=buffer_before)
            task_start = exact_start_time
            task_end = task_start + duration
            buffer_after_end = task_end + timedelta(minutes=buffer_after)
            
            # Check if the entire time range (including buffers) is available
            for slot in self.slots:
                if (slot.occupant == AVAILABLE and 
                    slot.start <= buffer_before_start and 
                    slot.end >= buffer_after_end):
                    
                    # Found a slot that can accommodate the entire task + buffers
                    available_slot = slot
                    break
            else:
                return []  # No available slot that can fit the entire range
            
            # Create a candidate slot for exact time scheduling
            optimal_candidate = CleanTimeSlot(buffer_before_start, buffer_after_end, AVAILABLE)
        else:
            # Find optimal slot based on priority and deadline
            total_duration = duration + timedelta(minutes=buffer_before + buffer_after)
            print(f"      🔍 Looking for optimal slot for '{quest.title}' (duration: {total_duration})")
            optimal_candidate = self._find_optimal_slot(quest, total_duration)
            
            
            if not optimal_candidate:
                # Try displacement for higher priority tasks
                optimal_candidate = self._displace_lower_priority_tasks(quest, total_duration)
                if optimal_candidate:
                    print(f"         🔄 DISPLACED lower priority tasks to schedule {quest.title}")
                else:
                    return []  # No available slot and no displacement possible
            
            # Find the original available slot that contains this candidate
            available_slot = None
            for slot in self.slots:
                if (slot.occupant == AVAILABLE and 
                    slot.start <= optimal_candidate.start and 
                    slot.end >= optimal_candidate.end):
                    available_slot = slot
                    break
            
            if not available_slot:
                return []  # Couldn't find the original slot
        
        # Use _schedule_in_slot to handle pomodoro vs regular tasks
        # Pass the optimal candidate slot directly
        new_slots = self._schedule_in_slot(quest, duration, optimal_candidate, buffer_before, buffer_after)
        
        # Update the scheduler by replacing the original available slot
        self._replace_slot(available_slot, new_slots)
        
        return new_slots

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
            if self._is_slot_allowed(quest, candidate):
                allowed_candidates.append(candidate)
        
        if not allowed_candidates:
            return None
        
        # Score each allowed candidate slot using the weighted formula
        scored_candidates = []
        for candidate in allowed_candidates:
            score = self._calculate_slot_score(quest, candidate)
            scored_candidates.append((score, candidate))
            if "Gym Workout" in quest.title:
                print(f"      🏅 Candidate slot: {candidate.start.strftime('%H:%M')} - {candidate.end.strftime('%H:%M')}, score={score}")
        
        # Sort by score (highest first) and return the best candidate
        scored_candidates.sort(key=lambda x: x[0], reverse=True)
        if scored_candidates and "Gym Workout" in quest.title:
            best = scored_candidates[0][1]
            print(f"      🥇 PICKED slot: {best.start.strftime('%H:%M')} - {best.end.strftime('%H:%M')}, score={scored_candidates[0][0]}")
        return scored_candidates[0][1]

    def _is_slot_allowed(self, quest: Quest, slot: CleanTimeSlot) -> bool:
        """
        Check if a slot is allowed for this quest based on strict rules.
        """
        # Rule 1: Check absolute deadline (hard constraint)
        if quest.deadline:
            # Calculate when the task would finish
            task_duration = timedelta(minutes=quest.duration_minutes or 60)
            task_end_time = slot.start + task_duration
            
            # If the task finishes after the absolute deadline, it's not allowed
            if task_end_time > quest.deadline:
                print(f"      ❌ Slot rejected: absolute deadline constraint (finishes at {task_end_time}, deadline {quest.deadline})")
                return False
        
        # Rule 2: Check scheduling flexibility constraints
        if hasattr(quest, 'scheduling_flexibility'):
            if quest.scheduling_flexibility == SchedulingFlexibility.FIXED:
                # FIXED tasks must be scheduled at their exact hard_start time
                if hasattr(quest, 'hard_start') and quest.hard_start:
                    # Check if slot starts at the exact hard_start time
                    slot_start_time = slot.start.time()
                    if slot_start_time != quest.hard_start or slot_end_time != quest.hard_end:
                        print(f"      ❌ Slot rejected: FIXED scheduling constraint (slot starts at {slot_start_time}, hard_start {quest.hard_start})")
                        return False
                else:
                    print(f"      ❌ Slot rejected: FIXED scheduling constraint but no hard_start specified")
                    return False
            
            elif quest.scheduling_flexibility == SchedulingFlexibility.WINDOW:
                # WINDOW tasks must be within their preferred time window AND on the correct day
                
                # First, check hard time constraints (hard_start and hard_end)
                slot_start_time = slot.start.time()
                slot_end_time = slot.end.time()
                
                print(f"      🔍 WINDOW constraint check for '{quest.title}': slot {slot_start_time}-{slot_end_time}, hard {quest.hard_start}-{quest.hard_end}")
                
                if quest.hard_start and slot_start_time < quest.hard_start:
                    print(f"      ❌ Slot rejected: WINDOW hard start constraint (slot starts at {slot_start_time}, hard_start {quest.hard_start})")
                    return False
                
                if quest.hard_end and slot_end_time > quest.hard_end:
                    print(f"      ❌ Slot rejected: WINDOW hard end constraint (slot ends at {slot_end_time}, hard_end {quest.hard_end})")
                    return False
                
                # Check time preference score
                time_preference_score = self._calculate_time_preference_score(quest, slot)
                if time_preference_score < 0.1:  # Must be at least within hard window (0.1 score)
                    print(f"      ❌ Slot rejected: WINDOW scheduling constraint (time preference score {time_preference_score} < 0.1)")
                    return False
                
                # STRICT DAY CONSTRAINT: WINDOW tasks must be on their designated recurrence days
                if quest.recurrence_rule:
                    # Parse the recurrence rule to get the allowed days
                    try:
                        from dateutil import rrule
                        rule = rrule.rrulestr(quest.recurrence_rule, dtstart=slot.start)
                        
                        # Get the day of week for the slot
                        slot_day = slot.start.weekday()  # Monday=0, Tuesday=1, etc.
                        
                        # Convert to RRULE day format (MO=0, TU=1, etc.)
                        day_names = ['MO', 'TU', 'WE', 'TH', 'FR', 'SA', 'SU']
                        slot_day_name = day_names[slot_day]
                        
                        # Check if this day is allowed in the recurrence rule
                        if 'BYDAY=' in quest.recurrence_rule:
                            allowed_days = quest.recurrence_rule.split('BYDAY=')[1].split(';')[0].split(',')
                            print(f"      🔍 WINDOW day constraint check for '{quest.title}' (ID: {getattr(quest, 'id', 'None')}): slot day {slot_day_name}, recurrence rule '{quest.recurrence_rule}', allowed days {allowed_days}")
                            if slot_day_name not in allowed_days:
                                print(f"      ❌ Slot rejected: WINDOW day constraint (slot day {slot_day_name}, allowed days {allowed_days})")
                                return False
                        else:
                            print(f"      ❌ Slot rejected: WINDOW day constraint (no BYDAY in recurrence rule)")
                            return False
                            
                    except Exception as e:
                        print(f"      ❌ Slot rejected: WINDOW day constraint (error parsing recurrence: {e})")
                        return False
            
            elif quest.scheduling_flexibility == SchedulingFlexibility.STRICT:
                # STRICT tasks must stay on the same day as their designated date
                # This is handled by the recurrence service expanding them correctly
                pass
        
        # Rule 3: Check time preference for non-constrained tasks (hard limit)
        if not hasattr(quest, 'scheduling_flexibility') or quest.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE:
            time_preference_score = self._calculate_time_preference_score(quest, slot)
            if time_preference_score < 0:  # Negative score means disqualified
                print(f"      ❌ Slot rejected: time preference score {time_preference_score} < 0")
                return False
        
        # Rule 4: Check for same-day recurring tasks (unless allowed)
        if not self._is_same_day_recurring_allowed(quest, slot):
            print(f"      ❌ Slot rejected: same-day recurring constraint")
            return False
        
        return True

    def _is_same_day_recurring_allowed(self, quest: Quest, slot: CleanTimeSlot) -> bool:
        """
        Check if a recurring task can be scheduled on the same day as another instance.
        Returns True if allowed, False if not allowed.
        """
        # If explicitly allowed, return True
        if hasattr(quest, 'allow_same_day_recurring') and quest.allow_same_day_recurring:
            return True
        
        # Check if there are other instances of the same task on the same day
        slot_date = slot.start.date()
        for s in self.slots:
            if (s.occupant and 
                hasattr(s.occupant, 'id') and  # Check if it's a Quest object
                s.occupant.id != quest.id and 
                hasattr(s.occupant, 'title') and  # Check if it has a title
                s.occupant.title == quest.title and
                s.start.date() == slot_date):
                return False  # Same task already scheduled on this day
        
        return True

    def _calculate_distribution_bonus(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate bonus for distributing similar tasks across time.
        Prevents clustering of recurring tasks.
        """
        # Check if this is a recurring task (has recurrence_rule)
        if not quest.recurrence_rule:
            return 0.0
        
        # Find other instances of the same task type
        similar_tasks = []
        for s in self.slots:
            if (s.occupant and 
                hasattr(s.occupant, 'id') and  # Check if it's a Quest object
                s.occupant.id != quest.id and 
                hasattr(s.occupant, 'title') and  # Check if it has a title
                s.occupant.title == quest.title):
                similar_tasks.append(s)
        
        if not similar_tasks:
            return 0.0  # No other instances to distribute from
        
        # Calculate how close this slot is to existing instances
        min_distance = float('inf')
        for task_slot in similar_tasks:
            distance = abs((slot.start - task_slot.start).total_seconds() / 3600)  # hours
            min_distance = min(min_distance, distance)
        
        # Bonus for being far from other instances (spread out)
        # 24+ hours apart = full bonus, 0 hours = no bonus
        if min_distance >= 24:
            return 0.3  # Good distribution
        elif min_distance >= 12:
            return 0.15  # Moderate distribution
        else:
            return 0.0  # Too close, no bonus

    def _calculate_daily_workload_bonus(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate bonus for respecting daily workload limits.
        Hard limit: Cannot exceed daily maximum.
        """
        slot_date = slot.start.date()
        
        # Calculate current daily workload
        daily_workload_hours = 0
        for s in self.slots:
            if (s.occupant and 
                hasattr(s.occupant, 'id') and  # Check if it's a Quest object
                s.occupant.id != quest.id and
                s.start.date() == slot_date):
                # Add task duration to daily workload
                if hasattr(s.occupant, 'duration_minutes') and s.occupant.duration_minutes:
                    daily_workload_hours += s.occupant.duration_minutes / 60
                else:
                    daily_workload_hours += s.duration().total_seconds() / 3600
        
        # Add current task duration
        quest_duration_hours = quest.duration_minutes / 60 if quest.duration_minutes else 1
        
        # Hard daily limit: 8 hours of focused work per day
        daily_limit_hours = 8.0
        
        # HARD LIMIT: Cannot exceed daily maximum
        if daily_workload_hours + quest_duration_hours > daily_limit_hours:
            return -1000.0  # Very strong penalty - effectively disqualifies the slot
        
        # Bonus for staying well under the limit
        if daily_workload_hours + quest_duration_hours <= daily_limit_hours * 0.8:  # Under 80% of limit
            return 0.2  # Small bonus for not overloading the day
        else:
            return 0.0  # Neutral score when approaching the limit

    def _calculate_weekly_balance_score(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate weekly balance score: encourage placing tasks on days with lower difficulty and workload.
        Looks at the full Monday-Sunday week, not just current day forward.
        """
        slot_date = slot.start.date()
        
        # Find the Monday of the current week (always start from Monday)
        week_start = slot_date - timedelta(days=slot_date.weekday())
        week_end = week_start + timedelta(days=7)
        
        # Calculate workload and difficulty for each day of the week
        weekly_scores = {}
        for i in range(7):
            day_date = week_start + timedelta(days=i)
            weekly_scores[day_date] = {
                'workload_hours': 0,
                'difficulty_score': 0,
                'task_count': 0
            }
        
        # Add existing tasks to weekly scores
        for s in self.slots:
            if (s.occupant and 
                hasattr(s.occupant, 'id') and
                s.occupant.id != quest.id and
                week_start <= s.start.date() < week_end):
                
                day_date = s.start.date()
                
                # Add workload hours
                if hasattr(s.occupant, 'duration_minutes') and s.occupant.duration_minutes:
                    weekly_scores[day_date]['workload_hours'] += s.occupant.duration_minutes / 60
                else:
                    weekly_scores[day_date]['workload_hours'] += s.duration().total_seconds() / 3600
                
                # Add difficulty score (using actual difficulty field)
                if hasattr(s.occupant, 'difficulty'):
                    # Convert QuestDifficulty enum to numeric score
                    difficulty_value = self._get_quest_difficulty_score(s.occupant)
                    weekly_scores[day_date]['difficulty_score'] += difficulty_value
                
                weekly_scores[day_date]['task_count'] += 1
        
        # Add current task to the target day
        quest_duration_hours = quest.duration_minutes / 60 if quest.duration_minutes else 1
        weekly_scores[slot_date]['workload_hours'] += quest_duration_hours
        weekly_scores[slot_date]['difficulty_score'] += self._get_quest_difficulty_score(quest)
        weekly_scores[slot_date]['task_count'] += 1
        
        # Calculate combined score for each day (lower = better)
        day_scores = {}
        for day_date, data in weekly_scores.items():
            # Normalize workload (0-8 hours = 0-1 score)
            workload_score = min(data['workload_hours'] / 8.0, 1.0)
            
            # Normalize difficulty (0-20 difficulty = 0-1 score, assuming max 5 tasks * 4 priority)
            difficulty_score = min(data['difficulty_score'] / 20.0, 1.0)
            
            # Combined score: average of workload and difficulty
            day_scores[day_date] = (workload_score + difficulty_score) / 2
        
        # Get the score for the target day (lower is better)
        target_day_score = day_scores[slot_date]
        
        # Convert to bonus/penalty: lower day score = higher bonus
        # 0.0 day score = +0.5 bonus, 1.0 day score = -0.2 penalty
        weekly_balance_bonus = 0.5 - (target_day_score * 0.7)
        
        return weekly_balance_bonus

    def _calculate_automatic_buffer_bonus(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate bonus for automatic buffer time based on task difficulty and length.
        Ensures adequate breaks between demanding tasks.
        """
        # Calculate task difficulty score (1-5 scale)
        difficulty_score = quest.priority  # Using priority as difficulty proxy
        
        # Calculate task length in hours
        task_length_hours = quest.duration_minutes / 60 if quest.duration_minutes else 1
        
        # Calculate required buffer time based on difficulty and length
        required_buffer_minutes = 0
        
        # Base buffer on task length
        if task_length_hours >= 4:
            required_buffer_minutes = 30  # 30 min buffer for 4+ hour tasks
        elif task_length_hours >= 2:
            required_buffer_minutes = 20  # 20 min buffer for 2+ hour tasks
        elif task_length_hours >= 1:
            required_buffer_minutes = 15  # 15 min buffer for 1+ hour tasks
        else:
            required_buffer_minutes = 10  # 10 min buffer for short tasks
        
        # Increase buffer for high-difficulty tasks
        if difficulty_score >= 4:
            required_buffer_minutes += 15  # Extra 15 min for high-priority tasks
        elif difficulty_score >= 3:
            required_buffer_minutes += 10  # Extra 10 min for medium-high priority tasks
        
        # Check if there's adequate buffer time before this slot
        buffer_start = slot.start - timedelta(minutes=required_buffer_minutes)
        
        # Look for tasks that end too close to our buffer start
        for s in self.slots:
            if (s.occupant and 
                hasattr(s.occupant, 'id') and  # Check if it's a Quest object
                s.occupant.id != quest.id and
                s.end > buffer_start):
                # Task ends too close, not enough buffer
                return -0.3  # Penalty for insufficient buffer
        
        return 0.2  # Bonus for adequate buffer time



    def _calculate_slot_score(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate slot score using weighted formula with proper priorities:
        Deadline first, then daily balance, then weekly optimization
        """
        # HARD CONSTRAINT: Deadline check - if this slot is after deadline, disqualify
        if quest.deadline and slot.start > quest.deadline:
            return -1000.0  # Very strong penalty - effectively disqualifies the slot
        
        # Component 1: Time preference match (W_time = 1.2)
        time_match = self._calculate_time_preference_score(quest, slot)
        
        # Component 2: Urgency/deadline (W_urgency = 0.0) - Urgency handled in task selection order
        urgency = 0.0  # Urgency is now handled in task selection phase, not slot scoring
        
        # Component 3: Priority (W_priority = 0.0) - Priority handled separately in task ordering
        priority = 0.0  # Priority is now handled in task selection phase, not slot scoring
        
        # Component 4: Daily workload balance (W_workload = 1.0)
        daily_workload = self._calculate_daily_workload_bonus(quest, slot)
        
        # Component 5: Weekly balance optimization (W_weekly = 1.0)
        weekly_balance = self._calculate_weekly_balance_score(quest, slot)
        
        # Component 6: Spacing bonus (W_spacing = 0.7)
        spacing_bonus = self._calculate_spacing_bonus(quest, slot)
        
        # Component 7: Difficulty-based workload balancing (W_difficulty = 1.3)
        difficulty_balance = self._calculate_difficulty_workload_balance(quest, slot)
        
        # Component 8: Earlier scheduling bonus (W_earlier = 0.8)
        earlier_bonus = self._calculate_earlier_bonus(quest, slot)
        
        # Apply weights and calculate total score
        total_score = (
            (1000.0 * time_match) +  # Increased to 1000.0 - absolutely dominant
            (0.0 * urgency) +  # Urgency handled in task selection order
            (0.0 * priority) +  # Priority handled separately
            (1.0 * daily_workload) +
            (1.0 * weekly_balance) +
            (0.7 * spacing_bonus) +
            (1.3 * difficulty_balance) +
            (0.8 * earlier_bonus)  # Bonus for scheduling earlier within 2 weeks of deadline
        )
        
        # Debug output for gym workouts
        if "Gym Workout" in quest.title:
            print(f"      🏋️ SLOT SCORE DEBUG: '{quest.title}' slot {slot.start.time()}-{slot.end.time()}")
            print(f"         📊 time_match={time_match} (weighted={1000.0 * time_match})")
            print(f"         📊 daily_workload={daily_workload}, weekly_balance={weekly_balance}")
            print(f"         📊 spacing_bonus={spacing_bonus}, difficulty_balance={difficulty_balance}")
            print(f"         📊 earlier_bonus={earlier_bonus}")
            print(f"         📊 TOTAL SCORE={total_score}")
        
        return total_score



    def _calculate_urgency_score(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate pure deadline-based urgency score.
        Uses deadline for hard constraints, due_at for soft urgency.
        Returns exponentially higher scores for earlier slots to prioritize urgent tasks.
        """
        # Use deadline for urgency scoring (hard constraint)
        deadline_datetime = quest.deadline
        if not deadline_datetime:
            return 0.0
        
        slot_datetime = slot.start
        
        # Calculate hours until deadline from the slot datetime
        hours_until_deadline = (deadline_datetime - slot_datetime).total_seconds() / 3600
        
        # If deadline has passed, return negative score to discourage scheduling
        if hours_until_deadline < 0:
            return -1.0  # Strong penalty: discourage scheduling past deadline
        
        # Pure deadline-based urgency scoring (no priority influence)
        if hours_until_deadline <= 24:  # 1 day or less
            # Very urgent: exponential decay based on hours
            urgency_score = 1.0 - (hours_until_deadline / 24.0) ** 2  # Quadratic decay
            urgency_score = max(0.8, urgency_score)  # Higher minimum for very urgent tasks
        elif hours_until_deadline <= 48:  # 2 days or less
            # Urgent: linear decay
            urgency_score = 0.9 - (hours_until_deadline - 24.0) / 24.0 * 0.4
            urgency_score = max(0.5, urgency_score)
        elif hours_until_deadline <= 72:  # 3 days or less
            # Moderately urgent: gentle decay
            urgency_score = 0.7 - (hours_until_deadline - 48.0) / 24.0 * 0.3
            urgency_score = max(0.3, urgency_score)
        elif hours_until_deadline <= 168:  # 1 week or less
            # Somewhat urgent: very gentle decay
            urgency_score = 0.5 - (hours_until_deadline - 72.0) / 96.0 * 0.2
            urgency_score = max(0.2, urgency_score)
        else:
            # Not urgent: minimal preference
            urgency_score = 0.2 - (hours_until_deadline - 168.0) / 168.0 * 0.1
            urgency_score = max(0.1, urgency_score)
        
        # Apply deadline multiplier for exponential urgency boost
        # The closer to deadline, the more the urgency score is amplified
        if hours_until_deadline <= 24:  # 1 day or less
            deadline_multiplier = 25.0  # 25x boost for very urgent tasks
        elif hours_until_deadline <= 48:  # 2 days or less
            deadline_multiplier = 15.0  # 15x boost for urgent tasks
        elif hours_until_deadline <= 72:  # 3 days or less
            deadline_multiplier = 8.0   # 8x boost for moderately urgent tasks
        elif hours_until_deadline <= 168:  # 1 week or less
            deadline_multiplier = 3.0   # 3x boost for somewhat urgent tasks
        else:
            deadline_multiplier = 1.0   # No boost for non-urgent tasks
        
        # Apply the deadline multiplier
        final_urgency_score = urgency_score * deadline_multiplier
        
        return final_urgency_score

    def _calculate_difficulty_workload_balance(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate difficulty-based workload balancing score.
        Penalizes clustering of difficult tasks on the same day.
        Higher score = better distribution of difficulty across the week.
        """
        # Get the difficulty level of the current quest
        quest_difficulty = self._get_quest_difficulty_score(quest)
        
        # Get the target day for this slot
        target_date = slot.start.date()
        
        # Calculate current difficulty load for the target day
        current_day_difficulty = self._get_day_difficulty_load(target_date)
        
        # Calculate average difficulty across all days
        avg_difficulty = self._get_average_difficulty_across_week()
        
        # Calculate difficulty variance across the week
        difficulty_variance = self._get_difficulty_variance_across_week()
        
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

    def _get_quest_difficulty_score(self, quest: Quest) -> float:
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

    def _get_day_difficulty_load(self, target_date: date) -> float:
        """
        Calculate the total difficulty load for a specific day.
        """
        total_difficulty = 0.0
        
        for slot in self.slots:
            if (slot.occupant and 
                hasattr(slot.occupant, 'id') and 
                slot.start.date() == target_date):
                # This is a scheduled task on the target day
                total_difficulty += self._get_quest_difficulty_score(slot.occupant)
        
        return total_difficulty

    def _get_average_difficulty_across_week(self) -> float:
        """
        Calculate the average difficulty load across all days in the scheduling window.
        """
        total_difficulty = 0.0
        days_with_tasks = 0
        
        # Get all unique dates in the scheduling window
        dates_in_window = set()
        for slot in self.slots:
            if slot.start:
                dates_in_window.add(slot.start.date())
        
        for date in dates_in_window:
            day_difficulty = self._get_day_difficulty_load(date)
            if day_difficulty > 0:
                total_difficulty += day_difficulty
                days_with_tasks += 1
        
        if days_with_tasks == 0:
            return 0.0
        
        return total_difficulty / days_with_tasks

    def _get_difficulty_variance_across_week(self) -> float:
        """
        Calculate the variance in difficulty across the week.
        Higher variance = more uneven distribution.
        """
        avg_difficulty = self._get_average_difficulty_across_week()
        if avg_difficulty == 0:
            return 0.0
        
        total_variance = 0.0
        days_with_tasks = 0
        
        # Get all unique dates in the scheduling window
        dates_in_window = set()
        for slot in self.slots:
            if slot.start:
                dates_in_window.add(slot.start.date())
        
        for date in dates_in_window:
            day_difficulty = self._get_day_difficulty_load(date)
            if day_difficulty > 0:
                variance = ((day_difficulty - avg_difficulty) ** 2)
                total_variance += variance
                days_with_tasks += 1
        
        if days_with_tasks == 0:
            return 0.0
        
        return total_variance / days_with_tasks

    def _calculate_priority_score(self, quest: Quest) -> float:
        """
        Map priority to score: Low: 0.3, Medium: 0.6, High: 1.0, Very High: 1.5+
        """
        if quest.priority == 1:
            return 0.3  # Low priority
        elif quest.priority == 2:
            return 0.6  # Medium priority
        elif quest.priority == 3:
            return 0.8  # Medium-high priority
        elif quest.priority == 4:
            return 1.0  # High priority
        elif quest.priority == 5:
            return 1.2  # Very high priority
        elif quest.priority == 6:
            return 1.5  # Extremely high priority
        else:
            return 0.5  # Default

    def _calculate_task_selection_priority(self, quest: Quest) -> float:
        """
        Calculate task selection priority combining priority, urgency, and frequency.
        Higher score = higher priority for task selection order.
        """
        # Base priority score (0.3 - 1.0)
        priority_score = self._calculate_priority_score(quest)
        
        # Urgency score based on deadline proximity
        urgency_score = self._calculate_deadline_urgency_score(quest)
        
        # Frequency bonus for recurring tasks
        frequency_score = self._calculate_frequency_score(quest)
        
        # Combine scores with weights
        # Priority is most important (50%), then urgency (40%), then frequency (10%)
        total_score = (
            (0.5 * priority_score) +
            (0.4 * urgency_score) +
            (0.1 * frequency_score)
        )
        
        return total_score

    def _calculate_deadline_urgency_score(self, quest: Quest) -> float:
        """
        Calculate urgency score based on deadline proximity (0.0 - 1.0).
        Higher score = closer to deadline = more urgent.
        """
        deadline_datetime = quest.deadline
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

    def _calculate_frequency_score(self, quest: Quest) -> float:
        """
        Calculate frequency score for recurring tasks (0.0 - 1.0).
        Higher score = more frequent = higher priority.
        """
        if not quest.recurrence_rule:
            return 0.0  # Not recurring
        
        # Parse recurrence rule to determine frequency
        if "FREQ=DAILY" in quest.recurrence_rule:
            return 1.0  # Daily tasks get highest frequency score
        elif "FREQ=WEEKLY" in quest.recurrence_rule:
            return 0.8  # Weekly tasks get high frequency score
        elif "FREQ=MONTHLY" in quest.recurrence_rule:
            return 0.6  # Monthly tasks get medium frequency score
        elif "FREQ=YEARLY" in quest.recurrence_rule:
            return 0.4  # Yearly tasks get low frequency score
        else:
            return 0.5  # Unknown frequency, default medium

    def _calculate_earlier_bonus(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate bonus for scheduling tasks earlier than their deadline.
        Only applies when within 2 weeks of deadline to encourage earlier scheduling.
        Returns 0.0 if more than 2 weeks from deadline.
        """
        deadline_datetime = quest.deadline
        if not deadline_datetime:
            return 0.0
        
        # Calculate days until deadline from the slot start time
        days_until_deadline = (deadline_datetime - slot.start).days
        
        # Only apply bonus if within 2 weeks (14 days) of deadline
        if days_until_deadline > 14:
            return 0.0
        
        # Calculate bonus: more days before deadline = higher bonus
        # Max bonus (1.0) when 14 days before deadline
        # Min bonus (0.0) when at deadline
        if days_until_deadline >= 0:
            # Linear bonus from 0.0 to 1.0 over 14 days
            bonus = days_until_deadline / 14.0
            return bonus
        else:
            # Negative days means past deadline - no bonus
            return 0.0

    def _calculate_workload_density_score(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate workload density: 1 - (num_tasks_scheduled_on_day / max_daily_capacity)
        Rewards open days
        """
        slot_date = slot.start.date()
        
        # Count tasks already scheduled on this day
        num_tasks_on_day = 0
        for s in self.slots:
            if (s.occupant and 
                hasattr(s.occupant, 'id') and  # Check if it's a Quest object
                s.occupant.id != quest.id and
                s.start.date() == slot_date):
                num_tasks_on_day += 1
        
        # Add current task
        num_tasks_on_day += 1
        
        # Set maximum daily capacity (8 hours of focused work)
        max_daily_capacity = 8.0
        
        # Calculate density
        density = num_tasks_on_day / max_daily_capacity
        
        # Return reverse density to reward open days
        return max(0.0, 1.0 - density)

    def _calculate_spacing_bonus(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate spacing bonus for recurring tasks
        For daily tasks: prioritize exactly 24 hours apart (same time each day)
        For weekly tasks: score higher if well-spaced from other instances
        """
        if not quest.recurrence_rule:
            return 0.0  # Not a recurring task
        
        # Check if this is a daily recurring task
        is_daily = "FREQ=DAILY" in quest.recurrence_rule
        
        # Find other instances of the same task type
        similar_tasks = []
        for s in self.slots:
            if (s.occupant and 
                hasattr(s.occupant, 'id') and  # Check if it's a Quest object
                s.occupant.id != quest.id and 
                hasattr(s.occupant, 'title') and  # Check if it has a title
                s.occupant.title == quest.title):
                similar_tasks.append(s)
        
        if not similar_tasks:
            return 0.5  # No other instances, moderate bonus
        
        # For daily tasks: prioritize exactly 24 hours apart (same time each day)
        if is_daily:
            # Find the most recent instance
            most_recent = max(similar_tasks, key=lambda s: s.start)
            
            # Calculate time difference in hours
            time_diff_hours = abs((slot.start - most_recent.start).total_seconds() / 3600)
            
            # Perfect 24-hour spacing gets maximum bonus
            if 23.5 <= time_diff_hours <= 24.5:  # Allow 30-minute tolerance
                return 1.0  # Perfect daily spacing
            elif 22 <= time_diff_hours <= 26:  # Allow 2-hour tolerance
                return 0.7  # Good daily spacing
            elif 20 <= time_diff_hours <= 28:  # Allow 4-hour tolerance
                return 0.3  # Acceptable daily spacing
            else:
                return 0.0  # Poor daily spacing
        
        # For weekly tasks: use the original spacing logic
        else:
            # Calculate minimum distance to other instances
            min_distance = float('inf')
            for task_slot in similar_tasks:
                distance = abs((slot.start - task_slot.start).total_seconds() / 3600)  # hours
                min_distance = min(min_distance, distance)
            
            # Score based on spacing
            if min_distance >= 24:
                return 1.0  # Well spaced (24+ hours)
            elif min_distance >= 12:
                return 0.7  # Moderately spaced (12+ hours)
            elif min_distance >= 6:
                return 0.3  # Somewhat spaced (6+ hours)
            else:
                return 0.0  # Too close

    def _calculate_time_preference_score(self, quest: Quest, slot: CleanTimeSlot) -> float:
        """
        Calculate score for time preferences with 3-tier scoring system:
        1. Expected window (highest score): exact expected_start to expected_end
        2. Soft window (medium score): soft_start to soft_end  
        3. Hard window (low score): hard_start to hard_end
        4. Outside hard window: reject (0.0)
        
        Also considers preferred_time_of_day as a separate scoring component.
        """
        slot_start_time = slot.start.time()
        slot_end_time = slot.end.time()
        
        # Convert times to minutes for easier comparison
        slot_start_minutes = slot_start_time.hour * 60 + slot_start_time.minute
        slot_end_minutes = slot_end_time.hour * 60 + slot_end_time.minute
        
        # Handle FIXED flexibility with hard_start and hard_end constraints
        if quest.scheduling_flexibility == SchedulingFlexibility.FIXED:
            if quest.hard_start and quest.hard_end:
                # Check if slot exactly matches the hard_start and hard_end times
                if slot_start_time == quest.hard_start and slot_end_time == quest.hard_end:
                    return 1.0  # Perfect score for exact match
                else:
                    return 0.0  # Reject if not exact match
        
        # 3-tier time window scoring system
        time_window_score = 0.0
        
        # Check if we have any time window constraints
        has_time_constraints = (quest.expected_start or quest.expected_end or 
                              quest.soft_start or quest.soft_end or 
                              quest.hard_start or quest.hard_end)
        
        if has_time_constraints:
            # Convert constraint times to minutes
            expected_start_minutes = (quest.expected_start.hour * 60 + quest.expected_start.minute) if quest.expected_start else None
            expected_end_minutes = (quest.expected_end.hour * 60 + quest.expected_end.minute) if quest.expected_end else None
            soft_start_minutes = (quest.soft_start.hour * 60 + quest.soft_start.minute) if quest.soft_start else None
            soft_end_minutes = (quest.soft_end.hour * 60 + quest.soft_end.minute) if quest.soft_end else None
            hard_start_minutes = (quest.hard_start.hour * 60 + quest.hard_start.minute) if quest.hard_start else None
            hard_end_minutes = (quest.hard_end.hour * 60 + quest.hard_end.minute) if quest.hard_end else None
            
            # Check if slot is within hard window (must pass this)
            if hard_start_minutes is not None and slot_start_minutes < hard_start_minutes:
                return 0.0  # Reject - starts too early
            if hard_end_minutes is not None and slot_end_minutes > hard_end_minutes:
                return 0.0  # Reject - ends too late
            
            # 3-tier scoring - check BOTH start and end times
            if (expected_start_minutes is not None and expected_end_minutes is not None and
                slot_start_minutes >= expected_start_minutes and slot_end_minutes <= expected_end_minutes):
                time_window_score = 100.0  # ⭐⭐⭐ Perfect - within expected window (increased from 10.0 to 100.0)
            elif (soft_start_minutes is not None and soft_end_minutes is not None and
                  slot_start_minutes >= soft_start_minutes and slot_end_minutes <= soft_end_minutes):
                time_window_score = 0.5  # ⭐⭐ Good - within soft window (reduced from 0.7)
            elif (hard_start_minutes is not None and hard_end_minutes is not None and
                  slot_start_minutes >= hard_start_minutes and slot_end_minutes <= hard_end_minutes):
                time_window_score = 0.1  # ⭐ Acceptable - within hard window (reduced from 0.3)
            else:
                time_window_score = 0.0  # ❌ Reject - outside all windows
        
        # Handle WINDOW flexibility - must have time window constraints
        if quest.scheduling_flexibility == SchedulingFlexibility.WINDOW:
            if not has_time_constraints:
                return 0.0  # WINDOW tasks must have time constraints
            print(f"      🎯 TIME PREFERENCE: '{quest.title}' slot {slot.start.time()}-{slot.end.time()} = {time_window_score}")
            print(f"         📊 DEBUG: expected={expected_start_minutes}-{expected_end_minutes}, soft={soft_start_minutes}-{soft_end_minutes}, hard={hard_start_minutes}-{hard_end_minutes}")
            print(f"         📊 DEBUG: slot_start={slot_start_minutes}, slot_end={slot_end_minutes}")
            return time_window_score  # Use the 3-tier score directly
        
        # For other flexibility types, combine time window score with time of day preference
        time_of_day_score = 0.5  # Default neutral score
        
        if quest.preferred_time_of_day and quest.preferred_time_of_day != PreferredTimeOfDay.NO_PREFERENCE:
            slot_start_hour = slot.start.hour
            
            # Check if we should allow deviation from preferred time
            allow_deviation = quest.allow_time_deviation or quest.scheduling_flexibility == SchedulingFlexibility.FLEXIBLE
            
            if quest.preferred_time_of_day == PreferredTimeOfDay.MORNING:
                if 6 <= slot_start_hour < 12:
                    time_of_day_score = 1.0
                elif allow_deviation and (5 <= slot_start_hour < 14):
                    time_of_day_score = 0.7
                else:
                    time_of_day_score = 0.3
            elif quest.preferred_time_of_day == PreferredTimeOfDay.AFTERNOON:
                if 12 <= slot_start_hour < 18:
                    time_of_day_score = 1.0
                elif allow_deviation and (10 <= slot_start_hour < 20):
                    time_of_day_score = 0.7
                else:
                    time_of_day_score = 0.3
            elif quest.preferred_time_of_day == PreferredTimeOfDay.EVENING:
                if 18 <= slot_start_hour < 23:
                    time_of_day_score = 1.0
                elif allow_deviation and (16 <= slot_start_hour < 24):
                    time_of_day_score = 0.7
                else:
                    time_of_day_score = 0.3
        
        # Combine scores: if we have time window constraints, prioritize them
        if has_time_constraints:
            return time_window_score
        else:
            return time_of_day_score

    def _should_allow_time_deviation(self, quest: Quest) -> bool:
        """
        Determine if a quest should be allowed to deviate from its preferred time.
        By default, NO deviation is allowed unless explicitly configured.
        """
        # Check if quest has explicit permission to deviate
        # This would be a new field like quest.allow_time_deviation
        if hasattr(quest, 'allow_time_deviation') and quest.allow_time_deviation:
            return True
        
        # Check if quest has explicit permission for urgent override
        # This would be a new field like quest.allow_urgent_override
        if hasattr(quest, 'allow_urgent_override') and quest.allow_urgent_override:
            # Only allow deviation for very urgent deadlines (within 12 hours)
            if quest.deadline:
                time_until_deadline = quest.deadline - datetime.now()
                if time_until_deadline.total_seconds() <= 12 * 3600:  # 12 hours
                    return True
        
        return False

    def schedule_task_at_exact_time(self, quest: Quest, exact_start_time: datetime, duration: timedelta) -> List[CleanTimeSlot]:
        """
        Schedule a task at an exact time, creating separate slots for each component.
        Returns list of created slots (task + buffers).
        """
        return self.schedule_task_with_buffers(quest, duration, exact_start_time)

    def _replace_slot(self, old_slot: CleanTimeSlot, new_slots: List[CleanTimeSlot]):
        """Replace one slot with multiple new slots"""
        # Find the slot by time range and occupant type rather than object identity
        slot_index = None
        
        # First, try to find an exact match
        for i, slot in enumerate(self.slots):
            # Match by time range and occupant type
            if (slot.start == old_slot.start and 
                slot.end == old_slot.end and 
                type(slot.occupant) == type(old_slot.occupant)):
                
                # For AVAILABLE slots, just check the occupant type
                if old_slot.occupant == AVAILABLE:
                    if slot.occupant == AVAILABLE:
                        slot_index = i
                        break
                # For other occupants, check if they're the same object or have the same title
                elif hasattr(old_slot.occupant, 'title') and hasattr(slot.occupant, 'title'):
                    if (slot.occupant.title == old_slot.occupant.title or 
                        slot.occupant == old_slot.occupant):
                        slot_index = i
                        break
                # For string occupants (like "BUFFER"), check exact match
                elif isinstance(old_slot.occupant, str) and slot.occupant == old_slot.occupant:
                    slot_index = i
                    break
        
        # If no exact match, try to find a slot that contains the time range
        if slot_index is None:
            for i, slot in enumerate(self.slots):
                if (slot.start <= old_slot.start and slot.end >= old_slot.end and
                    slot.occupant == AVAILABLE):
                    slot_index = i
                    print(f"🔧 FOUND CONTAINING SLOT: {slot} contains {old_slot}")
                    break
        
        # If still no match, try a more lenient search by just time range
        if slot_index is None:
            for i, slot in enumerate(self.slots):
                if (slot.start == old_slot.start and slot.end == old_slot.end):
                    slot_index = i
                    print(f"🔧 FOUND SLOT BY TIME RANGE ONLY: {slot}")
                    break
        
        if slot_index is None:

            for i, slot in enumerate(self.slots):
                if (slot.start <= old_slot.end and slot.end >= old_slot.start and
                    slot.occupant == AVAILABLE):
                    print(f"   Slot {i}: {slot.start} - {slot.end} ({slot.occupant})")
            return
        
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
            if (slot.occupant == AVAILABLE and 
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

    def _displace_lower_priority_tasks(self, quest: Quest, required_duration: timedelta) -> Optional[CleanTimeSlot]:
        """
        Comprehensive displacement system that evaluates single and multi-event displacements using scoring.
        Returns the optimal slot after displacement, or None if no effective displacement possible.
        """
        if not quest.priority:
            return None
        
        quest_priority = quest.priority
        
        # Find all displaceable tasks
        displaceable_tasks = []
        for slot in self.slots:
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
            score = self._evaluate_single_displacement(quest, slot, required_duration)
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
                score = self._evaluate_multi_displacement(quest, list(task_combination), required_duration)
                task_names = [slot.occupant.title for slot in task_combination]
                print(f"      📈 Multi displacement score for {task_names}: {score}")
                if score > best_score:
                    best_score = score
                    best_displacement = (list(task_combination), score)
                    print(f"      ✅ New best multi displacement: {task_names} (score: {score})")
        
        # If we found a good displacement, perform it
        if best_displacement and best_score > 0:  # Only displace if score is positive
            slots_to_displace, score = best_displacement
            return self._perform_comprehensive_displacement(quest, slots_to_displace, required_duration)
        
        return None
    
    def _evaluate_single_displacement(self, quest: Quest, slot_to_displace: CleanTimeSlot, required_duration: timedelta) -> float:
        """Evaluate the score for displacing a single task."""
        displaced_task = slot_to_displace.occupant
        
        # Check if there's enough time around this slot
        total_available_time = self._find_available_time_around_slot(slot_to_displace)
        if total_available_time < required_duration:
            return float('-inf')  # Not enough time
        
        # Find the optimal slot that would be created
        # Temporarily remove the task to test
        original_occupant = slot_to_displace.occupant
        slot_to_displace.occupant = AVAILABLE
        self._merge_adjacent_available_slots()
        
        optimal_slot = self._find_optimal_slot(quest, required_duration)
        
        # Restore the task
        slot_to_displace.occupant = original_occupant
        self._merge_adjacent_available_slots()
        
        if not optimal_slot:
            return float('-inf')
        
        # Calculate displacement score
        displacement_score = self._calculate_displacement_score(quest, optimal_slot, displaced_task, slot_to_displace)
        
        # Add reschedulability penalty
        reschedule_penalty = self._calculate_reschedule_difficulty(displaced_task)
        
        total_score = displacement_score - reschedule_penalty
        print(f"         📊 Displacement score: {displacement_score}, Reschedule penalty: {reschedule_penalty}, Total: {total_score}")
        
        return total_score
    
    def _evaluate_multi_displacement(self, quest: Quest, slots_to_displace: List[CleanTimeSlot], required_duration: timedelta) -> float:
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
        
        self._merge_adjacent_available_slots()
        
        optimal_slot = self._find_optimal_slot(quest, required_duration)
        
        # Restore all tasks
        for slot, occupant in zip(slots_to_displace, original_occupants):
            slot.occupant = occupant
        self._merge_adjacent_available_slots()
        
        if not optimal_slot:
            return float('-inf')
        
        # Calculate base displacement score (sum of individual scores)
        total_displacement_score = 0
        total_reschedule_penalty = 0
        
        for slot, task in zip(slots_to_displace, displaced_tasks):
            individual_score = self._calculate_displacement_score(quest, optimal_slot, task, slot)
            total_displacement_score += individual_score
            total_reschedule_penalty += self._calculate_reschedule_difficulty(task)
        
        # Multi-displacement penalty (displacing multiple tasks is harder)
        multi_penalty = len(slots_to_displace) * 0.5
        
        return total_displacement_score - total_reschedule_penalty - multi_penalty
    
    def _calculate_reschedule_difficulty(self, task: Quest) -> float:
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
    
    def _perform_comprehensive_displacement(self, quest: Quest, slots_to_displace: List[CleanTimeSlot], required_duration: timedelta) -> Optional[CleanTimeSlot]:
        """Actually perform the displacement and return the optimal slot."""
        displaced_tasks = []
        
        # Remove all tasks to be displaced
        for slot in slots_to_displace:
            displaced_tasks.append((slot, slot.occupant))
            slot.occupant = AVAILABLE
        
        # Merge adjacent slots
        self._merge_adjacent_available_slots()
        
        # Find the optimal slot for the new quest
        optimal_slot = self._find_optimal_slot(quest, required_duration)
        if not optimal_slot:
            # Restore displaced tasks if we can't find a slot
            for slot, task in displaced_tasks:
                slot.occupant = task
            self._merge_adjacent_available_slots()
            return None
        
        # Reserve the optimal slot by temporarily marking it as occupied
        original_optimal_occupant = optimal_slot.occupant
        optimal_slot.occupant = "RESERVED"
        
        # Reschedule all displaced tasks
        failed_reschedules = []
        for slot, displaced_task in displaced_tasks:
            print(f'      🔄 Rescheduling displaced task: {displaced_task.title} (original slot: {slot.start.strftime("%Y-%m-%d %H:%M")}-{slot.end.strftime("%H:%M")})')
            displaced_duration = timedelta(minutes=displaced_task.duration_minutes or 60)
            reschedule_result = self.schedule_task_with_buffers(displaced_task, displaced_duration)
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
        self._merge_adjacent_available_slots()
        
        print(f'      ✅ Displacement successful: {len(displaced_tasks)} tasks displaced, {len(failed_reschedules)} failed to reschedule')
        return optimal_slot
    
    def _find_available_time_around_slot(self, task_slot: CleanTimeSlot) -> timedelta:
        """
        Find the total available time around a task slot (including the task's own duration).
        This uses the same logic as the working method in metaheuristic.py.
        """
        # Start with the task's own duration
        total_available = task_slot.duration()
        
        # Look for AVAILABLE slots that are adjacent to this task
        for slot in self.slots:
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
    
    def _calculate_displacement_score(self, new_quest: Quest, new_slot: CleanTimeSlot, 
                                    displaced_task: Quest, original_slot: CleanTimeSlot) -> float:
        """
        Calculate the score for a displacement decision.
        Higher score = better displacement choice.
        """
        # Base score: priority difference (higher is better) - INCREASED WEIGHT
        priority_diff = (new_quest.priority - displaced_task.priority) * 5  # Increased from 2 to 5
        
        # Time preference bonus for new task
        time_pref_bonus = self._calculate_time_preference_score(new_quest, new_slot)
        
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
        current_slot_quality = self._calculate_time_preference_score(displaced_task, original_slot)
        slot_quality_bonus = current_slot_quality * 0.5  # Reduce penalty if current slot is poor
        
        # Add a small positive base score to encourage displacement when beneficial
        base_score = 0.1
        
        total_score = (priority_diff + time_pref_bonus + deadline_penalty + 
                      flexibility_penalty + duration_penalty + slot_quality_bonus + base_score)
        
        return total_score



    def _should_chunk_task(self, quest: Quest, duration: timedelta) -> bool:
        """
        Determine if a task should be chunked based on its duration, deadline, and available slots.
        """
        # Don't chunk if task is already chunked
        if getattr(quest, 'is_chunked', False):
            return False
        
        # Don't chunk if chunking is explicitly disabled
        if not getattr(quest, 'allow_chunking', True):
            return False
        
        # Check if task has a specific chunk preference that should force chunking
        chunk_preference = getattr(quest, 'chunk_preference', None)
        if chunk_preference and chunk_preference in ['deadline_aware', 'front_loaded', 'user_preference']:
            return True
        
        # Don't chunk very short tasks (less than 2 hours)
        if duration.total_seconds() / 3600 < 2:
            return False
        
        # ALWAYS chunk tasks longer than 4 hours, regardless of available slots
        if duration.total_seconds() / 3600 >= 4:
            return True
        
        # For tasks 2-4 hours, check if they can fit in available slots
        total_duration = duration + timedelta(minutes=getattr(quest, 'buffer_before', 0) + getattr(quest, 'buffer_after', 0))
        
        for slot in self.slots:
            if (slot.occupant == AVAILABLE and 
                slot.duration() >= total_duration):
                return False  # Can fit in one slot, no need to chunk
        
        # Task is too long for any single slot, should be chunked
        return True

    def _schedule_chunked_task(self, quest: Quest, duration: timedelta, exact_start_time: datetime = None) -> List[CleanTimeSlot]:
        """
        Schedule a task using study-focused chunking with deadline-aware day distribution.
        Supports multiple chunking strategies and pomodoro intervals.
        """
        # Calculate chunking strategy
        chunk_strategy = self._calculate_chunk_strategy(quest, duration)
        chunk_count = chunk_strategy['chunk_count']
        chunk_minutes = chunk_strategy['chunk_minutes']
        remaining_minutes = chunk_strategy['remaining_minutes']
        strategy = chunk_strategy['strategy']
        days_available = chunk_strategy.get('days_available', 1)
        
        # Store strategy in quest for chunk creation
        quest.chunk_strategy = chunk_strategy
        
        scheduled_slots = []
        
        # Handle different chunking strategies
        if strategy == 'front_loaded' and 'chunk_sizes' in chunk_strategy:
            # Front-loaded strategy with variable chunk sizes
            scheduled_slots = self._schedule_front_loaded_chunks(quest, chunk_strategy)
        else:
            # Standard chunking with day distribution
            scheduled_slots = self._schedule_standard_chunks(quest, chunk_strategy)
        
        return scheduled_slots
    
    def _schedule_standard_chunks(self, quest: Quest, chunk_strategy: dict) -> List[CleanTimeSlot]:
        """Schedule standard chunks with day distribution."""
        chunk_count = chunk_strategy['chunk_count']
        chunk_minutes = chunk_strategy['chunk_minutes']
        remaining_minutes = chunk_strategy['remaining_minutes']
        days_available = chunk_strategy.get('days_available', 1)
        
        # Calculate target days for each chunk (distribute evenly)
        target_days = self._calculate_chunk_distribution_days(quest, chunk_count, days_available)
        
        scheduled_slots = []
        failed_chunks = []
        
        # Schedule each chunk on its target day
        for chunk_index in range(chunk_count):
            # Calculate chunk duration (last chunk gets remaining minutes)
            if chunk_index == chunk_count - 1 and remaining_minutes > 0:
                chunk_duration = timedelta(minutes=chunk_minutes + remaining_minutes)
            else:
                chunk_duration = timedelta(minutes=chunk_minutes)
            
            # Create chunk quest with numbering
            chunk_quest = self._create_chunk_quest(quest, chunk_index + 1, chunk_count, chunk_duration)
            
            # Get target day for this chunk
            target_day = target_days[chunk_index]
            
            # Try to schedule this chunk on the target day
            chunk_slots = self._schedule_chunk_on_target_day(chunk_quest, chunk_duration, target_day)
            
            if chunk_slots:
                scheduled_slots.extend(chunk_slots)
                print(f"   ✅ Chunk {chunk_index + 1}/{chunk_count} scheduled on {target_day.strftime('%Y-%m-%d')}")
            else:
                failed_chunks.append(chunk_index + 1)
                print(f"   ❌ Chunk {chunk_index + 1}/{chunk_count} failed to schedule on {target_day.strftime('%Y-%m-%d')}")
        
        # If any chunks failed, log the conflict
        if failed_chunks:
            print(f"⚠️ CHUNK SCHEDULING CONFLICTS: {quest.title}")
            print(f"   Failed chunks: {failed_chunks}")
        
        return scheduled_slots
    
    def _schedule_front_loaded_chunks(self, quest: Quest, chunk_strategy: dict) -> List[CleanTimeSlot]:
        """Schedule front-loaded chunks with variable sizes."""
        chunk_sizes = chunk_strategy['chunk_sizes']
        days_available = chunk_strategy.get('days_available', 1)
        
        # Calculate target days (larger chunks get earlier days)
        target_days = self._calculate_chunk_distribution_days(quest, len(chunk_sizes), days_available)
        
        scheduled_slots = []
        
        for chunk_index, chunk_size in enumerate(chunk_sizes):
            chunk_duration = timedelta(minutes=chunk_size)
            chunk_quest = self._create_chunk_quest(quest, chunk_index + 1, len(chunk_sizes), chunk_duration)
            
            target_day = target_days[chunk_index]
            chunk_slots = self._schedule_chunk_on_target_day(chunk_quest, chunk_duration, target_day)
            
            if chunk_slots:
                scheduled_slots.extend(chunk_slots)
                print(f"   ✅ Front-loaded chunk {chunk_index + 1}/{len(chunk_sizes)} ({chunk_size}min) scheduled on {target_day.strftime('%Y-%m-%d')}")
            else:
                print(f"   ❌ Front-loaded chunk {chunk_index + 1}/{len(chunk_sizes)} failed to schedule")
        
        return scheduled_slots
    

    
    def _calculate_chunk_distribution_days(self, quest: Quest, chunk_count: int, days_available: int) -> List[datetime]:
        """Calculate target days for chunk distribution."""
        # Use scheduler window start instead of today
        window_start_date = self.window_start.date()
        target_days = []
        
        # Distribute chunks evenly across available days
        for i in range(chunk_count):
            day_offset = i % days_available
            target_day = window_start_date + timedelta(days=day_offset)
            target_days.append(target_day)
        
        return target_days
    
    def _schedule_chunk_on_target_day(self, chunk_quest: Quest, chunk_duration: timedelta, target_day: datetime) -> List[CleanTimeSlot]:
        """Schedule a chunk on a specific target day."""
        # Find available slots on the target day
        available_slots = []
        for slot in self.slots:
            if (slot.occupant == AVAILABLE and 
                slot.start.date() == target_day and 
                slot.duration() >= chunk_duration):
                available_slots.append(slot)
        
        if not available_slots:
            return []
        
        # Find the best slot on the target day
        best_slot = None
        best_score = -1
        
        for slot in available_slots:
            # Check if this slot is allowed for the quest
            if not self._is_slot_allowed(chunk_quest, slot):
                continue  # Skip slots that don't meet constraints
            
            score = self._calculate_slot_score(chunk_quest, slot)
            if score > best_score:
                best_score = score
                best_slot = slot
        
        if best_slot:
            return self._schedule_in_slot(chunk_quest, chunk_duration, best_slot,
                                        getattr(chunk_quest, 'buffer_before', 0) or 0,
                                        getattr(chunk_quest, 'buffer_after', 0) or 0)
        
        return []

    def _calculate_chunk_strategy(self, quest: Quest, duration: timedelta) -> dict:
        """
        Study-focused chunking strategy that considers deadline constraints and user preferences.
        Supports multiple strategies: fixed-size, deadline-aware, front-loaded, pomodoro-style, and adaptive fallback.
        """
        total_minutes = int(duration.total_seconds() / 60)
        
        # Get user preferences and task properties
        chunk_preference = getattr(quest, 'chunk_preference', 'adaptive')
        deadline = quest.deadline
        
        print(f"🔍 STUDY CHUNKING: {quest.title} - {total_minutes} minutes")
        print(f"   ⚙️ Chunk preference: {chunk_preference}")
        
        # Calculate available days until deadline
        days_available = self._calculate_days_until_deadline(quest) if deadline else 1
        
        # Select and apply chunking strategy
        if chunk_preference == 'fixed_size':
            strategy_result = self._calculate_fixed_size_chunks(total_minutes, days_available)
        elif chunk_preference == 'deadline_aware':
            strategy_result = self._calculate_deadline_aware_chunks(total_minutes, days_available, deadline)
        elif chunk_preference == 'front_loaded':
            strategy_result = self._calculate_front_loaded_chunks(total_minutes, days_available)

        elif chunk_preference == 'user_preference':
            strategy_result = self._calculate_user_preference_chunks(total_minutes, days_available, quest)
        else:  # adaptive fallback
            strategy_result = self._calculate_adaptive_chunks(total_minutes, days_available, quest)
        

        
        return strategy_result
    
    def _calculate_days_until_deadline(self, quest: Quest) -> int:
        """Calculate available days until deadline."""
        if not quest.deadline:
            return 1
        
        window_start_date = self.window_start.date()
        deadline_date = quest.deadline.date()
        days_until = (deadline_date - window_start_date).days
        
        # Ensure at least 1 day, cap at 30 days for reasonable chunking
        return max(1, min(30, days_until))
    
    def _calculate_fixed_size_chunks(self, total_minutes: int, days_available: int) -> dict:
        """Fixed-size chunking strategy (default 2 hours)."""
        chunk_minutes = 120  # 2 hours
        chunk_count = (total_minutes + chunk_minutes - 1) // chunk_minutes
        remaining_minutes = total_minutes % chunk_minutes
        if remaining_minutes == 0:
            remaining_minutes = chunk_minutes
        
        return {
            'chunk_count': chunk_count,
            'chunk_minutes': chunk_minutes,
            'remaining_minutes': remaining_minutes,
            'strategy': 'fixed_size',
            'days_available': days_available
        }
    
    def _calculate_deadline_aware_chunks(self, total_minutes: int, days_available: int, deadline: datetime) -> dict:
        """Deadline-aware even spread across available days."""
        # Calculate ideal minutes per day
        minutes_per_day = total_minutes / days_available
        
        # Round to reasonable chunk sizes (30min to 4 hours)
        if minutes_per_day <= 30:
            chunk_minutes = 30
        elif minutes_per_day <= 60:
            chunk_minutes = 60
        elif minutes_per_day <= 120:
            chunk_minutes = 120
        elif minutes_per_day <= 240:
            chunk_minutes = 240
        else:
            chunk_minutes = 240  # Cap at 4 hours per day
        
        chunk_count = (total_minutes + chunk_minutes - 1) // chunk_minutes
        remaining_minutes = total_minutes % chunk_minutes
        if remaining_minutes == 0:
            remaining_minutes = chunk_minutes
        
        return {
            'chunk_count': chunk_count,
            'chunk_minutes': chunk_minutes,
            'remaining_minutes': remaining_minutes,
            'strategy': 'deadline_aware',
            'days_available': days_available
        }
    
    def _calculate_front_loaded_chunks(self, total_minutes: int, days_available: int) -> dict:
        """Front-loaded strategy: larger chunks earlier, smaller chunks later."""
        # Start with 3-hour chunks, then 2-hour, then 1-hour
        if days_available >= 3:
            chunk_sizes = [180, 120, 60]  # 3h, 2h, 1h
        elif days_available >= 2:
            chunk_sizes = [180, 120]  # 3h, 2h
        else:
            chunk_sizes = [120]  # 2h
        
        chunks = []
        remaining = total_minutes
        
        for chunk_size in chunk_sizes:
            while remaining >= chunk_size and len(chunks) < days_available:
                chunks.append(chunk_size)
                remaining -= chunk_size
        
        # Handle remaining minutes
        if remaining > 0:
            chunks.append(remaining)
        
        return {
            'chunk_count': len(chunks),
            'chunk_minutes': chunks[0] if chunks else 120,
            'remaining_minutes': chunks[-1] if len(chunks) > 1 else 0,
            'chunk_sizes': chunks,  # Variable chunk sizes
            'strategy': 'front_loaded',
            'days_available': days_available
        }
    

    
    def _calculate_user_preference_chunks(self, total_minutes: int, days_available: int, quest: Quest) -> dict:
        """User preference-based chunking."""
        preference = getattr(quest, 'chunk_size_preference', 'medium')
        
        if preference == 'large':
            chunk_minutes = 240  # 4 hours
        elif preference == 'medium':
            chunk_minutes = 120  # 2 hours
        elif preference == 'small':
            chunk_minutes = 60   # 1 hour
        else:
            chunk_minutes = 120  # Default to medium
        
        # Check if chunks fit in available days
        if chunk_minutes * days_available < total_minutes:
            # Fall back to adaptive sizing
            return self._calculate_adaptive_chunks(total_minutes, days_available, quest)
        
        chunk_count = (total_minutes + chunk_minutes - 1) // chunk_minutes
        remaining_minutes = total_minutes % chunk_minutes
        if remaining_minutes == 0:
            remaining_minutes = chunk_minutes
        
        return {
            'chunk_count': chunk_count,
            'chunk_minutes': chunk_minutes,
            'remaining_minutes': remaining_minutes,
            'strategy': 'user_preference',
            'days_available': days_available
        }
    
    def _calculate_adaptive_chunks(self, total_minutes: int, days_available: int, quest: Quest) -> dict:
        """Adaptive fallback: automatically adjust chunk size based on constraints."""
        # Start with ideal chunk size
        ideal_chunk_minutes = total_minutes / days_available
        
        # Round to reasonable sizes
        if ideal_chunk_minutes <= 30:
            chunk_minutes = 30
        elif ideal_chunk_minutes <= 60:
            chunk_minutes = 60
        elif ideal_chunk_minutes <= 120:
            chunk_minutes = 120
        elif ideal_chunk_minutes <= 240:
            chunk_minutes = 240
        else:
            chunk_minutes = 240  # Cap at 4 hours
        
        # Ensure we don't exceed available days
        max_chunks = days_available
        if chunk_minutes * max_chunks < total_minutes:
            chunk_minutes = total_minutes // max_chunks
            chunk_minutes = max(30, chunk_minutes)  # Minimum 30 minutes
        
        chunk_count = (total_minutes + chunk_minutes - 1) // chunk_minutes
        remaining_minutes = total_minutes % chunk_minutes
        if remaining_minutes == 0:
            remaining_minutes = chunk_minutes
        
        return {
            'chunk_count': chunk_count,
            'chunk_minutes': chunk_minutes,
            'remaining_minutes': remaining_minutes,
            'strategy': 'adaptive_fallback',
            'days_available': days_available
        }
    


    def _create_chunk_quest(self, original_quest: Quest, chunk_index: int, chunk_count: int, chunk_duration: timedelta) -> Quest:
        """
        Create a chunk quest from the original quest with proper parent-child relationship.
        Enhanced for study sessions with pomodoro structure.
        """
        # Determine the title based on chunking strategy
        chunk_strategy = getattr(original_quest, 'chunk_strategy', {})
        strategy = chunk_strategy.get('strategy', 'unknown')
        
        if chunk_count > 1:
            # Strategy-based labeling
            if strategy == 'deadline_aware':
                title = f"{original_quest.title} (Study Session {chunk_index}/{chunk_count})"
            elif strategy == 'pomodoro_style':
                title = f"{original_quest.title} (Pomodoro {chunk_index}/{chunk_count})"
            elif strategy == 'front_loaded':
                title = f"{original_quest.title} (Session {chunk_index}/{chunk_count})"
            else:
                title = f"{original_quest.title} (Part {chunk_index}/{chunk_count})"
        else:
            title = f"{original_quest.title} (Chunk)"
        
        # Create a copy of the original quest with chunk-specific modifications
        chunk_quest = Quest(
            title=title,
            description=original_quest.description,
            priority=original_quest.priority,
            duration_minutes=int(chunk_duration.total_seconds() / 60),  # Use chunk-specific duration
            preferred_time_of_day=original_quest.preferred_time_of_day,
            scheduling_flexibility=original_quest.scheduling_flexibility,
            deadline=original_quest.deadline,
            buffer_before=original_quest.buffer_before,
            buffer_after=original_quest.buffer_after,
            owner_id=original_quest.owner_id,
            
            # Chunking-specific fields
            is_chunked=(strategy != 'pomodoro_style'),  # Pomodoro chunks are not marked as chunked
            chunk_index=chunk_index if chunk_index > 0 else None,
            chunk_count=chunk_count if chunk_count > 0 else None,
            base_title=original_quest.title,  # Store original title
            allow_chunking=False,  # Chunks cannot be further chunked
            parent_quest_id=original_quest.id if hasattr(original_quest, 'id') and original_quest.id else None,  # Link to parent quest
            chunk_duration_minutes=int(chunk_duration.total_seconds() / 60),  # Store chunk duration
            
            # Study-specific fields
            chunk_strategy=chunk_strategy,
            
            # Copy other relevant fields
            soft_start=original_quest.soft_start,
            soft_end=original_quest.soft_end,
            hard_start=original_quest.hard_start,
            hard_end=original_quest.hard_end,
            allow_time_deviation=original_quest.allow_time_deviation,
            allow_urgent_override=original_quest.allow_urgent_override,
            allow_same_day_recurring=original_quest.allow_same_day_recurring
        )
        
        # For in-memory quests without IDs, store the original title as a reference
        if not hasattr(original_quest, 'id') or not original_quest.id:
            chunk_quest.parent_quest_title = original_quest.title
        
        return chunk_quest



    def _schedule_in_slot(self, quest: Quest, duration: timedelta, slot: CleanTimeSlot, buffer_before: int, buffer_after: int) -> List[CleanTimeSlot]:
        """
        Schedule a quest in a specific slot with buffers.
        """
        # Check if pomodoro is enabled for this task
        pomodoro_enabled = getattr(quest, 'pomodoro_enabled', False)
        
        if pomodoro_enabled:
            return self._schedule_pomodoro_events(quest, duration, slot, buffer_before, buffer_after)
        else:
            return self._schedule_regular_task(quest, duration, slot, buffer_before, buffer_after)
    
    def _schedule_regular_task(self, quest: Quest, duration: timedelta, slot: CleanTimeSlot, buffer_before: int, buffer_after: int) -> List[CleanTimeSlot]:
        """
        Schedule a regular task (non-pomodoro) in a specific slot with buffers.
        """
        # Calculate start time (prefer earlier in the slot)
        task_start = slot.start + timedelta(minutes=buffer_before)
        task_end = task_start + duration
        buffer_after_end = task_end + timedelta(minutes=buffer_after)
        
        # Debug output for gym workouts
        if "Gym Workout" in quest.title:
            print(f"      🏋️ SCHEDULING: '{quest.title}' (ID: {quest.id})")
            print(f"         📅 Slot: {slot.start.strftime('%Y-%m-%d %H:%M')} - {slot.end.strftime('%H:%M')}")
            print(f"         ⏰ Task: {task_start.strftime('%H:%M')} - {task_end.strftime('%H:%M')}")
            print(f"         🔧 Buffer before: {buffer_before}min, after: {buffer_after}min")
        
        # Create the scheduled slots
        scheduled_slots = []
        
        # Buffer before
        if buffer_before > 0:
            buffer_slot = CleanTimeSlot(slot.start, task_start, "BUFFER", is_flexible=False)
            scheduled_slots.append(buffer_slot)
        
        # Task slot
        task_slot = CleanTimeSlot(task_start, task_end, quest, is_flexible=True)
        scheduled_slots.append(task_slot)
        
        # Buffer after
        if buffer_after > 0:
            buffer_slot = CleanTimeSlot(task_end, buffer_after_end, "BUFFER", is_flexible=False)
            scheduled_slots.append(buffer_slot)
        
        # Create remaining available time after the task
        if buffer_after_end < slot.end:
            remaining_slot = CleanTimeSlot(buffer_after_end, slot.end, AVAILABLE, is_flexible=False)
            scheduled_slots.append(remaining_slot)
        
        # Replace the original slot with the new slots
        self._replace_slot(slot, scheduled_slots)
        
        # Track the slots for this event
        if hasattr(quest, 'id'):
            self.event_slots[quest.id] = scheduled_slots
        
        # Debug: print all slots after scheduling
        print(f"      🔧 All slots after scheduling {quest.title}:")
        for i, s in enumerate(self.slots):
            print(f"         Slot {i}: {s.start} - {s.end} ({s.occupant})")
        
        return scheduled_slots
    
    def _schedule_pomodoro_events(self, quest: Quest, duration: timedelta, slot: CleanTimeSlot, buffer_before: int, buffer_after: int) -> List[CleanTimeSlot]:
        """
        Schedule a task with pomodoro technique - creates separate events for each pomodoro session and break.
        """
        # Pomodoro timing
        pomodoro_work_minutes = 25
        pomodoro_break_minutes = 5
        
        # Calculate how many pomodoros fit in the total duration
        total_minutes = int(duration.total_seconds() / 60)
        pomodoro_cycles = total_minutes // (pomodoro_work_minutes + pomodoro_break_minutes)
        remaining_minutes = total_minutes % (pomodoro_work_minutes + pomodoro_break_minutes)
        
        # Calculate start time
        task_start = slot.start + timedelta(minutes=buffer_before)
        current_time = task_start
        buffer_after_end = task_start + duration + timedelta(minutes=buffer_after)
        
        # Create the scheduled slots
        scheduled_slots = []
        
        # Buffer before
        if buffer_before > 0:
            buffer_slot = CleanTimeSlot(slot.start, task_start, "BUFFER", is_flexible=False)
            scheduled_slots.append(buffer_slot)
        
        # Create pomodoro events
        for cycle in range(pomodoro_cycles):
            # Work session
            work_start = current_time
            work_end = work_start + timedelta(minutes=pomodoro_work_minutes)
            
            # Create work session quest
            work_quest = self._create_pomodoro_quest(quest, cycle + 1, pomodoro_cycles, "work")
            work_slot = CleanTimeSlot(work_start, work_end, work_quest, is_flexible=True)
            scheduled_slots.append(work_slot)
            
            current_time = work_end
            
            # Break session (except after the last pomodoro)
            if cycle < pomodoro_cycles - 1 or remaining_minutes > 0:
                break_start = current_time
                break_end = break_start + timedelta(minutes=pomodoro_break_minutes)
                
                # Create break session quest
                break_quest = self._create_pomodoro_quest(quest, cycle + 1, pomodoro_cycles, "break")
                break_slot = CleanTimeSlot(break_start, break_end, break_quest, is_flexible=True)
                scheduled_slots.append(break_slot)
                
                current_time = break_end
        
        # Handle remaining minutes as a final work session
        if remaining_minutes > 0:
            final_work_start = current_time
            final_work_end = final_work_start + timedelta(minutes=remaining_minutes)
            
            # Create final work session quest
            final_work_quest = self._create_pomodoro_quest(quest, pomodoro_cycles + 1, pomodoro_cycles + 1, "work")
            final_work_slot = CleanTimeSlot(final_work_start, final_work_end, final_work_quest, is_flexible=True)
            scheduled_slots.append(final_work_slot)
        
        # Buffer after
        if buffer_after > 0:
            buffer_slot = CleanTimeSlot(task_start + duration, buffer_after_end, "BUFFER", is_flexible=False)
            scheduled_slots.append(buffer_slot)
        
        # Create remaining available time after the task
        if buffer_after_end < slot.end:
            remaining_slot = CleanTimeSlot(buffer_after_end, slot.end, AVAILABLE, is_flexible=False)
            scheduled_slots.append(remaining_slot)
        
        # Replace the original slot with the new slots
        self._replace_slot(slot, scheduled_slots)
        
        # Track the slots for the parent event
        if hasattr(quest, 'id'):
            self.event_slots[quest.id] = scheduled_slots
        

        
        return scheduled_slots
    
    def _create_pomodoro_quest(self, original_quest: Quest, pomodoro_index: int, total_pomodoros: int, session_type: str) -> Quest:
        """
        Create a pomodoro session quest (work or break) linked to the original quest.
        """
        if session_type == "work":
            title = f"{original_quest.title} (Pomodoro {pomodoro_index}/{total_pomodoros})"
            duration_minutes = 25
        else:  # break
            title = f"{original_quest.title} (Break {pomodoro_index}/{total_pomodoros})"
            duration_minutes = 5
        
        # Create pomodoro quest with only valid fields
        pomodoro_quest = Quest(
            title=title,
            description=f"{session_type.title()} session for {original_quest.title}",
            priority=original_quest.priority,
            duration_minutes=duration_minutes,
            preferred_time_of_day=original_quest.preferred_time_of_day,
            scheduling_flexibility=original_quest.scheduling_flexibility,
            deadline=original_quest.deadline,
            buffer_before=0,  # No buffers for individual pomodoro sessions
            buffer_after=0,
            owner_id=original_quest.owner_id,
            
            # Chunking fields to link to parent
            is_chunked=False,  # Not a chunk, but a pomodoro session
            parent_quest_id=original_quest.id if hasattr(original_quest, 'id') and original_quest.id else None,
            base_title=original_quest.title,  # Store original title
            
            # Copy other relevant fields
            soft_start=original_quest.soft_start,
            soft_end=original_quest.soft_end,
            hard_start=original_quest.hard_start,
            hard_end=original_quest.hard_end,
            allow_time_deviation=original_quest.allow_time_deviation,
            allow_urgent_override=original_quest.allow_urgent_override,
            allow_same_day_recurring=original_quest.allow_same_day_recurring
        )
        
        return pomodoro_quest


