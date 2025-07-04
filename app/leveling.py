"""
Leveling system for AI Foco
Handles XP calculations, level progression, and quest rewards
"""

from typing import Tuple
from sqlalchemy.orm import Session
from datetime import datetime

# Leveling constants
BASE_XP_PER_LEVEL = 100
MAX_LEVEL = 500
DAILY_QUEST_XP = 100

def calculate_xp_for_level(level: int) -> int:
    """
    Calculate XP required to reach a specific level.
    XP requirement increases with each level.
    """
    if level <= 1:
        return 0
    
    # Formula: Each level requires more XP than the previous
    # Level 1->2: 100 XP
    # Level 2->3: 200 XP  
    # Level 3->4: 300 XP
    # etc.
    return sum(BASE_XP_PER_LEVEL * i for i in range(1, level))

def calculate_level_from_xp(xp: int) -> int:
    """
    Calculate current level based on total XP.
    Returns the highest level that can be achieved with the given XP.
    """
    if xp < BASE_XP_PER_LEVEL:
        return 1
    
    level = 1
    while level <= MAX_LEVEL:
        xp_needed = calculate_xp_for_level(level + 1)
        if xp < xp_needed:
            break
        level += 1
    
    return min(level, MAX_LEVEL)

def calculate_xp_to_next_level(current_xp: int) -> int:
    """
    Calculate XP needed to reach the next level.
    """
    current_level = calculate_level_from_xp(current_xp)
    if current_level >= MAX_LEVEL:
        return 0
    
    xp_for_next_level = calculate_xp_for_level(current_level + 1)
    return xp_for_next_level - current_xp

def add_xp_to_user(current_xp: int, xp_to_add: int) -> Tuple[int, int, int]:
    """
    Add XP to a user and return new XP, level, and XP gained.
    
    Returns:
        Tuple of (new_xp, new_level, levels_gained)
    """
    old_level = calculate_level_from_xp(current_xp)
    new_xp = max(0, current_xp + xp_to_add)  # XP can't go below 0
    new_level = calculate_level_from_xp(new_xp)
    levels_gained = new_level - old_level
    
    return new_xp, new_level, levels_gained

def remove_xp_from_user(current_xp: int, xp_to_remove: int) -> Tuple[int, int, int]:
    """
    Remove XP from a user and return new XP, level, and levels lost.
    
    Returns:
        Tuple of (new_xp, new_level, levels_lost)
    """
    old_level = calculate_level_from_xp(current_xp)
    new_xp = max(0, current_xp - xp_to_remove)  # XP can't go below 0
    new_level = calculate_level_from_xp(new_xp)
    levels_lost = old_level - new_level
    
    return new_xp, new_level, levels_lost

def get_quest_xp_reward(quest_xp: int, quest_type: str, is_penalty: bool = False) -> int:
    """
    Calculate the actual XP reward for completing a quest.
    
    Args:
        quest_xp: Base XP of the quest
        quest_type: Type of quest (daily, regular, etc.)
        is_penalty: Whether this is a penalty quest (negative XP)
    
    Returns:
        XP reward (positive for normal quests, negative for penalty quests)
    """
    if is_penalty:
        # Penalty quests give negative XP
        return -quest_xp
    
    # Daily quests always give 100 XP
    if quest_type == "daily":
        return DAILY_QUEST_XP
    
    # Other quest types give their base XP
    return quest_xp

def get_level_progress(current_xp: int) -> dict:
    """
    Get detailed level progress information.
    
    Returns:
        Dictionary with level progress details
    """
    current_level = calculate_level_from_xp(current_xp)
    xp_for_current_level = calculate_xp_for_level(current_level)
    xp_for_next_level = calculate_xp_for_level(current_level + 1) if current_level < MAX_LEVEL else xp_for_current_level
    
    xp_in_current_level = current_xp - xp_for_current_level
    xp_needed_for_next = xp_for_next_level - current_xp
    
    if current_level >= MAX_LEVEL:
        progress_percentage = 100.0
    else:
        level_xp_range = xp_for_next_level - xp_for_current_level
        progress_percentage = (xp_in_current_level / level_xp_range) * 100 if level_xp_range > 0 else 0
    
    return {
        "current_level": current_level,
        "current_xp": current_xp,
        "xp_in_current_level": xp_in_current_level,
        "xp_for_next_level": xp_needed_for_next,
        "progress_percentage": round(progress_percentage, 2),
        "is_max_level": current_level >= MAX_LEVEL
    }

# Statistics update functions
def update_user_stats_on_quest_created(db: Session, user_id: int):
    """Increment quest creation counter when a new quest is created"""
    from .models import User
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.total_quests_created += 1
        user.stats_updated_at = datetime.utcnow()
        db.commit()

def update_user_stats_on_quest_completed(db: Session, user_id: int, quest_xp: int, quest_type: str, is_penalty: bool = False):
    """Update user stats when a quest is completed"""
    from .models import User
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        # Update completion counters
        user.total_quests_completed += 1
        user.total_xp_earned += quest_xp
        
        # Update quest type counters
        if quest_type == "daily":
            user.daily_quests_completed += 1
        elif is_penalty:
            user.penalty_quests_completed += 1
        
        user.stats_updated_at = datetime.utcnow()
        db.commit()

def update_user_stats_on_quest_failed(db: Session, user_id: int):
    """Update user stats when a quest fails"""
    from .models import User
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.total_quests_failed += 1
        user.stats_updated_at = datetime.utcnow()
        db.commit()

def update_user_stats_on_task_created(db: Session, user_id: int):
    """Increment task creation counter when a new task is created"""
    from .models import User
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.total_tasks_created += 1
        user.stats_updated_at = datetime.utcnow()
        db.commit()

def update_user_stats_on_task_completed(db: Session, user_id: int):
    """Update user stats when a task is completed"""
    from .models import User
    user = db.query(User).filter(User.id == user_id).first()
    if user:
        user.total_tasks_completed += 1
        user.stats_updated_at = datetime.utcnow()
        db.commit()

def get_user_stats_from_cache(user) -> dict:
    """
    Get user statistics from cached database fields.
    Much faster than calculating from scratch.
    """
    return {
        "user_info": {
            "username": user.username,
            "level": user.level,
            "xp": user.xp,
            "level_progress": get_level_progress(user.xp)
        },
        "quest_statistics": {
            "total_quests": user.total_quests_created,
            "completed_quests": user.total_quests_completed,
            "failed_quests": user.total_quests_failed,
            "completion_rate": round((user.total_quests_completed / user.total_quests_created * 100) if user.total_quests_created > 0 else 0, 2),
            "quest_types": {
                "daily": user.daily_quests_completed,
                "penalty": user.penalty_quests_completed,
                "timed": user.timed_quests_completed,
                "hidden": user.hidden_quests_completed,
                "regular": user.total_quests_completed - user.daily_quests_completed - user.penalty_quests_completed - user.timed_quests_completed - user.hidden_quests_completed
            }
        },
        "task_statistics": {
            "total_tasks": user.total_tasks_created,
            "completed_tasks": user.total_tasks_completed,
            "pending_tasks": user.total_tasks_created - user.total_tasks_completed,
            "completion_rate": round((user.total_tasks_completed / user.total_tasks_created * 100) if user.total_tasks_created > 0 else 0, 2)
        },
        "xp_statistics": {
            "total_xp_earned": user.total_xp_earned,
            "avg_xp_per_quest": round(user.total_xp_earned / user.total_quests_completed, 2) if user.total_quests_completed > 0 else 0,
            "total_xp_from_quests": user.total_xp_earned
        },
        "stats_last_updated": user.stats_updated_at
    } 