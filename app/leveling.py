"""
Leveling system for AI Foco
Handles XP-locked leveling, quest rewards, and user statistics
"""

from typing import Tuple
from sqlalchemy.orm import Session
from datetime import datetime
from .models import QuestType

# Leveling constants
BASE_XP_PER_LEVEL = 100
MAX_LEVEL = 500

# XP curve function (can be changed at any time without affecting existing users)
def get_next_level_xp(level: int) -> int:
    """Calculate XP needed for the next level"""
    if level >= MAX_LEVEL:
        return 0
    # Example: 100 * 1.5^(level-1)
    return int(BASE_XP_PER_LEVEL * (1.5 ** (level - 1)))

def award_xp_and_level_up(user_stats, xp_gained: int) -> int:
    """
    Add XP to user and handle level-ups. Only ever increase level when enough XP is earned.
    
    Args:
        user_stats: UserStats object
        xp_gained: XP to award
        
    Returns:
        Number of levels gained
    """
    user_stats.xp_total += xp_gained
    user_stats.xp_since_last_level += xp_gained
    levels_gained = 0
    
    while user_stats.xp_since_last_level >= user_stats.xp_needed_for_next:
        user_stats.xp_since_last_level -= user_stats.xp_needed_for_next
        user_stats.level += 1
        user_stats.xp_needed_for_next = get_next_level_xp(user_stats.level)
        levels_gained += 1
        
        # Cap at max level
        if user_stats.level >= MAX_LEVEL:
            user_stats.xp_since_last_level = 0
            user_stats.xp_needed_for_next = 0
            break
    
    return levels_gained

def get_level_progress(user_stats) -> dict:
    if user_stats.level >= MAX_LEVEL:
        return {
            "current_level": user_stats.level,
            "current_xp": user_stats.xp_total,
            "xp_in_current_level": 0,
            "xp_for_next_level": 0,
            "progress_percentage": 100.0,
            "is_max_level": True
        }
    progress_percentage = (user_stats.xp_since_last_level / user_stats.xp_needed_for_next * 100) if user_stats.xp_needed_for_next > 0 else 0
    return {
        "current_level": user_stats.level,
        "current_xp": user_stats.xp_total,
        "xp_in_current_level": user_stats.xp_since_last_level,
        "xp_for_next_level": user_stats.xp_needed_for_next,
        "progress_percentage": round(progress_percentage, 2),
        "is_max_level": False
    }

# Batch update system for better performance
class UserStatsBatch:
    """Batch user statistics updates to reduce database commits"""
    
    def __init__(self):
        self.updates = {}
    
    def add_quest_created(self, user_id: int):
        if user_id not in self.updates:
            self.updates[user_id] = {"quests_created": 0, "quests_completed": 0, "quests_failed": 0, "goals_created": 0, "goals_completed": 0}
        self.updates[user_id]["quests_created"] += 1
    
    def add_quest_completed(self, user_id: int, quest_type: str):
        if user_id not in self.updates:
            self.updates[user_id] = {"quests_created": 0, "quests_completed": 0, "quests_failed": 0, "goals_created": 0, "goals_completed": 0}
        self.updates[user_id]["quests_completed"] += 1
    
    def add_quest_failed(self, user_id: int):
        if user_id not in self.updates:
            self.updates[user_id] = {"quests_created": 0, "quests_completed": 0, "quests_failed": 0, "goals_created": 0, "goals_completed": 0}
        self.updates[user_id]["quests_failed"] += 1
    
    def add_goal_created(self, user_id: int):
        if user_id not in self.updates:
            self.updates[user_id] = {"quests_created": 0, "quests_completed": 0, "quests_failed": 0, "goals_created": 0, "goals_completed": 0}
        self.updates[user_id]["goals_created"] += 1
    
    def add_goal_completed(self, user_id: int):
        if user_id not in self.updates:
            self.updates[user_id] = {"quests_created": 0, "quests_completed": 0, "quests_failed": 0, "goals_created": 0, "goals_completed": 0}
        self.updates[user_id]["goals_completed"] += 1
    
    def get_pending_updates(self, user_id: int) -> dict:
        """Get pending updates for a user (before commit)"""
        return self.updates.get(user_id, {})
    
    def commit(self, db: Session):
        """Commit all batched updates to database in one transaction"""
        from .models import UserStats
        
        for user_id, updates in self.updates.items():
            user_stats = db.query(UserStats).filter(UserStats.user_id == user_id).first()
            if user_stats:
                user_stats.total_quests_created += updates.get("quests_created", 0)
                user_stats.total_quests_completed += updates.get("quests_completed", 0)
                user_stats.total_quests_failed += updates.get("quests_failed", 0)
                user_stats.total_goals_created += updates.get("goals_created", 0)
                user_stats.total_goals_completed += updates.get("goals_completed", 0)
                user_stats.stats_updated_at = datetime.utcnow()
        
        # Single commit for all updates
        db.commit()
        self.updates.clear()

