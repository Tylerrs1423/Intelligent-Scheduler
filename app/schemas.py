from pydantic import BaseModel, Field, EmailStr
from datetime import datetime, time
from typing import Optional, List, Tuple
from .models import UserRole, QuestStatus, QuestCategory, QuestGeneration, QuestType, QuestDifficulty, GoalStatus, PriorityLevel, MeasurementType, TaskType, UserIntensityProfile, SourceType, EventMood, PreferredTimeOfDay, TaskDifficulty, SchedulingFlexibility

# ----------------- User Schemas ---------------------


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
    sleep_start: Optional[time] = None
    sleep_end: Optional[time] = None
    max_daily_hours: Optional[float] = 8.0

class UserCreate(UserBase):
    password: str
    sleep_start: Optional[time] = None
    sleep_end: Optional[time] = None
    max_daily_hours: Optional[float] = 8.0

class UserUpdate(BaseModel):
    username: Optional[str] = None
    email: Optional[EmailStr] = None
    daily_quest_time: Optional[datetime] = None
    daily_quest_goals: Optional[List[DailyQuestGoal]] = None
    sleep_start: Optional[time] = None
    sleep_end: Optional[time] = None
    max_daily_hours: Optional[float] = None

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
    sleep_start: Optional[time] = None
    sleep_end: Optional[time] = None
    max_daily_hours: Optional[float] = None
    
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
    sleep_start: Optional[time] = None
    sleep_end: Optional[time] = None
    max_daily_hours: Optional[float] = None
    
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


# ----------------- Subgoal Schemas ---------------------

class SubgoalCreate(BaseModel):
    title: str
    description: Optional[str] = ""

class SubgoalOut(BaseModel):
    id: int
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    goal_id: int
    is_completed: bool

    class Config:
        from_attributes = True

# ----------------- Goal Schemas ---------------------
class GoalCreate(BaseModel):
    title: str
    preferred_time_of_day: Optional[PreferredTimeOfDay] = None
    difficulty: Optional[TaskDifficulty] = None
    expected_duration: Optional[int] = None  # in minutes
    description: Optional[str] = None
    subgoals: Optional[List[str]] = None
    deadline: Optional[datetime] = None
    frequency: Optional[str] = None  # e.g., '3 times this week', 'Daily', 'Every Monday'
    priority: Optional[PriorityLevel] = PriorityLevel.MEDIUM
    # Advanced (hidden by default)
    exact_times: Optional[List[datetime]] = None  # e.g., ["2024-07-01T07:00:00"]
    preferred_time_windows: Optional[List[Tuple[time, time]]] = None  # e.g., [(time(18,0), time(21,0))]
    duration_range: Optional[Tuple[int, int]] = None  # (min_minutes, max_minutes)
    repeat_rules: Optional[str] = None  # RRULE string
    buffer_before: Optional[int] = None  # minutes
    buffer_after: Optional[int] = None  # minutes
    constraints: Optional[str] = None  # e.g., 'Never on weekends', or specific days
    depends_on_event_id: Optional[int] = None
    depends_on_goal_id: Optional[int] = None
    location_tag: Optional[str] = None  # e.g., 'Home', 'Work', 'Gym'

class GoalUpdate(BaseModel):
    title: Optional[str] = None
    preferred_time_of_day: Optional[PreferredTimeOfDay] = None
    difficulty: Optional[TaskDifficulty] = None
    expected_duration: Optional[int] = None
    description: Optional[str] = None
    subgoals: Optional[List[str]] = None
    deadline: Optional[datetime] = None
    frequency: Optional[str] = None
    priority: Optional[PriorityLevel] = None
    exact_times: Optional[List[datetime]] = None
    preferred_time_windows: Optional[List[Tuple[time, time]]] = None
    duration_range: Optional[Tuple[int, int]] = None
    repeat_rules: Optional[str] = None
    buffer_before: Optional[int] = None
    buffer_after: Optional[int] = None
    constraints: Optional[str] = None
    depends_on_event_id: Optional[int] = None
    depends_on_goal_id: Optional[int] = None
    location_tag: Optional[str] = None

class GoalOut(BaseModel):
    id: int
    title: str
    description: str
    created_at: datetime
    updated_at: datetime
    user_id: int
    priority: Optional[int]
    difficulty: TaskDifficulty
    estimated_duration_minutes: Optional[int]
    due_date: Optional[datetime]
    status: GoalStatus
    subgoals: List[SubgoalOut] = []

    class Config:
        from_attributes = True




# ----------------- Quest Schemas ---------------------
class QuestCreate(BaseModel):
    title: str
    description: str
    xp_reward: int
    quest_type: QuestType = QuestType.REGULAR
    goal_id: Optional[int] = None  # Optional goal relationship
    theme_tags: Optional[List[str]] = Field(default_factory=list, description="Theme tags for this quest")
    
    # Scheduling fields
    priority: int = 2  # Default to MEDIUM priority
    # due_at field removed - only deadline is used for date constraints
    preferred_time_of_day: PreferredTimeOfDay = PreferredTimeOfDay.NO_PREFERENCE
    duration_minutes: Optional[int] = None
    
    # Chunking fields
    chunk_index: int = 1
    chunk_count: int = 1
    is_chunked: bool = False
    base_title: Optional[str] = None
    
    # Recurrence field - RRULE string (RFC 5545 standard)
    recurrence_rule: Optional[str] = None  # RRULE string for recurrence patterns
    
    # Buffer fields
    buffer_before: int = 0
    buffer_after: int = 0
    
    # Scheduling flexibility
    scheduling_flexibility: SchedulingFlexibility = SchedulingFlexibility.FLEXIBLE
    
    # Time window constraints (for AI scheduling)
    soft_start: Optional[time] = None  # Preferred start time (soft limit)
    soft_end: Optional[time] = None    # Preferred end time (soft limit)
    hard_start: Optional[time] = None  # Must start after this time (hard limit)
    hard_end: Optional[time] = None    # Must end before this time (hard limit)
    
    # Strict scheduling rule overrides
    allow_time_deviation: bool = False      # Allow deviation from time preference
    allow_urgent_override: bool = False     # Allow urgent deadline override
    allow_same_day_recurring: bool = False  # Allow same-day recurring instances
    
    # Time-based fields (legacy - only for timed quests)
    completion_deadline: Optional[datetime] = None
    time_limit_minutes: Optional[int] = None

