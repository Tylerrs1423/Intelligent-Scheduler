from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
import enum
from datetime import datetime
from typing import Optional

class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"

class QuestStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    EXPIRED = "expired"
    FAILED = "failed"

class QuestType(str, enum.Enum):
    REGULAR = "regular"
    DAILY = "daily"
    HIDDEN = "hidden"
    PENALTY = "penalty"
    TIMED = "timed"

class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    hashed_password: Mapped[str]
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(Enum(UserRole), default=UserRole.USER)
    
    # XP and Leveling system
    xp: Mapped[int] = mapped_column(Integer, default=0)
    level: Mapped[int] = mapped_column(Integer, default=1)
    
    # Daily quest preferences
    daily_quest_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    daily_quest_tasks: Mapped[Optional[str]] = mapped_column(JSON, nullable=True)  # Store as JSON array
    
    # Cached Statistics (updated incrementally)
    total_quests_created: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_quests_failed: Mapped[int] = mapped_column(Integer, default=0)
    total_tasks_created: Mapped[int] = mapped_column(Integer, default=0)
    total_tasks_completed: Mapped[int] = mapped_column(Integer, default=0)
    total_xp_earned: Mapped[int] = mapped_column(Integer, default=0)
    
    # Quest type counters
    daily_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    penalty_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    timed_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    hidden_quests_completed: Mapped[int] = mapped_column(Integer, default=0)
    
    # Last updated timestamp for stats
    stats_updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    tasks = relationship("Task", back_populates="owner")
    quests = relationship("Quest", back_populates="owner")

class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String, index=True)
    description: Mapped[str] = mapped_column(String, default="")
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="tasks")
    quests = relationship("Quest", back_populates="task")
    
class Quest(Base):
    __tablename__ = "quests"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String)
    description: Mapped[str] = mapped_column(String)
    xp_reward: Mapped[int] = mapped_column(Integer)  # Renamed from xp to xp_reward
    
    # Quest type (single type instead of multiple boolean flags)
    quest_type: Mapped[str] = mapped_column(Enum(QuestType), default=QuestType.REGULAR)
    
    # Time-based fields
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    earliest_acceptance: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    earliest_completion: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    time_limit_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # For timed quests
    
    # Quest state timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    accepted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    
    # Quest status and relationships
    status: Mapped[str] = mapped_column(Enum(QuestStatus), default=QuestStatus.PENDING)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"))
    task_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tasks.id"), nullable=True)  # Optional task relationship
    
    # Relationships
    owner = relationship("User", back_populates="quests")
    task = relationship("Task", back_populates="quests")