# Global batch instance
stats_batch = UserStatsBatch()

# Batch update functions
def update_user_stats_on_quest_created(user_id: int):
    """Add quest creation to batch"""
    stats_batch.add_quest_created(user_id)

def update_user_stats_on_quest_completed(user_id: int, quest_type: str):
    """Add quest completion to batch"""
    stats_batch.add_quest_completed(user_id, quest_type)

def update_user_stats_on_quest_failed(user_id: int):
    """Add quest failure to batch"""
    stats_batch.add_quest_failed(user_id)

def update_user_stats_on_goal_created(user_id: int):
    """Add goal creation to batch"""
    stats_batch.add_goal_created(user_id)

def update_user_stats_on_goal_completed(user_id: int):
    """Add goal completion to batch"""
    stats_batch.add_goal_completed(user_id)

def commit_user_stats_batch(db: Session):
    """Commit all batched user statistics updates"""
    stats_batch.commit(db)

def get_user_stats(user, db: Session = None, include_pending: bool = True) -> dict:
    """
    Get user statistics. Automatically includes pending batch updates if available.
    
    Args:
        user: User object with stats relationship
        db: Database session (needed if include_pending=True)
        include_pending: Whether to include pending batch updates (default: True)
    """
    if not user.stats:
        return {"error": "User stats not found"}
    
    stats = user.stats
    
    # Get base stats from database
    base_stats = {
        "total_quests_created": stats.total_quests_created,
        "total_quests_completed": stats.total_quests_completed,
        "total_quests_failed": stats.total_quests_failed,
        "total_goals_created": stats.total_goals_created,
        "total_goals_completed": stats.total_goals_completed,
        "daily_quests_completed": stats.daily_quests_completed,
        "penalty_quests_completed": stats.penalty_quests_completed,
        "timed_quests_completed": stats.timed_quests_completed,
        "hidden_quests_completed": stats.hidden_quests_completed,
    }
    
    # Include pending updates if requested and available
    has_pending = False
    if include_pending and db:
        pending = stats_batch.get_pending_updates(user.id)
        if pending:
            has_pending = True
            base_stats["total_quests_created"] += pending.get("quests_created", 0)
            base_stats["total_quests_completed"] += pending.get("quests_completed", 0)
            base_stats["total_quests_failed"] += pending.get("quests_failed", 0)
            base_stats["total_goals_created"] += pending.get("goals_created", 0)
            base_stats["total_goals_completed"] += pending.get("goals_completed", 0)
    
    return {
        "user_info": {
            "username": user.username,
            "level": stats.level,
            "xp_total": stats.xp_total,
            "level_progress": get_level_progress(stats)
        },
        "quest_statistics": {
            "total_quests": base_stats["total_quests_created"],
            "completed_quests": base_stats["total_quests_completed"],
            "failed_quests": base_stats["total_quests_failed"],
            "completion_rate": round((base_stats["total_quests_completed"] / base_stats["total_quests_created"] * 100) if base_stats["total_quests_created"] > 0 else 0, 2),
            "quest_types": {
                "daily": base_stats["daily_quests_completed"],
                "penalty": base_stats["penalty_quests_completed"],
                "timed": base_stats["timed_quests_completed"],
                "hidden": base_stats["hidden_quests_completed"],
                "regular": base_stats["total_quests_completed"] - base_stats["daily_quests_completed"] - base_stats["penalty_quests_completed"] - base_stats["timed_quests_completed"] - base_stats["hidden_quests_completed"]
            }
        },
        "goal_statistics": {
            "total_goals": base_stats["total_goals_created"],
            "completed_goals": base_stats["total_goals_completed"],
            "pending_goals": base_stats["total_goals_created"] - base_stats["total_goals_completed"],
            "completion_rate": round((base_stats["total_goals_completed"] / base_stats["total_goals_created"] * 100) if base_stats["total_goals_created"] > 0 else 0, 2)
        },
        "xp_statistics": {
            "total_xp_earned": stats.xp_total,
            "avg_xp_per_quest": round(stats.xp_total / base_stats["total_quests_completed"], 2) if base_stats["total_quests_completed"] > 0 else 0,
        },
        "stats_last_updated": stats.stats_updated_at,
        "has_pending_updates": has_pending
    } 