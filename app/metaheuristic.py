from typing import List
from datetime import timedelta, datetime
import random
from .scheduling import CleanScheduler
from .scheduling.scoring.priority_scoring import calculate_task_selection_priority, calculate_deadline_urgency_score, calculate_frequency_score
from .models import Quest, SchedulingFlexibility
from .services.recurrence import expand_recurring_quest


class HybridScheduler:
    """Simple hybrid scheduler that uses the existing CleanScheduler"""
    
    def __init__(self, base_scheduler: CleanScheduler):
        self.base_scheduler = base_scheduler
        self.greedy_threshold = 0.7  # Minimum score to accept greedy solution
    
    def schedule_with_optimization(self, quests: List[Quest]) -> CleanScheduler:
        """Schedule tasks using the existing greedy scheduler"""
        print("🚀 Starting hybrid scheduler...")
        
        # Run greedy scheduler
        scheduler = self._run_greedy_scheduler(quests)
        
        # Evaluate the result
        score = self._evaluate_scheduler(scheduler)
        print(f"📊 Greedy scheduler score: {score:.3f}")
        
        # If score is low, try optimization
        if score < self.greedy_threshold:
            print("🔄 Score is low, trying swap optimization...")
            scheduler = self._try_swap_optimization(scheduler)
            new_score = self._evaluate_scheduler(scheduler)
            print(f"📊 After optimization score: {new_score:.3f}")
        else:
            print("✅ Greedy score is good enough!")
        
        return scheduler
    
    def _run_greedy_scheduler(self, quests: List[Quest]) -> CleanScheduler:
        """Run the existing greedy scheduler"""
        # Create a copy of the base scheduler
        scheduler = CleanScheduler(
            self.base_scheduler.window_start,
            self.base_scheduler.window_end,
            self.base_scheduler.sleep_start,
            self.base_scheduler.sleep_end
        )
        
        print(f"🔍 Initial available slots: {len(scheduler.slots)}")
        for i, slot in enumerate(scheduler.slots):
            print(f"   Slot {i}: {slot.start} - {slot.end} ({slot.duration()})")
        
        # Expand recurring tasks first
        expanded_quests = []
        for quest in quests:
            if quest.recurrence_rule:
                print(f"\n🔄 Expanding recurring task: {quest.title} (ID: {quest.id})")
                print(f"   📅 Recurrence rule: {quest.recurrence_rule}")
                instances = expand_recurring_quest(quest, scheduler.window_start, scheduler.window_end)
                print(f"   📊 Generated {len(instances)} instances")
                for i, instance in enumerate(instances):
                    print(f"      Instance {i+1}: {instance.title} (ID: {instance.id}) - {instance.recurrence_rule}")
                expanded_quests.extend(instances)
            else:
                expanded_quests.append(quest)
        
        print(f"\n📊 Total quests after expansion: {len(expanded_quests)} (original: {len(quests)})")
        
        # Separate FIXED events from other tasks - FIXED events must be scheduled FIRST
        fixed_events = []
        other_quests = []
        
        for quest in expanded_quests:
            if hasattr(quest, 'scheduling_flexibility') and quest.scheduling_flexibility == SchedulingFlexibility.FIXED:
                fixed_events.append(quest)
            else:
                other_quests.append(quest)
        
        print(f"\n🔒 FIXED Events (must be scheduled first): {len(fixed_events)}")
        for i, quest in enumerate(fixed_events):
            print(f"   {i+1}. {quest.title} at {quest.hard_start} (Priority: {quest.priority})")
        
        print(f"\n📋 Other Tasks: {len(other_quests)}")
        
        # Sort other quests by task selection priority (priority + urgency + frequency)
        sorted_other_quests = sorted(other_quests, key=lambda q: calculate_task_selection_priority(q), reverse=True)
        
        # Schedule tasks in normal priority order
        print(f"\n📋 Scheduling tasks in priority order")
        
        print(f"\n📋 Other task selection order (by priority + urgency + frequency):")
        for i, quest in enumerate(sorted_other_quests):
            priority_score = calculate_task_selection_priority(quest)
            urgency_score = calculate_deadline_urgency_score(quest)
            frequency_score = calculate_frequency_score(quest)
            print(f"   {i+1}. {quest.title} (Priority: {priority_score:.3f}, Urgency: {urgency_score:.3f}, Frequency: {frequency_score:.3f})")
        
        # STEP 1: Schedule FIXED events FIRST (they cannot be displaced)
        print(f"\n🔒 STEP 1: Scheduling FIXED events first...")
        for quest in fixed_events:
            print(f"\n🔄 Scheduling FIXED: {quest.title} ({quest.duration_minutes}min)")
            print(f"   🎯 Priority: {quest.priority}, Hard start time: {quest.hard_start}")
            
            duration = timedelta(minutes=quest.duration_minutes or 60)
            
            # Calculate the exact start time for this specific day
            # FIXED events have hard_start times - use the date from the expanded instance
            # For FIXED events, we need to combine the date with the hard_start time
            exact_start_time = datetime.combine(quest.deadline.date(), quest.hard_start)
            
            print(f"   🔒 FIXED event - scheduling at exact time: {exact_start_time}")
            result = scheduler.schedule_task_at_exact_time(quest, exact_start_time, duration)
            
            if result:
                print(f"   ✅ Scheduled FIXED: {quest.title} ({quest.duration_minutes}min)")
                # Show current slots after scheduling
                print(f"   📊 Total slots after: {len(scheduler.slots)}")
                task_slots = [s for s in scheduler.slots if hasattr(s.occupant, 'id')]
                print(f"   📝 Task slots: {len(task_slots)}")
                for slot in task_slots:
                    print(f"      Task: {slot.occupant.title} at {slot.start} - {slot.end}")
            else:
                print(f"   ❌ Failed to schedule FIXED: {quest.title} ({quest.duration_minutes}min)")
        
        # STEP 2: Schedule other quests (they cannot displace FIXED events)
        print(f"\n📋 STEP 2: Scheduling other tasks...")
        for quest in sorted_other_quests:
            print(f"\n🔄 Scheduling: {quest.title} ({quest.duration_minutes}min)")
            print(f"   🎯 Priority: {quest.priority}, Preferred time: {getattr(quest, 'preferred_time_of_day', 'None')}")
            
            # Show available slots before scheduling
            available_slots = [s for s in scheduler.slots if s.occupant == "AVAILABLE"]
            print(f"   📊 Available slots before: {len(available_slots)}")
            for slot in available_slots:
                print(f"      Available: {slot.start} - {slot.end} ({slot.duration()})")
            
            duration = timedelta(minutes=quest.duration_minutes or 60)
            
            # Regular scheduling for non-FIXED events (FIXED events already handled)
            result = scheduler.schedule_task_with_buffers(quest, duration)
            
            if result:
                print(f"   ✅ Scheduled: {quest.title} ({quest.duration_minutes}min)")
                # Show current slots after scheduling
                print(f"   📊 Total slots after: {len(scheduler.slots)}")
                task_slots = [s for s in scheduler.slots if hasattr(s.occupant, 'id')]
                print(f"   📝 Task slots: {len(task_slots)}")
                for slot in task_slots:
                    print(f"      Task: {slot.occupant.title} at {slot.start} - {slot.end}")
            else:
                print(f"   ❌ Failed to schedule: {quest.title} ({quest.duration_minutes}min)")
        
        return scheduler
    
    def _evaluate_scheduler(self, scheduler: CleanScheduler) -> float:
        """Evaluate the quality of a schedule using existing scoring"""
        total_score = 0.0
        task_count = 0
        
        # Use the existing slot scoring for each scheduled task
        from app.scheduling.scoring.slot_scoring import calculate_slot_score
        for slot in scheduler.slots:
            if hasattr(slot.occupant, 'id'):  # It's a Quest object
                score = calculate_slot_score(slot.occupant, slot, scheduler.slots)
                total_score += score
                task_count += 1
        
        # Return average score
        return total_score / task_count if task_count > 0 else 0.0
    
    def _try_swap_optimization(self, scheduler: CleanScheduler) -> CleanScheduler:
        """Try to improve schedule by swapping task slots"""
        print("   🔄 Starting swap optimization...")
        
        # Get all task slots
        task_slots = []
        for slot in scheduler.slots:
            if hasattr(slot.occupant, 'id'):  # It's a Quest object
                task_slots.append(slot)
        
        if len(task_slots) < 2:
            print("   ⚠️ Not enough tasks to swap")
            return scheduler
        
        # Try a few swaps
        max_attempts = 10
        improvements = 0
        attempts = 0
        
        while attempts < max_attempts:
            # Pick two random task slots
            slot1, slot2 = random.sample(task_slots, 2)
            
            # Check if tasks can actually fit in each other's slots
            if not self._can_swap_slots(slot1, slot2, scheduler):
                print(f"   ⚠️ Swap {attempts + 1}: Tasks don't fit, skipping")
                print(f"      Task 1: {slot1.occupant.title} ({slot1.end - slot1.start})")
                print(f"      Task 2: {slot2.occupant.title} ({slot2.end - slot2.start})")
                attempts += 1
                continue
            
            # Calculate current score
            current_score = self._evaluate_scheduler(scheduler)
            
            # Try the swap
            self._swap_slots(slot1, slot2)
            
            # Calculate new score
            new_score = self._evaluate_scheduler(scheduler)
            
            # If it's better, keep it
            if new_score > current_score:
                print(f"   ✅ Swap {attempts + 1}: Score improved {current_score:.3f} → {new_score:.3f}")
                improvements += 1
            else:
                # Revert the swap
                self._swap_slots(slot1, slot2)
                print(f"   ❌ Swap {attempts + 1}: No improvement, reverted")
            
            attempts += 1
        
        print(f"   📊 Made {improvements} improvements out of {attempts} attempts")
        return scheduler
    
    def _can_swap_slots(self, slot1, slot2, scheduler):
        """Check if two slots can be swapped based on their current slot sizes"""
        # Get task durations
        task1_duration = slot1.end - slot1.start
        task2_duration = slot2.end - slot2.start
        
        # Case 1: Same duration tasks - can always swap
        if task1_duration == task2_duration:
            print(f"      ✅ Same duration tasks - can swap")
            return True
        
        # Case 2: Different duration tasks - check if they can fit in available time
        print(f"      🔍 Different durations - checking available time")
        return self._can_fit_in_available_time(slot1, slot2, scheduler)
    
    def _can_fit_in_available_time(self, slot1, slot2, scheduler):
        """Check if tasks can fit in each other's available time windows"""
        task1_duration = slot1.end - slot1.start
        task2_duration = slot2.end - slot2.start
        
        # Find available time around each task
        available_around_slot1 = self._find_available_time_around(slot1, scheduler)
        available_around_slot2 = self._find_available_time_around(slot2, scheduler)
        
        # COMBINE: available time + task's own slot time
        total_space_around_slot1 = available_around_slot1 + (slot1.end - slot1.start)
        total_space_around_slot2 = available_around_slot2 + (slot2.end - slot2.start)
        
        # Check if tasks can fit in each other's combined spaces
        task1_fits_in_slot2_area = task1_duration <= total_space_around_slot2
        task2_fits_in_slot1_area = task2_duration <= total_space_around_slot1
        
        print(f"      📏 Task 1 ({task1_duration}) fits in slot 2 total area ({total_space_around_slot2}): {task1_fits_in_slot2_area}")
        print(f"      📏 Task 2 ({task2_duration}) fits in slot 1 total area ({total_space_around_slot1}): {task2_fits_in_slot1_area}")
        
        return task1_fits_in_slot2_area and task2_fits_in_slot1_area
    
    def _find_available_time_around(self, task_slot, scheduler):
        """Find the total available time around a task slot"""
        # Look for available slots that are adjacent to or overlap with this task
        total_available = timedelta(0)
        
        print(f"      🔍 Looking for available time around task: {task_slot.start} - {task_slot.end}")
        
        # Look for AVAILABLE slots that are adjacent to this task
        for slot in scheduler.slots:
            if hasattr(slot.occupant, 'str') and slot.occupant == "AVAILABLE":
                print(f"      📅 Found available slot: {slot.start} - {slot.end}")
                # Check if this available slot is adjacent to the task
                if slot.end <= task_slot.start:
                    # Available slot ends before task starts
                    adjacent_time = task_slot.start - slot.end
                    total_available += adjacent_time
                    print(f"      ✅ Adjacent before: {adjacent_time}")
                elif slot.start >= task_slot.end:
                    # Available slot starts after task ends
                    adjacent_time = slot.start - task_slot.end
                    total_available += adjacent_time
                    print(f"      ✅ Adjacent after: {adjacent_time}")
        
        # If no AVAILABLE slots found, calculate available time based on day boundaries
        if total_available == timedelta(0):
            print(f"      🔍 No AVAILABLE slots found, checking day boundaries")
            # Find the day boundaries for this task
            day_start = task_slot.start.replace(hour=7, minute=0, second=0, microsecond=0)  # 7 AM
            day_end = task_slot.start.replace(hour=22, minute=0, second=0, microsecond=0)   # 10 PM
            
            # Calculate available time before and after the task
            available_before = task_slot.start - day_start
            available_after = day_end - task_slot.end
            
            if available_before > timedelta(0):
                total_available += available_before
                print(f"      ✅ Available before task: {available_before}")
            if available_after > timedelta(0):
                total_available += available_after
                print(f"      ✅ Available after task: {available_after}")
        
        print(f"      📊 Total available time: {total_available}")
        return total_available
    
    def _find_original_available_slot(self, task_slot, scheduler):
        """Find the original available slot that contains this task slot"""
        # Look for an available slot that completely contains this task slot
        for slot in scheduler.slots:
            if (hasattr(slot.occupant, 'str') and slot.occupant == "AVAILABLE" and
                slot.start <= task_slot.start and slot.end >= task_slot.end):
                return slot
        return None
    
    def _swap_slots(self, slot1, slot2):
        """Swap the occupants of two slots"""
        slot1.occupant, slot2.occupant = slot2.occupant, slot1.occupant


