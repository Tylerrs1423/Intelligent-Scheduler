from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from sqlalchemy import func

from ..database import get_db
from ..models import User, Quest, Task, QuestStatus, UserRole
from ..schemas import UserCreate, RefreshTokenRequest, UserInfo, UserLogin, TokenResponse, LevelProgress, User as UserSchema, UserUpdate, DailyQuestTasks, DailyQuestTask
from ..auth import (
    create_access_token, 
    create_refresh_token, 
    verify_refresh_token,
    hash_password,
    verify_password,
    require_admin,
    verify_token_with_role,
    get_current_user,
    get_password_hash
)
from ..leveling import get_level_progress, get_user_stats_from_cache, update_user_stats_on_quest_created, update_user_stats_on_quest_completed, update_user_stats_on_quest_failed, update_user_stats_on_task_created, update_user_stats_on_task_completed
from typing import List

router = APIRouter(tags=["users"])

@router.post("/", response_model=UserSchema)
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Create a new user"""
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

@router.get("/me", response_model=UserSchema)
def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current user information"""
    return current_user

@router.put("/me", response_model=UserSchema)
def update_user(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current user information"""
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

@router.get("/me/daily-quest-tasks", response_model=DailyQuestTasks)
def get_daily_quest_tasks(current_user: User = Depends(get_current_user)):
    """Get user's daily quest tasks"""
    daily_tasks = current_user.daily_quest_tasks or []
    return DailyQuestTasks(tasks=[DailyQuestTask(**task) for task in daily_tasks])

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

@router.get("/me/stats")
def get_user_stats(current_user: User = Depends(get_current_user)):
    """Get user statistics"""
    return get_user_stats_from_cache(current_user)

@router.get("/", response_model=List[UserSchema])
def read_users(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all users (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    users = db.query(User).offset(skip).limit(limit).all()
    return users

@router.get("/{user_id}", response_model=UserSchema)
def read_user(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific user (admin only)"""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions"
        )
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.post("/login", response_model=TokenResponse)
def login_user(user_data: UserLogin, db: Session = Depends(get_db)):
    """Login endpoint that accepts JSON data"""
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

@router.get("/profile", response_model=dict)
def get_user_profile(current_user: dict = Depends(verify_token_with_role), db: Session = Depends(get_db)):
    """Get current user's profile with level progress"""
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    level_progress = get_level_progress(user.xp)
    
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "is_active": user.is_active,
        "xp": user.xp,
        "level": user.level,
        "level_progress": level_progress
    }

@router.get("/stats", response_model=dict)
def get_user_stats(current_user: dict = Depends(verify_token_with_role), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    stats = get_user_stats_efficient(db, user.id)
    return stats

# Admin-only endpoints
@router.get("/admin/all", response_model=list[UserInfo])
def get_all_users(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Get all users (admin only)"""
    users = db.query(User).all()
    return users

@router.get("/admin/stats")
def get_user_stats(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Get user statistics (admin only)"""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.role == "admin").count()
    
    # XP and level statistics
    total_xp = db.query(User).with_entities(func.sum(User.xp)).scalar() or 0
    avg_level = db.query(User).with_entities(func.avg(User.level)).scalar() or 0
    max_level_user = db.query(User).order_by(User.level.desc(), User.xp.desc()).first()
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "regular_users": total_users - admin_users,
        "total_xp_earned": total_xp,
        "average_level": round(avg_level, 2),
        "highest_level_user": {
            "username": max_level_user.username,
            "level": max_level_user.level,
            "xp": max_level_user.xp
        } if max_level_user else None
    }

@router.put("/admin/{user_id}/role")
def update_user_role(
    user_id: int, 
    role: str, 
    current_user: dict = Depends(require_admin), 
    db: Session = Depends(get_db)
):
    """Update user role (admin only)"""
    if role not in ["user", "admin"]:
        raise HTTPException(status_code=400, detail="Invalid role")
    
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user.role = role
    db.commit()
    db.refresh(user)
    
    return {"message": f"User {user.username} role updated to {role}"} 