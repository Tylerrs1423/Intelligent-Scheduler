from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta, datetime
from sqlalchemy import func

from ..database import get_db
from ..models import User, Quest, Task, QuestStatus
from ..schemas import UserCreate, RefreshTokenRequest, UserInfo, UserLogin, TokenResponse, LevelProgress
from ..auth import (
    create_access_token, 
    create_refresh_token, 
    verify_refresh_token,
    hash_password,
    verify_password,
    require_admin,
    verify_token_with_role
)
from ..leveling import get_level_progress

router = APIRouter(tags=["users"])

@router.put("/register")
def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """Register a new user"""
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=409, detail="User already exists")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=409, detail="Email already exists")

    hashed_password = hash_password(user.password)
    db_user = User(
        username=user.username, 
        email=user.email, 
        hashed_password=hashed_password,
        role=user.role,
        xp=0,  # Start with 0 XP
        level=1  # Start at level 1
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": f"User {user.username} created successfully"}

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
    """Get detailed statistics for the current user"""
    user = db.query(User).filter(User.username == current_user["username"]).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Quest statistics
    total_quests = db.query(Quest).filter(Quest.owner_id == user.id).count()
    completed_quests = db.query(Quest).filter(
        Quest.owner_id == user.id, 
        Quest.status == QuestStatus.COMPLETED
    ).count()
    pending_quests = db.query(Quest).filter(
        Quest.owner_id == user.id, 
        Quest.status == QuestStatus.PENDING
    ).count()
    accepted_quests = db.query(Quest).filter(
        Quest.owner_id == user.id, 
        Quest.status == QuestStatus.ACCEPTED
    ).count()
    rejected_quests = db.query(Quest).filter(
        Quest.owner_id == user.id, 
        Quest.status == QuestStatus.REJECTED
    ).count()
    failed_quests = db.query(Quest).filter(
        Quest.owner_id == user.id, 
        Quest.status.in_([QuestStatus.EXPIRED, QuestStatus.FAILED])
    ).count()
    
    # Quest type breakdown
    daily_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.is_daily == True
    ).count()
    penalty_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.is_penalty == True
    ).count()
    timed_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.is_timed == True
    ).count()
    hidden_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.is_hidden == True
    ).count()
    
    # Task statistics
    total_tasks = db.query(Task).filter(Task.owner_id == user.id).count()
    completed_tasks = db.query(Task).filter(
        Task.owner_id == user.id, 
        Task.completed == True
    ).count()
    pending_tasks = total_tasks - completed_tasks
    
    # XP and level statistics
    level_progress = get_level_progress(user.xp)
    
    # Recent activity (last 7 days)
    week_ago = datetime.utcnow() - timedelta(days=7)
    recent_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.created_at >= week_ago
    ).count()
    recent_completed_quests = db.query(Quest).filter(
        Quest.owner_id == user.id,
        Quest.status == QuestStatus.COMPLETED,
        Quest.completed_at >= week_ago
    ).count()
    
    # Calculate completion rates
    quest_completion_rate = (completed_quests / total_quests * 100) if total_quests > 0 else 0
    task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Calculate average XP per quest (for completed quests)
    completed_quest_xp = db.query(func.sum(Quest.xp)).filter(
        Quest.owner_id == user.id,
        Quest.status == QuestStatus.COMPLETED
    ).scalar() or 0
    avg_xp_per_quest = completed_quest_xp / completed_quests if completed_quests > 0 else 0
    
    return {
        "user_info": {
            "username": user.username,
            "level": user.level,
            "xp": user.xp,
            "level_progress": level_progress
        },
        "quest_statistics": {
            "total_quests": total_quests,
            "completed_quests": completed_quests,
            "pending_quests": pending_quests,
            "accepted_quests": accepted_quests,
            "rejected_quests": rejected_quests,
            "failed_quests": failed_quests,
            "completion_rate": round(quest_completion_rate, 2),
            "quest_types": {
                "daily": daily_quests,
                "penalty": penalty_quests,
                "timed": timed_quests,
                "hidden": hidden_quests,
                "regular": total_quests - daily_quests - penalty_quests - timed_quests - hidden_quests
            }
        },
        "task_statistics": {
            "total_tasks": total_tasks,
            "completed_tasks": completed_tasks,
            "pending_tasks": pending_tasks,
            "completion_rate": round(task_completion_rate, 2)
        },
        "xp_statistics": {
            "total_xp_earned": user.xp,
            "avg_xp_per_quest": round(avg_xp_per_quest, 2),
            "total_xp_from_quests": completed_quest_xp
        },
        "recent_activity": {
            "quests_created_this_week": recent_quests,
            "quests_completed_this_week": recent_completed_quests
        },
        "achievements": {
            "quest_master": completed_quests >= 100,
            "task_completer": completed_tasks >= 50,
            "level_achiever": user.level >= 10,
            "daily_streak": daily_quests >= 10,
            "penalty_survivor": penalty_quests >= 5
        }
    }

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