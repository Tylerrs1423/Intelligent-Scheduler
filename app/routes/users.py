from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import timedelta

from ..database import get_db
from ..models import User
from ..schemas import UserCreate, RefreshTokenRequest, UserInfo
from ..auth import (
    create_access_token, 
    create_refresh_token, 
    verify_refresh_token,
    hash_password,
    verify_password,
    require_admin
)

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
        role=user.role
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"message": f"User {user.username} created successfully"}

@router.post("/login")
def login_user(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login endpoint that works with OAuth2 form data"""
    db_user = db.query(User).filter(User.username == form_data.username).first()
    if not db_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not verify_password(form_data.password, db_user.hashed_password):
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
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "admin_users": admin_users,
        "regular_users": total_users - admin_users
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