class QuestUpdate(BaseModel):
    status: Optional[QuestStatus] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[int] = None
    # due_at field removed - only deadline is used for date constraints
    preferred_time_of_day: Optional[PreferredTimeOfDay] = None
    duration_minutes: Optional[int] = None
    chunk_index: Optional[int] = None
    chunk_count: Optional[int] = None
    is_chunked: Optional[bool] = None
    base_title: Optional[str] = None
    recurrence_rule: Optional[str] = None
    buffer_before: Optional[int] = None
    buffer_after: Optional[int] = None
    
    # Strict scheduling rule overrides
    allow_time_deviation: Optional[bool] = None      # Allow deviation from time preference
    allow_urgent_override: Optional[bool] = None     # Allow urgent deadline override
    allow_same_day_recurring: Optional[bool] = None  # Allow same-day recurring instances
    
    # Scheduling flexibility
    scheduling_flexibility: Optional[SchedulingFlexibility] = None

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
    
    # Scheduling fields
    priority: int
    # due_at field removed - only deadline is used for date constraints
    preferred_time_of_day: PreferredTimeOfDay
    duration_minutes: Optional[int]
    
    # Chunking fields
    chunk_index: int
    chunk_count: int
    is_chunked: bool
    base_title: Optional[str]
    
    # Recurrence field - RRULE string (RFC 5545 standard)
    recurrence_rule: Optional[str]
    
    # Buffer fields
    buffer_before: int
    buffer_after: int
    
    # Scheduling flexibility
    scheduling_flexibility: SchedulingFlexibility
    
    # Time window constraints (for AI scheduling)
    soft_start: Optional[time]
    soft_end: Optional[time]
    hard_start: Optional[time]
    hard_end: Optional[time]
    
    # Strict scheduling rule overrides
    allow_time_deviation: bool
    allow_urgent_override: bool
    allow_same_day_recurring: bool
    
    # Time-based fields (legacy - only for timed quests)
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
        from_attributes = True

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
        from_attributes = True

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

class EventCreate(BaseModel):
    title: str
    description: str = ""
    start_time: Optional[datetime] = None  # Required for FIXED, not allowed for FLEXIBLE
    end_time: Optional[datetime] = None    # Required for FIXED, not allowed for FLEXIBLE
    scheduling_flexibility: SchedulingFlexibility = SchedulingFlexibility.FIXED
    buffer_before: Optional[int] = None
    buffer_after: Optional[int] = None
    priority: PriorityLevel = PriorityLevel.MEDIUM
    # Flexible event fields
    duration: Optional[int] = None  # Required for FLEXIBLE (in minutes)
    time_preference: Optional[PreferredTimeOfDay] = None  # Morning, Afternoon, Evening
    # Other fields
    recurrence_rule: Optional[str] = None
    depends_on_event_id: Optional[int] = None
    depends_on_quest_id: Optional[int] = None
    mood: Optional[EventMood] = None
    max_moves: Optional[int] = None

class EventUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    # scheduling_flexibility: Optional[SchedulingFlexibility] = None
    # is_auto_generated: Optional[bool] = None
    # source: Optional[SourceType] = None
    # source_id: Optional[int] = None
    # earliest_start: Optional[datetime] = None
    # latest_end: Optional[datetime] = None
    # priority: Optional[PriorityLevel] = None
    # allowed_days: Optional[list[int]] = None
    # soft_start: Optional[time] = None
    # soft_end: Optional[time] = None
    # hard_start: Optional[time] = None
    # hard_end: Optional[time] = None
    # min_duration: Optional[int] = None
    # max_duration: Optional[int] = None
    buffer_before: Optional[int] = None
    buffer_after: Optional[int] = None
    # recurrence_rule: Optional[str] = None
    # depends_on_event_id: Optional[int] = None
    # depends_on_quest_id: Optional[int] = None
    # mood: Optional[EventMood] = None
    # max_moves: Optional[int] = None

class EventOut(BaseModel):
    id: int
    user_id: int
    title: str
    description: str
    start_time: datetime
    end_time: datetime
    scheduling_flexibility: SchedulingFlexibility
    is_auto_generated: bool
    source: Optional[SourceType]
    source_id: Optional[int]
    earliest_start: Optional[datetime]
    latest_end: Optional[datetime]
    priority: PriorityLevel
    allowed_days: Optional[list[int]]
    soft_start: Optional[time]
    soft_end: Optional[time]
    hard_start: Optional[time]
    hard_end: Optional[time]
    min_duration: Optional[int]
    max_duration: Optional[int]
    buffer_before: Optional[int]
    buffer_after: Optional[int]
    recurrence_rule: Optional[str]
    depends_on_event_id: Optional[int]
    depends_on_quest_id: Optional[int]
    mood: Optional[EventMood]
    max_moves: Optional[int]
    moves_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

