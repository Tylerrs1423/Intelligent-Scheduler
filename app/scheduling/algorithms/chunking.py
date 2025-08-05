"""
Chunking algorithms for breaking large tasks into manageable pieces.
"""

from datetime import datetime, timedelta
from typing import List, Optional
from ..core.time_slot import CleanTimeSlot, AVAILABLE
from app.models import Quest


def should_chunk_task(quest: Quest, duration: timedelta, slots: List[CleanTimeSlot]) -> bool:
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
    
    for slot in slots:
        if (slot.occupant == AVAILABLE and 
            slot.duration() >= total_duration):
            return False  # Can fit in one slot, no need to chunk
    
    # Task is too long for any single slot, should be chunked
    return True


def schedule_chunked_task(quest: Quest, duration: timedelta, slots: List[CleanTimeSlot], 
                         window_start: datetime, calculate_chunk_strategy_func, schedule_chunk_func,
                         exact_start_time: datetime = None) -> List[CleanTimeSlot]:
    """
    Schedule a task using study-focused chunking with deadline-aware day distribution.
    Supports multiple chunking strategies and pomodoro intervals.
    """
    # Calculate chunking strategy
    chunk_strategy = calculate_chunk_strategy_func(quest, duration, window_start)
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
        scheduled_slots = schedule_front_loaded_chunks(quest, chunk_strategy, slots, window_start, schedule_chunk_func)
    else:
        # Standard chunking with day distribution
        scheduled_slots = schedule_standard_chunks(quest, chunk_strategy, slots, window_start, schedule_chunk_func)
    
    return scheduled_slots


def schedule_standard_chunks(quest: Quest, chunk_strategy: dict, slots: List[CleanTimeSlot], 
                           window_start: datetime, schedule_chunk_func) -> List[CleanTimeSlot]:
    """Schedule standard chunks with day distribution."""
    chunk_count = chunk_strategy['chunk_count']
    chunk_minutes = chunk_strategy['chunk_minutes']
    remaining_minutes = chunk_strategy['remaining_minutes']
    days_available = chunk_strategy.get('days_available', 1)
    
    # Calculate target days for each chunk (distribute evenly)
    target_days = calculate_chunk_distribution_days(quest, chunk_count, days_available, window_start)
    
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
        chunk_quest = create_chunk_quest(quest, chunk_index + 1, chunk_count, chunk_duration)
        
        # Get target day for this chunk
        target_day = target_days[chunk_index]
        
        # Try to schedule this chunk on the target day
        chunk_slots = schedule_chunk_func(chunk_quest, chunk_duration, target_day, slots)
        
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


def schedule_front_loaded_chunks(quest: Quest, chunk_strategy: dict, slots: List[CleanTimeSlot],
                               window_start: datetime, schedule_chunk_func) -> List[CleanTimeSlot]:
    """Schedule front-loaded chunks with variable sizes."""
    chunk_sizes = chunk_strategy['chunk_sizes']
    days_available = chunk_strategy.get('days_available', 1)
    
    # Calculate target days (larger chunks get earlier days)
    target_days = calculate_chunk_distribution_days(quest, len(chunk_sizes), days_available, window_start)
    
    scheduled_slots = []
    
    for chunk_index, chunk_size in enumerate(chunk_sizes):
        chunk_duration = timedelta(minutes=chunk_size)
        chunk_quest = create_chunk_quest(quest, chunk_index + 1, len(chunk_sizes), chunk_duration)
        
        target_day = target_days[chunk_index]
        chunk_slots = schedule_chunk_func(chunk_quest, chunk_duration, target_day, slots)
        
        if chunk_slots:
            scheduled_slots.extend(chunk_slots)
            print(f"   ✅ Front-loaded chunk {chunk_index + 1}/{len(chunk_sizes)} ({chunk_size}min) scheduled on {target_day.strftime('%Y-%m-%d')}")
        else:
            print(f"   ❌ Front-loaded chunk {chunk_index + 1}/{len(chunk_sizes)} failed to schedule")
    
    return scheduled_slots


def calculate_chunk_distribution_days(quest: Quest, chunk_count: int, days_available: int, window_start: datetime) -> List[datetime]:
    """Calculate target days for chunk distribution."""
    # Use scheduler window start instead of today
    window_start_date = window_start.date()
    target_days = []
    
    # Distribute chunks evenly across available days
    for i in range(chunk_count):
        day_offset = i % days_available
        target_day = window_start_date + timedelta(days=day_offset)
        target_days.append(target_day)
    
    return target_days


def calculate_chunk_strategy(quest: Quest, duration: timedelta, window_start: datetime) -> dict:
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
    days_available = calculate_days_until_deadline(quest, window_start) if deadline else 1
    
    # Select and apply chunking strategy
    if chunk_preference == 'fixed_size':
        strategy_result = calculate_fixed_size_chunks(total_minutes, days_available)
    elif chunk_preference == 'deadline_aware':
        strategy_result = calculate_deadline_aware_chunks(total_minutes, days_available, deadline)
    elif chunk_preference == 'front_loaded':
        strategy_result = calculate_front_loaded_chunks(total_minutes, days_available)
    elif chunk_preference == 'user_preference':
        strategy_result = calculate_user_preference_chunks(total_minutes, days_available, quest)
    else:  # adaptive fallback
        strategy_result = calculate_adaptive_chunks(total_minutes, days_available, quest)
    
    return strategy_result


def calculate_days_until_deadline(quest: Quest, window_start: datetime) -> int:
    """Calculate available days until deadline."""
    if not quest.deadline:
        return 1
    
    window_start_date = window_start.date()
    deadline_date = quest.deadline.date()
    days_until = (deadline_date - window_start_date).days
    
    # Ensure at least 1 day, cap at 30 days for reasonable chunking
    return max(1, min(30, days_until))


def calculate_fixed_size_chunks(total_minutes: int, days_available: int) -> dict:
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


def calculate_deadline_aware_chunks(total_minutes: int, days_available: int, deadline: datetime) -> dict:
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


def calculate_front_loaded_chunks(total_minutes: int, days_available: int) -> dict:
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


def calculate_user_preference_chunks(total_minutes: int, days_available: int, quest: Quest) -> dict:
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
        return calculate_adaptive_chunks(total_minutes, days_available, quest)
    
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


def calculate_adaptive_chunks(total_minutes: int, days_available: int, quest: Quest) -> dict:
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


def create_chunk_quest(original_quest: Quest, chunk_index: int, chunk_count: int, chunk_duration: timedelta) -> Quest:
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