# Test function
def test_hybrid_scheduler():
    """Test the hybrid scheduler with realistic student schedule"""
    from datetime import datetime, timedelta
    from .models import Quest, PreferredTimeOfDay, SchedulingFlexibility
    
    print("🧪 Testing Hybrid Scheduler with Realistic Student Schedule")
    print("=" * 60)
    
    # Calculate dates for the two-week period
    now = datetime.now()
    start_date = now.replace(hour=7, minute=0, second=0, microsecond=0)
    
    # Create realistic student tasks
    quests = [
        # URGENT TASKS THAT WILL FORCE DISPLACEMENT
        # URGENT: Big Project (4 hours) - HIGHEST PRIORITY
        Quest(
            id=1,
            title="URGENT: Big Project (4 hours)",
            duration_minutes=240,
            priority=10,  # HIGHEST PRIORITY
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # CRITICAL: Emergency Meeting (3 hours) - Will force displacement
        Quest(
            id=2,
            title="CRITICAL: Emergency Meeting (3 hours)",
            duration_minutes=180,
            priority=9,  # Very high priority
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # IMPORTANT: Client Presentation (2.5 hours) - Will force displacement
        Quest(
            id=3,
            title="IMPORTANT: Client Presentation (2.5 hours)",
            duration_minutes=150,
            priority=8,  # High priority
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # Fixed Classes - each on their specific day of the week
        # CS 101 Lecture - Monday at 9:00 AM
        Quest(
            id=4,
            title="CS 101 Lecture",
            duration_minutes=90,
            priority=5,
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.FIXED,
            hard_start=datetime.strptime("09:00", "%H:%M").time(),
            hard_end=datetime.strptime("10:30", "%H:%M").time(),
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO"
        ),
        
        # Math 201 Lecture - Wednesday at 11:00 AM
        Quest(
            id=5,
            title="Math 201 Lecture",
            duration_minutes=90,
            priority=5,
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.FIXED,
            hard_start=datetime.strptime("11:00", "%H:%M").time(),
            hard_end=datetime.strptime("12:30", "%H:%M").time(),
            recurrence_rule="FREQ=WEEKLY;BYDAY=WE"
        ),
        
        # Physics Lab - Friday at 2:00 PM
        Quest(
            id=6,
            title="Physics Lab",
            duration_minutes=120,
            priority=5,
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FIXED,
            hard_start=datetime.strptime("14:00", "%H:%M").time(),
            hard_end=datetime.strptime("16:00", "%H:%M").time(),
            recurrence_rule="FREQ=WEEKLY;BYDAY=FR"
        ),
        
        # Gym Sessions (WINDOW flexibility - 3-tier time scoring)
        Quest(
            id=7,
            title="Gym Workout",
            duration_minutes=90,
            priority=6,  # Higher priority than fixed classes
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.WINDOW,
            expected_start=datetime.strptime("10:30", "%H:%M").time(),  # ⭐⭐⭐ Perfect time
            expected_end=datetime.strptime("12:00", "%H:%M").time(),    # ⭐⭐⭐ Perfect time
            soft_start=datetime.strptime("09:30", "%H:%M").time(),      # ⭐⭐ Good time
            soft_end=datetime.strptime("13:30", "%H:%M").time(),        # ⭐⭐ Good time
            hard_start=datetime.strptime("08:00", "%H:%M").time(),      # ⭐ Acceptable time
            hard_end=datetime.strptime("15:00", "%H:%M").time(),        # ⭐ Acceptable time
            recurrence_rule="FREQ=WEEKLY;BYDAY=TU"
        ),

        Quest(
            id=8,
            title="Gym Workout",
            duration_minutes=90,
            priority=6,  # Higher priority than fixed classes
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.WINDOW,
            expected_start=datetime.strptime("10:30", "%H:%M").time(),  # ⭐⭐⭐ Perfect time
            expected_end=datetime.strptime("12:00", "%H:%M").time(),    # ⭐⭐⭐ Perfect time
            soft_start=datetime.strptime("09:30", "%H:%M").time(),      # ⭐⭐ Good time
            soft_end=datetime.strptime("13:30", "%H:%M").time(),        # ⭐⭐ Good time
            hard_start=datetime.strptime("08:00", "%H:%M").time(),      # ⭐ Acceptable time
            hard_end=datetime.strptime("15:00", "%H:%M").time(),        # ⭐ Acceptable time
            recurrence_rule="FREQ=WEEKLY;BYDAY=FR"
        ),
        Quest(
            id=9,
            title="Gym Workout",
            duration_minutes=90,
            priority=6,  # Higher priority than fixed classes
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.WINDOW,
            expected_start=datetime.strptime("10:30", "%H:%M").time(),  # ⭐⭐⭐ Perfect time
            expected_end=datetime.strptime("12:00", "%H:%M").time(),    # ⭐⭐⭐ Perfect time
            soft_start=datetime.strptime("09:30", "%H:%M").time(),      # ⭐⭐ Good time
            soft_end=datetime.strptime("13:30", "%H:%M").time(),        # ⭐⭐ Good time
            hard_start=datetime.strptime("08:00", "%H:%M").time(),      # ⭐ Acceptable time
            hard_end=datetime.strptime("15:00", "%H:%M").time(),        # ⭐ Acceptable time
            recurrence_rule="FREQ=WEEKLY;BYDAY=SU"
        ),
        
        # Recurring Project Work (5 times per week) - STRICT (same day, flexible time)
        Quest(
            id=10,
            title="AI Project Work",
            duration_minutes=120,
            priority=4,
            deadline=start_date + timedelta(days=13),  # End of 2 weeks
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.STRICT,
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR;COUNT=5"
        ),
        
        # Homework and Study Tasks - FLEXIBLE with deadlines
        Quest(
            id=11,
            title="CS 101 Homework",
            duration_minutes=90,
            priority=4,
            deadline=start_date + timedelta(days=2),  # Wednesday
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=12,
            title="Math 201 Problem Set",
            duration_minutes=120,
            priority=4,
            deadline=start_date + timedelta(days=5),  # Saturday
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=13,
            title="Physics Lab Report",
            duration_minutes=60,
            priority=3,
            deadline=start_date + timedelta(days=7),  # Next Monday
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # Personal Tasks - FLEXIBLE with deadlines
        Quest(
            id=14,
            title="Grocery Shopping",
            duration_minutes=45,
            priority=2,
            deadline=start_date + timedelta(days=3),  # Thursday
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=15,
            title="Laundry",
            duration_minutes=30,
            priority=2,
            deadline=start_date + timedelta(days=6),  # Sunday
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=16,
            title="Call Parents",
            duration_minutes=30,
            priority=2,
            deadline=start_date + timedelta(days=7),  # Next Monday
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # One-time Tasks with Deadlines - FLEXIBLE
        Quest(
            id=17,
            title="Resume Update",
            duration_minutes=60,
            priority=3,
            deadline=start_date + timedelta(days=4),  # Friday
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=18,
            title="Study for Midterm",
            duration_minutes=180,
            priority=5,
            deadline=start_date + timedelta(days=8),  # Next Tuesday
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=19,
            title="Group Project Meeting",
            duration_minutes=90,
            priority=4,
            deadline=start_date + timedelta(days=10),  # Next Thursday
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # Flexible Tasks (no deadlines) - FLEXIBLE
        Quest(
                id=20,
            title="Read Tech Article",
            duration_minutes=30,
            priority=1,
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=21,
            title="Practice Guitar",
            duration_minutes=45,
            priority=1,
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=22,
            title="Plan Weekend Trip",
            duration_minutes=60,
            priority=2,
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=23,
            title="Clean Room",
            duration_minutes=45,
            priority=2,
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        Quest(
            id=24,
            title="Review Notes",
            duration_minutes=60,
            priority=3,
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # Additional Test Events - More Complex Scheduling Scenarios
        
        # High Priority Work Task - WINDOW flexibility (like gym workouts)
        Quest(
            id=25,
            title="Deep Work Session",
            duration_minutes=120,
            priority=6,  # Same high priority as gym workouts
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.WINDOW,
            expected_start=datetime.strptime("09:00", "%H:%M").time(),
            expected_end=datetime.strptime("11:00", "%H:%M").time(),
            soft_start=datetime.strptime("08:00", "%H:%M").time(),
            soft_end=datetime.strptime("12:00", "%H:%M").time(),
            hard_start=datetime.strptime("07:00", "%H:%M").time(),
            hard_end=datetime.strptime("13:00", "%H:%M").time(),
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO,WE,FR"
        ),
        
        # Another WINDOW task - Evening workout
        Quest(
            id=26,
            title="Evening Run",
            duration_minutes=45,
            priority=5,
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.WINDOW,
            expected_start=datetime.strptime("18:00", "%H:%M").time(),
            expected_end=datetime.strptime("19:00", "%H:%M").time(),
            soft_start=datetime.strptime("17:00", "%H:%M").time(),
            soft_end=datetime.strptime("20:00", "%H:%M").time(),
            hard_start=datetime.strptime("16:00", "%H:%M").time(),
            hard_end=datetime.strptime("21:00", "%H:%M").time(),
            recurrence_rule="FREQ=WEEKLY;BYDAY=TU,TH,SA"
        ),
        
        # Urgent deadline task - high priority
        Quest(
            id=27,
            title="URGENT: Client Presentation Prep",
            duration_minutes=180,
            priority=7,  # Higher than gym workouts
            deadline=start_date + timedelta(days=3),  # Thursday
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # Fixed time event - like classes
        Quest(
            id=28,
            title="Team Standup Meeting",
            duration_minutes=30,
            priority=5,
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.FIXED,
            hard_start=datetime.strptime("09:00", "%H:%M").time(),
            hard_end=datetime.strptime("09:30", "%H:%M").time(),
            recurrence_rule="FREQ=WEEKLY;BYDAY=MO,TU,WE,TH,FR"
        ),
        
        # Long project work session
        Quest(
            id=29,
            title="Code Review Session",
            duration_minutes=90,
            priority=4,
            deadline=start_date + timedelta(days=6),  # Sunday
            preferred_time_of_day=PreferredTimeOfDay.AFTERNOON,
            scheduling_flexibility=SchedulingFlexibility.STRICT
        ),
        
        # Personal development - medium priority
        Quest(
            id=30,
            title="Online Course Work",
            duration_minutes=75,
            priority=3,
            deadline=start_date + timedelta(days=5),  # Saturday
            preferred_time_of_day=PreferredTimeOfDay.EVENING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        ),
        
        # Quick personal task - low priority
        Quest(
            id=31,
            title="Meditation Session",
            duration_minutes=20,
            priority=2,
            preferred_time_of_day=PreferredTimeOfDay.MORNING,
            scheduling_flexibility=SchedulingFlexibility.FLEXIBLE
        )
    ]
    
    # Create base scheduler
    window_start = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
    window_end = datetime.now().replace(hour=22, minute=0, second=0, microsecond=0) + timedelta(days=14)
    sleep_start = datetime.now().replace(hour=22, minute=0, second=0, microsecond=0)
    sleep_end = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0)
    
    print(f"🔍 DEBUG: Window start: {window_start} ({window_start.strftime('%A')})")
    print(f"🔍 DEBUG: Window end: {window_end} ({window_end.strftime('%A')})")
    
    base_scheduler = CleanScheduler(window_start, window_end, sleep_start, sleep_end)
    
    # Debug: Show what days are in the window
    print(f"🔍 DEBUG: Days in window:")
    for i, day in enumerate(base_scheduler._get_days_in_window()):
        print(f"   Day {i+1}: {day.strftime('%Y-%m-%d %A')}")
    
    # Debug: Show what slots are created
    print(f"🔍 DEBUG: Available slots created:")
    for i, slot in enumerate(base_scheduler.slots):
        print(f"   Slot {i+1}: {slot.start.strftime('%Y-%m-%d %A %H:%M')} - {slot.end.strftime('%H:%M')}")
    
    # Create hybrid scheduler with LOWER threshold to trigger optimization
    hybrid = HybridScheduler(base_scheduler)
    hybrid.greedy_threshold = 5.0  # Much higher threshold to force optimization
    
    # Run the hybrid scheduler
    final_scheduler = hybrid.schedule_with_optimization(quests)
    
    # Test displacing functionality by adding a high-priority urgent task
    print("\n🧪 Testing Displacing Functionality:")
    print("-" * 40)
    
    # Create an urgent high-priority task that should displace others
    urgent_task = Quest(
        id=999,
        title="URGENT: Big Project (4 hours)",
        duration_minutes=240,  # 4 hours - will need to displace multiple tasks
        priority=10,  # Much higher priority than existing tasks (1-3)
        deadline=datetime.now() + timedelta(hours=8)  # 8 hours from now
    )
    
    print(f"📝 Adding urgent task: {urgent_task.title}")
    print(f"⏱️ Duration: {urgent_task.duration_minutes} minutes")
    print(f"🎯 Priority: {urgent_task.priority}")
    print(f"⏰ Deadline: {urgent_task.deadline}")
    
    # Try to schedule the urgent task and see what gets displaced
    print(f"\n🔄 Attempting to schedule urgent task...")
    
    # Debug: Check what tasks are currently scheduled
    print(f"🔍 Current scheduled tasks:")
    for slot in final_scheduler.slots:
        if hasattr(slot.occupant, 'id'):
            print(f"   📝 {slot.occupant.title} (priority {slot.occupant.priority}) at {slot.start} - {slot.end}")
    
    # Debug: Check if displacement should be possible
    print(f"🔍 Looking for tasks to displace (priority < {urgent_task.priority}):")
    for slot in final_scheduler.slots:
        if (hasattr(slot.occupant, 'id') and 
            hasattr(slot.occupant, 'priority') and 
            slot.occupant.priority < urgent_task.priority):
            print(f"   📤 Can displace: {slot.occupant.title} (priority {slot.occupant.priority}) at {slot.start} - {slot.end}")
            if urgent_task.deadline and slot.start > urgent_task.deadline:
                print(f"      ❌ But it's after deadline {urgent_task.deadline}")
            else:
                print(f"      ✅ Before deadline, can displace!")
    
    print(f"\n🔍 Testing greedy displacement for {urgent_task.duration_minutes} minutes...")
    
    # Create a copy of the scheduler for displacement testing
    test_scheduler = CleanScheduler(window_start, window_end, sleep_start, sleep_end)
    test_scheduler.slots = final_scheduler.slots.copy()
    test_scheduler.event_slots = final_scheduler.event_slots.copy()
    
    displaced_slots = test_scheduler.schedule_task_with_buffers(urgent_task, timedelta(minutes=urgent_task.duration_minutes))
    
    if displaced_slots:
        print(f"✅ Urgent task scheduled! Displaced {len(displaced_slots)} slots")
        for slot in displaced_slots:
            if hasattr(slot.occupant, 'id'):
                print(f"   📤 Displaced: {slot.occupant.title} from {slot.start} - {slot.end}")
        
        # Show the final schedule after displacement
        print(f"\n📋 Schedule after displacement:")
        for slot in test_scheduler.slots:
            if hasattr(slot.occupant, 'id'):
                print(f"   {slot.start.strftime('%H:%M')} - {slot.end.strftime('%H:%M')}: {slot.occupant.title} (Priority: {slot.occupant.priority})")
        
        # Check if urgent task was scheduled before deadline
        urgent_slot = None
        for slot in test_scheduler.slots:
            if hasattr(slot.occupant, 'id') and slot.occupant.id == 999:
                urgent_slot = slot
                break
        
        if urgent_slot:
            if urgent_slot.start <= urgent_task.deadline:
                print(f"✅ Urgent task scheduled before deadline: {urgent_slot.start} <= {urgent_task.deadline}")
            else:
                print(f"❌ BUG: Urgent task scheduled AFTER deadline: {urgent_slot.start} > {urgent_task.deadline}")
    else:
        print(f"❌ Could not schedule urgent task - no available space")
    
    # Show results
    print("\n📅 Final Schedule:")
    print("-" * 30)
    
    scheduled_tasks = 0
    total_hours = 0
    
    for slot in final_scheduler.slots:
        if hasattr(slot.occupant, 'id'):  # It's a Quest
            scheduled_tasks += 1
            duration_hours = (slot.end - slot.start).total_seconds() / 3600
            total_hours += duration_hours
            
            print(f"🕐 {slot.start.strftime('%m/%d %H:%M')} - {slot.end.strftime('%H:%M')}")
            print(f"   📝 {slot.occupant.title}")
            print(f"   ⏱️  {duration_hours:.1f} hours")
            print()
    
    print(f"📊 Summary: {scheduled_tasks} tasks scheduled, {total_hours:.1f} total hours")


if __name__ == "__main__":
    test_hybrid_scheduler()

