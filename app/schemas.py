from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from typing import Optional, List
from .models import UserRole, QuestStatus

class DailyQuestTask(BaseModel):
    title: str
    description: str
    
    class Config:
        from_attributes = True

class DailyQuestTasks(BaseModel):
    tasks: List[DailyQuestTask]
    
    class Config:
        from_attributes = True

class UserBase(BaseModel):
    username: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    daily_quest_time: Optional[datetime] = None
    daily_quest_tasks: Optional[List[DailyQuestTask]] = None

class UserSchema(UserBase):
    id: int
    is_active: bool
    role: UserRole
    xp: int
    level: int
    daily_quest_time: Optional[datetime] = None
    daily_quest_tasks: Optional[List[DailyQuestTask]] = None
    
    # Cached Statistics
    total_quests_created: int
    total_quests_completed: int
    total_quests_failed: int
    total_tasks_created: int
    total_tasks_completed: int
    total_xp_earned: int
    daily_quests_completed: int
    penalty_quests_completed: int
    timed_quests_completed: int
    hidden_quests_completed: int
    stats_updated_at: datetime
    
    class Config:
        from_attributes = True

class UserLogin(BaseModel):
    username: str
    password: str

class RefreshTokenRequest(BaseModel):
    refresh_token: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str

class RefreshResponse(BaseModel):
    access_token: str
    token_type: str
    message: str

class UserResponse(BaseModel):
    message: str

class UserInfo(BaseModel):
    id: int
    username: str
    email: str
    is_active: bool
    role: UserRole
    xp: int
    level: int

class LevelProgress(BaseModel):
    current_level: int
    current_xp: int
    xp_in_current_level: int
    xp_for_next_level: int
    progress_percentage: float
    is_max_level: bool

class QuestCompletionResponse(BaseModel):
    quest: dict
    xp_gained: int
    levels_gained: int
    new_xp: int
    new_level: int
    level_progress: LevelProgress

class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = ""

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None

class TaskOut(BaseModel):
    id: int
    title: str
    description: str
    completed: bool
    created_at: datetime
    updated_at: datetime
    owner_id: int

    class Config:
        from_attributes = True

# Quests
class QuestCreate(BaseModel):
    title: str
    description: str
    xp: int
    task_id: Optional[int] = None  # Optional task relationship
    
    # Quest type flags
    is_daily: bool = False
    is_hidden: bool = False
    is_penalty: bool = False
    is_timed: bool = False
    
    # Time-based fields
    earliest_completion_time: Optional[datetime] = None
    completion_deadline: Optional[datetime] = None
    earliest_acceptance_time: Optional[datetime] = None
    acceptance_deadline: Optional[datetime] = None
    time_limit_minutes: Optional[int] = None

class QuestUpdate(BaseModel):
    status: Optional[QuestStatus] = None

class QuestOut(BaseModel):
    id: int
    title: str
    description: str
    xp: int
    created_at: datetime
    status: QuestStatus
    owner_id: int
    task_id: Optional[int]  # Optional task relationship
    
    # Quest type flags
    is_daily: bool
    is_hidden: bool
    is_penalty: bool
    is_timed: bool
    
    # Time-based fields
    earliest_completion_time: Optional[datetime]
    completion_deadline: Optional[datetime]
    earliest_acceptance_time: Optional[datetime]
    acceptance_deadline: Optional[datetime]
    time_limit_minutes: Optional[int]
    
    # Quest state timestamps
    accepted_at: Optional[datetime]
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

