from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta

from ..database import get_db
from ..models import User
from ..schemas import UserCreate, RefreshTokenRequest, UserLogin, TokenResponse, UserSchema, UserUpdate, DailyQuestTasks, DailyQuestTask
from ..auth import (
    create_access_token, 
    create_refresh_token, 
    verify_refresh_token,
    verify_password,
    get_current_user,
    get_password_hash
)
from ..leveling import get_level_progress, get_user_stats_from_cache
from typing import List

router = APIRouter(tags=["users"])

# ============================================================================
# POST ENDPOINTS (Create/Login)
# ============================================================================

@router.post("/register", response_model=UserSchema)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    # Check if username already exists
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email already exists
    db_user = db.query(User).filter(User.email == user.email).first()
    if db_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = get_password_hash(user.password)
    db_user = User(
        username=user.username,
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@router.post("/login", response_model=TokenResponse)
def login_user(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login with username and password"""
    db_user = db.query(User).filter(User.username == user_data.username).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(user_data.password, db_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": db_user.username, "role": db_user.role.value}, 
        expires_delta=access_token_expires
    )
    
    refresh_token_expires = timedelta(days=7)
    refresh_token = create_refresh_token(
        data={"sub": db_user.username, "role": db_user.role.value}, 
        expires_delta=refresh_token_expires
    )
    return {"access_token": access_token, "refresh_token": refresh_token, "token_type": "bearer"}

@router.post("/refresh")
def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token"""
    try:
        # Verify the refresh token
        username = verify_refresh_token(request.refresh_token)
        
        # Generate new access token
        access_token_expires = timedelta(minutes=30)
        new_access_token = create_access_token(
            data={"sub": username, "role": "user"}, 
            expires_delta=access_token_expires
        )
        
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
            "message": "Token refreshed successfully"
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token"
        )

# ============================================================================
# GET ENDPOINTS (Read)
# ============================================================================

@router.get("/me", response_model=UserSchema)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@router.get("/me/profile", response_model=dict)
def get_user_profile(current_user: User = Depends(get_current_user)):
    """Get current user's profile with level progress"""
    level_progress = get_level_progress(current_user.xp)
    
    return {
        "id": current_user.id,
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role.value,
        "is_active": current_user.is_active,
        "xp": current_user.xp,
        "level": current_user.level,
        "level_progress": level_progress
    }

@router.get("/me/stats", response_model=dict)
def get_user_stats(current_user: User = Depends(get_current_user)):
    """Get current user's detailed statistics"""
    return get_user_stats_from_cache(current_user)

@router.get("/me/daily-quest-tasks", response_model=DailyQuestTasks)
def get_daily_quest_tasks(current_user: User = Depends(get_current_user)):
    """Get user's daily quest tasks"""
    daily_tasks = current_user.daily_quest_tasks or []
    return DailyQuestTasks(tasks=[DailyQuestTask(**task) for task in daily_tasks])

# ============================================================================
# PUT ENDPOINTS (Update)
# ============================================================================

@router.put("/me", response_model=UserSchema)
def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user's profile"""
    # Check if new username already exists (if changing username)
    if user_update.username and user_update.username != current_user.username:
        existing_user = db.query(User).filter(User.username == user_update.username).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken"
            )
    
    # Check if new email already exists (if changing email)
    if user_update.email and user_update.email != current_user.email:
        existing_user = db.query(User).filter(User.email == user_update.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Update fields
    update_data = user_update.dict(exclude_unset=True)
    
    # Convert daily quest tasks to JSON format for storage
    if "daily_quest_tasks" in update_data:
        daily_tasks = update_data["daily_quest_tasks"]
        if daily_tasks:
            # Validate task limit
            if len(daily_tasks) > 4:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Daily quest tasks cannot exceed 4 tasks"
                )
            # Convert to JSON format
            update_data["daily_quest_tasks"] = [task.dict() for task in daily_tasks]
    
    for field, value in update_data.items():
        setattr(current_user, field, value)
    
    db.commit()
    db.refresh(current_user)
    return current_user

@router.put("/me/daily-quest-tasks", response_model=DailyQuestTasks)
def set_daily_quest_tasks(
    daily_quest_tasks: DailyQuestTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set user's daily quest tasks"""
    # Validate task limit
    if len(daily_quest_tasks.tasks) > 4:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Daily quest tasks cannot exceed 4 tasks"
        )
    
    # Convert to JSON format for storage
    current_user.daily_quest_tasks = [task.dict() for task in daily_quest_tasks.tasks]
    db.commit()
    db.refresh(current_user)
    
    return daily_quest_tasks 