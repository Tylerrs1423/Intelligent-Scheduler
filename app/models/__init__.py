"""Models package for the AI-FOCO application."""

# Import everything from the models module
from . import models

# Re-export all the classes and enums
from .models import *

__all__ = [
    "User",
    "Event", 
    "Goal",
    "Quest",
    "UserPreferences",
    "SchedulingFlexibility",
    "PreferredTimeOfDay",
    "Priority",
    "Mood",
    "RecurrenceRule",
    "QuestStatus",
    "QuestType",
    "GoalStatus",
    "GoalType"
]
