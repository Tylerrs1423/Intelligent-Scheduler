from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from datetime import timedelta

from ..database import get_db
from ..models import User
from ..schemas import UserCreate, RefreshTokenRequest, UserLogin, TokenResponse, UserSchema, UserUpdate, DailyQuestGoals, DailyQuestGoal
from ..auth import (
    create_access_token, 
    create_refresh_token, 
    verify_refresh_token,
    verify_password,
    get_current_user,
    get_password_hash
)
from ..leveling import get_user_stats
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
    
    # Create UserStats record for the new user
    from ..models import UserStats
    user_stats = UserStats(user_id=db_user.id)
    db.add(user_stats)
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
def refresh_token(request: RefreshTokenRequest, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    try:
        # Verify the refresh token
        username = verify_refresh_token(request.refresh_token)
        
        # Get user from database to get their actual role
        db_user = db.query(User).filter(User.username == username).first()
        if not db_user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Generate new access token with correct role
        access_token_expires = timedelta(minutes=30)
        new_access_token = create_access_token(
            data={"sub": username, "role": db_user.role.value}, 
            expires_delta=access_token_expires
        )
        
        # Generate new refresh token
        refresh_token_expires = timedelta(days=7)
        new_refresh_token = create_refresh_token(
            data={"sub": username, "role": db_user.role.value}, 
            expires_delta=refresh_token_expires
        )
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token,
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
def get_current_user_info(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user information"""
    # Ensure user has stats record
    if not current_user.stats:
        from ..models import UserStats
        user_stats = UserStats(user_id=current_user.id)
        db.add(user_stats)
        db.commit()
        db.refresh(current_user)
    
    return current_user


@router.get("/me/stats", response_model=dict)
def get_user_stats_route(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get current user's detailed statistics"""
    return get_user_stats(current_user, db)

@router.get("/me/daily-quest-goals", response_model=DailyQuestGoals)
def get_daily_quest_goals(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Get user's daily quest goals"""
    # TODO: Replace with actual DB query for user's daily quest goals
    goals = []  # Placeholder: return empty list if no goals
    return DailyQuestGoals(goals=goals)

# ============================================================================
# PUT ENDPOINTS (Update)
# ============================================================================

@router.put("/me", response_model=UserSchema)
def update_user_profile(
    user_update: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    pass

@router.put("/me/daily-quest-goals", response_model=DailyQuestGoals)
def set_daily_quest_goals(
    daily_quest_goals: DailyQuestGoals,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set user's daily quest goals"""
    pass