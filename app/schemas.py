from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, time
from typing import Optional, List
from .models import UserRole, QuestStatus, QuestType, QuestDifficulty, MeasurementType, UserIntensityProfile

class DailyQuestGoal(BaseModel):
    title: str
    description: str
    
    class Config:
        from_attributes = True

class DailyQuestGoals(BaseModel):
    goals: List[DailyQuestGoal]
    
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
    daily_quest_goals: Optional[List[DailyQuestGoal]] = None

class UserStatsSchema(BaseModel):
    xp_total: int
    xp_since_last_level: int
    xp_needed_for_next: int
    level: int
    total_quests_created: int
    total_quests_completed: int
    total_quests_failed: int
    total_goals_created: int
    total_goals_completed: int
    daily_quests_completed: int
    penalty_quests_completed: int
    timed_quests_completed: int
    hidden_quests_completed: int
    stats_updated_at: datetime
    
    class Config:
        from_attributes = True

class UserSchema(UserBase):
    id: int
    is_active: bool
    role: UserRole
    stats: Optional[UserStatsSchema] = None
    
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
    
    class Config:
        from_attributes = True

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

class GoalCreate(BaseModel):
    title: str
    description: Optional[str] = ""

class GoalUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None

class GoalOut(BaseModel):
    id: int
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    owner_id: int

    class Config:
        from_attributes = True

# Quests
class QuestCreate(BaseModel):
    title: str
    description: str
    xp_reward: int
    quest_type: QuestType = QuestType.REGULAR
    goal_id: Optional[int] = None  # Optional goal relationship
    theme_tags: Optional[List[str]] = Field(default_factory=list, description="Theme tags for this quest")
    
    # Time-based fields (only for timed quests)
    completion_deadline: Optional[datetime] = None
    time_limit_minutes: Optional[int] = None

class QuestUpdate(BaseModel):
    status: Optional[QuestStatus] = None

class QuestOut(BaseModel):
    id: int
    title: str
    description: str
    xp_reward: int
    quest_type: QuestType
    difficulty: QuestDifficulty
    created_at: datetime
    updated_at: datetime
    status: QuestStatus
    owner_id: int
    theme_tags: List[str] = Field(default_factory=list, description="Theme tags for this quest")
    
    # Time-based fields (only for timed quests)
    deadline: Optional[datetime]
    time_limit_minutes: Optional[int]
    repeatable: bool
    
    # Quest state timestamps
    completed_at: Optional[datetime]

    class Config:
        from_attributes = True

class SubtaskIn(BaseModel):
    title: str
    measurement_type: MeasurementType = MeasurementType.BOOLEAN
    goal_value: Optional[int] = None

class SubtaskOut(BaseModel):
    id: int
    title: str
    measurement_type: MeasurementType
    goal_value: Optional[int]
    class Config:
        orm_mode = True

class DailyTemplateIn(BaseModel):
    title: str
    description: str
    xp_reward: int = 100

class DailyTemplateOut(BaseModel):
    id: int
    title: str
    description: str
    xp_reward: int
    active: bool
    created_at: datetime
    updated_at: datetime
    subtasks: List[SubtaskOut]
    class Config:
        orm_mode = True

class UserQuestPreferenceIn(BaseModel):
    preferred_daily_quest_time: Optional[str] = Field(None, description="Time of day in HH:MM format for daily quest")
    theme_tags: List[str] = Field(default_factory=list)
    goal_intent_paragraph: Optional[str] = Field(None, max_length=150, description="User's goal intent paragraph (max 150 characters)")
    enabled: bool = True
    timezone: Optional[str] = None
    preffered_difficulty: QuestDifficulty = QuestDifficulty.TIER_1
    user_intensity_profile: UserIntensityProfile = UserIntensityProfile.STEADY

class UserQuestPreferenceOut(BaseModel):
    id: int
    preferred_daily_quest_time: Optional[time]
    theme_tags: List[str]
    goal_intent_paragraph: Optional[str]
    enabled: bool
    timezone: Optional[str]
    preffered_difficulty: QuestDifficulty
    user_intensity_profile: UserIntensityProfile
    created_at: datetime
    updated_at: datetime
    class Config:
        from_attributes = True

class QuestTimeRangeIn(BaseModel):
    start: str = Field(..., description="Start time in HH:MM format")
    end: str = Field(..., description="End time in HH:MM format")

class QuestTimeRangeListOut(BaseModel):
    preferred_quest_times: List[QuestTimeRangeIn]

class ThemeTagIn(BaseModel):
    theme_tag: str = Field(..., description="Theme tag (must be one of the allowed categories)")

class ThemeTagListOut(BaseModel):
    theme_tags: List[str]

