"""Schemas package for the AI-FOCO application."""

# Import everything from the schemas module
from . import schemas

# Re-export all the classes
from .schemas import *

__all__ = [
    "EventOut",
    "EventCreate", 
    "EventUpdate",
    "GoalOut",
    "GoalCreate",
    "GoalUpdate",
    "QuestOut",
    "QuestCreate",
    "QuestUpdate",
    "UserPreferencesOut",
    "UserPreferencesCreate",
    "UserPreferencesUpdate",
    "UserOut",
    "UserCreate",
    "UserUpdate"
]
