from sqlalchemy import (
    String, Integer, Boolean, Enum, ForeignKey, DateTime, Interval, Table, Column, UniqueConstraint, Time, ARRAY, Float
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.mutable import MutableList
from datetime import datetime, timedelta
from typing import Optional, List
from .database import Base
import enum
from pydantic import BaseModel

# Core Pillars (broad categories) for theme_tags
THEME_CATEGORIES = {
    "Fitness": ["Movement", "Strength Training", "Stretching", "Cardio", "Steps"],
    "Mental Health": ["Meditation", "Journaling", "Mindfulness", "Gratitude", "Emotional Check-in"],
    "Learning & Growth": ["Reading", "Study", "Practice", "Skill Building", "Projects"],
    "Focus & Productivity": ["Deep Work", "Time Blocking", "Task Management", "Distraction Reduction", "Pomodoro"],
    "Breaking Bad Habits": ["Reduce Scrolling", "Nail Biting", "Hair Pulling", "Avoid Procrastination", "Impulse Control"],
    "Creativity": ["Writing", "Music", "Art", "Photography", "Creative Projects"],
    "Career & Development": ["Interview Practice", "Resume Improvement", "Networking", "Portfolio", "Certifications"],
    "Life Management": ["Cleaning", "Errands", "Meal Prep", "Budgeting", "Planning"]
}

# Enums

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class QuestStatus(str, enum.Enum):
    STANDING_BY = "standing_by"
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"

class QuestCategory(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"
    ONE_TIME = "one_time"
    CUSTOM = "custom"
    STORY = "story"

class QuestGeneration(str, enum.Enum):
    GOAL_GENERATED = "goal_generated"
    AI = "ai"

class QuestType(str, enum.Enum):
    REGULAR = "REGULAR"
    HIDDEN = "HIDDEN"
    UNIQUE = "UNIQUE"
    JOB_CHANGE = "JOB_CHANGE"
    TIMED = "TIMED"

class QuestDifficulty(str, enum.Enum):
    TIER_1 = "TIER_1"
    TIER_2 = "TIER_2"
    TIER_3 = "TIER_3"
    TIER_4 = "TIER_4"
    TIER_5 = "TIER_5"

class GoalStatus(str, enum.Enum):
    NOT_STARTED = "NOT_STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"

class PriorityLevel(int, enum.Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

class MeasurementType(str, enum.Enum):
    TIME = "time"
    REPS = "reps"
    DISTANCE = "distance"
    COUNT = "count"
    BOOLEAN = "boolean"
    CUSTOM = "custom"

class TaskType(str, enum.Enum):
    DAILY_QUEST = "DAILY_QUEST"
    # Extend as needed

class UserIntensityProfile(str, enum.Enum):
    CHILL = "chill"
    STEADY = "steady"
    HARDCORE = "hardcore"

class SourceType(str, enum.Enum):
    GOAL = "goal"
    SUBGOAL = "subgoal"
    QUEST = "quest"
    MANUAL = "manual"

class SchedulingFlexibility(str, enum.Enum):
    FIXED = "fixed"           # Cannot be moved at all (time and day locked)
    STRICT = "strict"         # Cannot be moved to different days, but can move time within same day
    FLEXIBLE = "flexible"     # Can be moved freely (both time and day)
    WINDOW = "window"         # Can move within preferred time window, but not outside it
    WINDOW_UNSTRICT = "window_unstrict"  # Can move within preferred time window on any day (same time window every day)

class EventMood(str, enum.Enum):
    FUN = "fun"
    STRESSFUL = "stressful"
    RELAXING = "relaxing"
    FOCUS = "focus"
    SOCIAL = "social"
    IMPORTANT = "important"
    OTHER = "other"

class PreferredTimeOfDay(str, enum.Enum):
    MORNING = "morning"      # 6:00 AM - 12:00 PM
    AFTERNOON = "afternoon"  # 12:00 PM - 6:00 PM
    EVENING = "evening"      # 6:00 PM - 11:00 PM
    NO_PREFERENCE = "no_preference"  # Any time

class TaskDifficulty(str, enum.Enum):
    EASY = "easy"           # 1-2 hours, low mental effort
    MEDIUM = "medium"       # 2-4 hours, moderate effort
    HARD = "hard"           # 4-6 hours, high effort
    VERY_HARD = "very_hard" # 6+ hours, very high effort
    UNKNOWN = "unknown"     # Not yet determined

# FrequencyType removed - using RRULE as the primary recurrence engine

# We'll use dateutil.rrule instead of custom RecurrenceRule class
# The recurrence_rule field in Quest will store RRULE strings
# and we'll use dateutil.rrule to parse and expand them

# Association table for many-to-many goals ↔ quests
goals_quests = Table(
    "goals_quests",
    Base.metadata,
    Column("goal_id", Integer, ForeignKey("goals.id"), primary_key=True),
    Column("quest_id", Integer, ForeignKey("quests.id"), primary_key=True),
)

# Models

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.USER)

    sleep_start: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    sleep_end: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    max_daily_hours: Mapped[float] = mapped_column(Float, default=8.0)  # Max hours per day

    # Relationships
    goals = relationship("Goal", back_populates="owner")
    quests = relationship("Quest", back_populates="owner")
    stats = relationship("UserStats", back_populates="user", uselist=False)
    quest_preference = relationship("UserQuestPreference", back_populates="user", uselist=False)
    scheduled_tasks = relationship("ScheduledTask", back_populates="user")
    events = relationship("Event", back_populates="user")
    google_token = relationship("GoogleOAuthToken", back_populates="user", uselist=False)
    

class UserStats(Base):
    __tablename__ = "user_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user = relationship("User", back_populates="stats")

    # XP & Leveling
    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    xp_since_last_level: Mapped[int] = mapped_column(Integer, default=0)
    xp_needed_for_next: Mapped[int] = mapped_column(Integer, default=100)
    level: Mapped[int] = mapped_column(Integer, default=1)

    # Quest stats
    total_quests_created: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_accepted: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_rejected: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_failed: Mapped[int] = mapped_column(Integer, default=0)

    # Goal stats
    total_goals_created: Mapped[int] = mapped_column(Integer, default=0)
    total_goals_completed: Mapped[int] = mapped_column(Integer, default=0)

    # Quest type stats
    daily_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    penalty_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    timed_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    hidden_quests_completed: Mapped[int] = mapped_column(Integer, default=0)

    stats_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class UserQuestPreference(Base):
    __tablename__ = "user_quest_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    user = relationship("User", back_populates="quest_preference")

    preferred_difficulty: Mapped[QuestDifficulty] = mapped_column(Enum(QuestDifficulty), default=QuestDifficulty.TIER_1)
    user_intensity_profile: Mapped[UserIntensityProfile] = mapped_column(Enum(UserIntensityProfile), default=UserIntensityProfile.STEADY)
    preferred_daily_quest_time: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    theme_tags: Mapped[Optional[list[str]]] = mapped_column(MutableList.as_mutable(SQLiteJSON), default=list)
    preferred_quest_times: Mapped[Optional[list[dict]]] = mapped_column(MutableList.as_mutable(SQLiteJSON), default=list)
    goal_intent_paragraph: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)

    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)

    status: Mapped[GoalStatus] = mapped_column(Enum(GoalStatus), default=GoalStatus.NOT_STARTED)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    priority: Mapped[PriorityLevel] = mapped_column(Enum(PriorityLevel), default=PriorityLevel.MEDIUM)
    difficulty: Mapped[TaskDifficulty] = mapped_column(Enum(TaskDifficulty), default=TaskDifficulty.UNKNOWN)
    estimated_duration: Mapped[Optional[timedelta]] = mapped_column(Interval, nullable=True)
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    
    # Relationships
    owner = relationship("User", back_populates="goals")
    quests = relationship("Quest", secondary=goals_quests, back_populates="goals")
    subgoals = relationship("Subgoal", back_populates="goal", cascade="all, delete-orphan")

