from typing import List
from datetime import timedelta
import random
from .routes.events import CleanScheduler
from .models import Quest


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
        
        # Schedule each quest using the existing system
        for quest in quests:
            duration = timedelta(minutes=quest.duration_minutes or 60)
            scheduler.schedule_task_with_buffers(quest, duration)
        
        return scheduler
    
    def _evaluate_scheduler(self, scheduler: CleanScheduler) -> float:
        """Evaluate the quality of a schedule using existing scoring"""
        total_score = 0.0
        task_count = 0
        
        # Use the existing slot scoring for each scheduled task
        for slot in scheduler.slots:
            if hasattr(slot.occupant, 'id'):  # It's a Quest object
                score = scheduler._calculate_slot_score(slot.occupant, slot)
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
        
        for attempt in range(max_attempts):
            # Pick two random task slots
            slot1, slot2 = random.sample(task_slots, 2)
            
            # Calculate current score
            current_score = self._evaluate_scheduler(scheduler)
            
            # Try the swap
            self._swap_slots(slot1, slot2)
            
            # Calculate new score
            new_score = self._evaluate_scheduler(scheduler)
            
            # If it's better, keep it
            if new_score > current_score:
                print(f"   ✅ Swap {attempt + 1}: Score improved {current_score:.3f} → {new_score:.3f}")
                improvements += 1
            else:
                # Revert the swap
                self._swap_slots(slot1, slot2)
                print(f"   ❌ Swap {attempt + 1}: No improvement, reverted")
        
        print(f"   📊 Made {improvements} improvements out of {max_attempts} attempts")
        return scheduler
    
    def _swap_slots(self, slot1, slot2):
        """Swap the occupants of two slots"""
        slot1.occupant, slot2.occupant = slot2.occupant, slot1.occupant
