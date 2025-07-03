from sqlalchemy import String, Integer, Boolean, Enum, ForeignKey, DateTime
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
    xp: Mapped[int] = mapped_column(Integer)
    
    # Quest type flags (can be multiple types)
    is_daily: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    is_penalty: Mapped[bool] = mapped_column(Boolean, default=False)
    is_timed: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Time-based fields
    earliest_completion_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completion_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    earliest_acceptance_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    acceptance_deadline: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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