class Subgoal(Base):
    __tablename__ = "subgoals"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    goal_id: Mapped[int] = mapped_column(Integer, ForeignKey("goals.id"))
    
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    goal = relationship("Goal", back_populates="subgoals")

class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)

    quest_type: Mapped[QuestType] = mapped_column(Enum(QuestType), default=QuestType.REGULAR)
    difficulty: Mapped[QuestDifficulty] = mapped_column(Enum(QuestDifficulty), default=QuestDifficulty.TIER_1)

    sent_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    time_limit_to_accept: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_limit_to_complete: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    xp_reward: Mapped[int] = mapped_column(Integer, default=10)
    time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    repeatable: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[QuestStatus] = mapped_column(Enum(QuestStatus), default=QuestStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_main_daily_quest: Mapped[bool] = mapped_column(Boolean, default=False)

    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("main_daily_quest_templates.id"), nullable=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    theme_tags: Mapped[Optional[list[str]]] = mapped_column(MutableList.as_mutable(SQLiteJSON), default=list)

    # Scheduling fields (merged from QuestInstance)
    priority: Mapped[int] = mapped_column(Integer, default=2)  # Default to MEDIUM priority
    # due_at field removed - only deadline is used for date constraints
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)  # Absolute deadline (hard constraint)
    preferred_time_of_day: Mapped[PreferredTimeOfDay] = mapped_column(Enum(PreferredTimeOfDay), default=PreferredTimeOfDay.NO_PREFERENCE)
    duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Use this instead of time_limit_minutes
    
    # Chunking fields
    chunk_index: Mapped[int] = mapped_column(Integer, default=1)
    chunk_count: Mapped[int] = mapped_column(Integer, default=1)
    is_chunked: Mapped[bool] = mapped_column(Boolean, default=False)
    base_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # Original title for chunked quests
    allow_chunking: Mapped[bool] = mapped_column(Boolean, default=True)  # Whether this task can be chunked
    
    # Parent-child relationship for chunked tasks
    parent_quest_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quests.id"), nullable=True)  # Link to parent quest
    chunk_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Duration of this specific chunk
    
    # Study-focused chunking fields
    chunk_preference: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 'fixed_size', 'deadline_aware', 'front_loaded', 'user_preference', 'adaptive'
    chunk_size_preference: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # 'small', 'medium', 'large'
    chunk_strategy: Mapped[Optional[dict]] = mapped_column(SQLiteJSON, nullable=True)  # Store chunking strategy details
    
    # Pomodoro technique field
    pomodoro_enabled: Mapped[bool] = mapped_column(Boolean, default=False)  # Whether to apply pomodoro technique within scheduled blocks
    
    # Recurrence field - RRULE string (RFC 5545 standard)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # RRULE string for recurrence patterns
    # Recurrence linkage (self-referential, separate from chunking)
    recurrence_parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("quests.id"), nullable=True)
    
    # Buffer fields
    buffer_before: Mapped[int] = mapped_column(Integer, default=0)  # minutes
    buffer_after: Mapped[int] = mapped_column(Integer, default=0)   # minutes
    
    # Scheduling flexibility
    scheduling_flexibility: Mapped[SchedulingFlexibility] = mapped_column(Enum(SchedulingFlexibility), default=SchedulingFlexibility.FLEXIBLE)
    
    # Time window constraints (for AI scheduling)
    expected_start: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)  # Expected start time (highest score)
    expected_end: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)    # Expected end time (highest score)
    soft_start: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)  # Preferred fall back window start(soft limit)
    soft_end: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)    # Preferred fall back window end time (soft limit)
    hard_start: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)  # Must start after this time (hard limit)
    hard_end: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)    # Must end before this time (hard limit)
    
    # Strict scheduling rule overrides
    allow_time_deviation: Mapped[bool] = mapped_column(Boolean, default=False)      # Allow deviation from time preference
    allow_urgent_override: Mapped[bool] = mapped_column(Boolean, default=False)     # Allow urgent deadline override
    allow_same_day_recurring: Mapped[bool] = mapped_column(Boolean, default=False)  # Allow same-day recurring instances

    # Relationships
    owner = relationship("User", back_populates="quests")
    goals = relationship("Goal", secondary=goals_quests, back_populates="quests")
    subtasks = relationship("QuestSubtask", cascade="all, delete-orphan", back_populates="quest")
    template = relationship("MainDailyQuestTemplate", back_populates="quests")
    
    # Parent-child relationships for chunked tasks
    parent_quest = relationship(
        "Quest",
        remote_side=[id],
        back_populates="chunk_quests",
        foreign_keys="Quest.parent_quest_id",
    )
    chunk_quests = relationship(
        "Quest",
        back_populates="parent_quest",
        cascade="all, delete-orphan",
        foreign_keys="Quest.parent_quest_id",
    )
    
    # Recurrence relationships (do not reuse chunking relationships)
    recurrence_parent = relationship(
        "Quest",
        remote_side=[id],
        back_populates="recurrence_children",
        foreign_keys="Quest.recurrence_parent_id",
    )
    recurrence_children = relationship(
        "Quest",
        back_populates="recurrence_parent",
        foreign_keys="Quest.recurrence_parent_id",
    )

