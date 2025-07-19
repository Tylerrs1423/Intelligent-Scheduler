from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, JSON, Text, Table, Column, UniqueConstraint, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
import enum
from datetime import datetime
from typing import Optional
from sqlalchemy.dialects.sqlite import JSON as SQLiteJSON
from sqlalchemy.ext.mutable import MutableList

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





class UserRole(str, enum.Enum):
    USER= "user"
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

class MeasurementType(str, enum.Enum):
    TIME = "time"
    REPS = "reps"
    DISTANCE = "distance"
    COUNT = "count"
    BOOLEAN = "boolean"
    CUSTOM = "custom"

class TaskType(str, enum.Enum):
    DAILY_QUEST = "DAILY_QUEST"
    # Add more task types as needed, e.g.:
    # WEEKLY_SUMMARY = "WEEKLY_SUMMARY"
    # REMINDER = "REMINDER"

class UserIntensityProfile(str, enum.Enum):
    """
    Intensity profile for user questing habits.
    - chill: 1–2 quests/day, low to medium difficulty, optional reminders
    - steady: 2–4 quests/day, mixed difficulty, consistent scheduling
    - hardcore: 4–6 quests/day, frequent Tier 3+ quests, streaks and penalties emphasized
    """
    CHILL = "chill"
    STEADY = "steady"
    HARDCORE = "hardcore"

goals_quests = Table(
    "goals_quests",
    Base.metadata,
    Column("goal_id", Integer, ForeignKey("goals.id"), primary_key=True),
    Column("quest_id", Integer, ForeignKey("quests.id"), primary_key=True),
)


class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(Enum(UserRole), default=UserRole.USER)
    
    # Relationships
    goals = relationship("Goal", back_populates="owner")
    quests = relationship("Quest", back_populates="owner")
    stats = relationship("UserStats", back_populates="user", uselist=False)
    quest_preference: Mapped["UserQuestPreference"] = relationship("UserQuestPreference", back_populates="user", uselist=False)
    scheduled_tasks: Mapped[list["ScheduledTask"]] = relationship("ScheduledTask", back_populates="user")

class UserStats(Base):
    __tablename__ = "user_stats"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    user = relationship("User", back_populates="stats")
    
    # XP-locked leveling fields
    xp_total: Mapped[int] = mapped_column(Integer, default=0)  # Total XP ever earned
    xp_since_last_level: Mapped[int] = mapped_column(Integer, default=0)  # Progress in current level
    xp_needed_for_next: Mapped[int] = mapped_column(Integer, default=100)  # XP required for next level
    level: Mapped[int] = mapped_column(Integer, default=1)  # Current level
    
    # Quest statistics
    total_quests_created: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_accepted: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_rejected: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_failed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Goal statistics
    total_goals_created: Mapped[int] = mapped_column(Integer, default=0)
    total_goals_completed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Quest type statistics
    daily_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    penalty_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    timed_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    hidden_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Timestamps
    stats_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class UserQuestPreference(Base):
    __tablename__ = "user_quest_preferences"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True)
    user = relationship("User", back_populates="quest_preference", uselist=False)

    preffered_difficulty: Mapped[str] = mapped_column(Enum(QuestDifficulty), default=QuestDifficulty.TIER_1)
    user_intensity_profile: Mapped[str] = mapped_column(Enum(UserIntensityProfile), default=UserIntensityProfile.STEADY)
    preferred_daily_quest_time: Mapped[Optional[Time]] = mapped_column(Time, nullable=True)
    theme_tags: Mapped[Optional[list[str]]] = mapped_column(MutableList.as_mutable(SQLiteJSON), default=list)
    preferred_quest_times: Mapped[Optional[list[dict]]] = mapped_column(MutableList.as_mutable(SQLiteJSON), default=list)
    goal_intent_paragraph: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    timezone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)



class Goal(Base):
    """Goals that quests can be associated with"""
    __tablename__ = "goals"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    owner = relationship("User")
    quests = relationship("Quest", secondary=goals_quests, back_populates="goals")

class Quest(Base):
    __tablename__ = "quests"
    
    # Basic quest information
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String)
    
    # Quest type and difficulty
    quest_type: Mapped[str] = mapped_column(Enum(QuestType), default=QuestType.REGULAR)
    difficulty: Mapped[str] = mapped_column(Enum(QuestDifficulty), default=QuestDifficulty.TIER_1)
    
    # Quest Timing After Sent Out
    sent_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    time_limit_to_accept: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    time_limit_to_complete: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Quest details
    xp_reward: Mapped[int] = mapped_column(Integer, default=10)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    repeatable: Mapped[bool] = mapped_column(Boolean, default=False)

    # Status and timestamps
    status: Mapped[str] = mapped_column(Enum(QuestStatus), default=QuestStatus.PENDING)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_main_daily_quest: Mapped[bool] = mapped_column(Boolean, default=False)
    
    template_id = mapped_column(Integer, ForeignKey("main_daily_quest_templates.id"))
    

    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    
    
    theme_tags: Mapped[Optional[list[str]]] = mapped_column(MutableList.as_mutable(SQLiteJSON), default=list)

    # Relationships
    owner = relationship("User", back_populates="quests")
    goals = relationship("Goal", secondary=goals_quests, back_populates="quests")
    subtasks = relationship("QuestSubtask", cascade="all, delete-orphan", back_populates="quest")
    template = relationship("MainDailyQuestTemplate", back_populates="quests")
    
class QuestSubtask(Base):
    __tablename__ = "quest_subtasks"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    quest_id: Mapped[int] = mapped_column(Integer, ForeignKey("quests.id"))
   
    
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    
    measurement_type: Mapped[str] = mapped_column(Enum(MeasurementType), default=MeasurementType.BOOLEAN)
    goal_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # E.g., 50 reps
    completed_value: Mapped[int] = mapped_column(Integer, default=0)
    
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    quest = relationship("Quest", back_populates="subtasks")

class MainDailyQuestTemplate(Base):
    __tablename__ = "main_daily_quest_templates"
    __table_args__ = (UniqueConstraint("user_id", "active", name="uq_user_active_template"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
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
    template_id: Mapped[int] = mapped_column(Integer, ForeignKey("main_daily_quest_templates.id"))
    template = relationship("MainDailyQuestTemplate", back_populates="subtasks")
    
    title: Mapped[str] = mapped_column(String, index=True)
    measurement_type: Mapped[str] = mapped_column(Enum(MeasurementType), default=MeasurementType.BOOLEAN)
    goal_value: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # E.g., 50 reps
       
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    task_id: Mapped[str] = mapped_column(String, unique=True)
    scheduled_for: Mapped[datetime] = mapped_column(DateTime)
    task_type: Mapped[str] = mapped_column(Enum(TaskType), default=TaskType.DAILY_QUEST)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    user: Mapped["User"] = relationship(back_populates="scheduled_tasks")