class QuestSubtask(Base):
    __tablename__ = "quest_subtasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    quest_id: Mapped[int] = mapped_column(ForeignKey("quests.id"))

    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    measurement_type: Mapped[MeasurementType] = mapped_column(Enum(MeasurementType), default=MeasurementType.BOOLEAN)
    goal_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g., 50 reps
    completed_value: Mapped[int] = mapped_column(Integer, default=0)

    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    quest = relationship("Quest", back_populates="subtasks")

class MainDailyQuestTemplate(Base):
    __tablename__ = "main_daily_quest_templates"
    __table_args__ = (UniqueConstraint("user_id", "active", name="uq_user_active_template"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    user = relationship("User")

    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    xp_reward: Mapped[int] = mapped_column(Integer, default=10)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    subtasks = relationship("MainDailyQuestSubtaskTemplate", cascade="all, delete-orphan", back_populates="template")
    quests = relationship("Quest", back_populates="template")

class MainDailyQuestSubtaskTemplate(Base):
    __tablename__ = "main_daily_quest_subtask_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_id: Mapped[int] = mapped_column(ForeignKey("main_daily_quest_templates.id"))
    template = relationship("MainDailyQuestTemplate", back_populates="subtasks")

    title: Mapped[str] = mapped_column(String, index=True)
    measurement_type: Mapped[MeasurementType] = mapped_column(Enum(MeasurementType), default=MeasurementType.BOOLEAN)
    goal_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[str] = mapped_column(String, unique=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    task_type: Mapped[TaskType] = mapped_column(Enum(TaskType), default=TaskType.DAILY_QUEST)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="scheduled_tasks")



class Event(Base):
    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, default="")
    
    start_time: Mapped[datetime] = mapped_column(nullable=False)
    end_time: Mapped[datetime] = mapped_column(nullable=False)
    
    scheduling_flexibility: Mapped[SchedulingFlexibility] = mapped_column(Enum(SchedulingFlexibility), default=SchedulingFlexibility.FIXED)
    is_auto_generated: Mapped[bool] = mapped_column(default=False)
    source: Mapped[Optional[SourceType]] = mapped_column(Enum(SourceType))  # 'goal', 'subgoal', 'quest', 'manual'
    source_id: Mapped[Optional[int]] = mapped_column(Integer)  # e.g. the goal or quest ID
    earliest_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    latest_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    priority: Mapped[PriorityLevel] = mapped_column(Enum(PriorityLevel), default=PriorityLevel.MEDIUM)
    allowed_days: Mapped[Optional[list[int]]] = mapped_column(SQLiteJSON, nullable=True)
    soft_start: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    soft_end: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    hard_start: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    hard_end: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    min_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    max_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    buffer_before: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    buffer_after: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    recurrence_rule: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    depends_on_event_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    depends_on_quest_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    mood: Mapped[Optional[EventMood]] = mapped_column(Enum(EventMood), nullable=True)
    max_moves: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    moves_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    user = relationship("User", back_populates="events")



class GoogleOAuthToken(Base):
    __tablename__ = "google_oauth_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    access_token: Mapped[str] = mapped_column(String, nullable=False)
    refresh_token: Mapped[str] = mapped_column(String, nullable=False)
    token_expiry: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user = relationship("User", back_populates="google_token")
