from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import UserInfo
from ..auth import require_admin

router = APIRouter(tags=["admin"])

@router.get("/dashboard")
def admin_dashboard(current_user: dict = Depends(require_admin)):
    """Admin dashboard overview"""
    return {
        "message": "Welcome to Admin Dashboard",
        "admin_user": current_user["username"],
        "available_actions": [
            "GET /admin/users - View all users",
            "GET /admin/stats - View user statistics", 
            "PUT /admin/users/{id}/role - Update user role",
            "GET /admin/system-info - System information"
        ]
    }

@router.get("/users", response_model=list[UserInfo])
def get_all_users(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Get all users (admin only)"""
    users = db.query(User).all()
    return users

@router.get("/users/{user_id}", response_model=UserInfo)
def get_user_by_id(user_id: int, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Get specific user by ID (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

@router.put("/users/{user_id}/role")
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
    
    # Prevent admin from removing their own admin role
    if user.username == current_user["username"] and role == "user":
        raise HTTPException(status_code=400, detail="Cannot remove your own admin role")
    
    user.role = role
    db.commit()
    db.refresh(user)
    
    return {"message": f"User {user.username} role updated to {role}"}

@router.put("/users/{user_id}/status")
def update_user_status(
    user_id: int, 
    is_active: bool, 
    current_user: dict = Depends(require_admin), 
    db: Session = Depends(get_db)
):
    """Update user active status (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deactivating themselves
    if user.username == current_user["username"] and not is_active:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")
    
    user.is_active = is_active
    db.commit()
    db.refresh(user)
    
    status_text = "activated" if is_active else "deactivated"
    return {"message": f"User {user.username} {status_text}"}

@router.get("/stats")
def get_user_stats(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Get user statistics (admin only)"""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    admin_users = db.query(User).filter(User.role == "admin").count()
    inactive_users = total_users - active_users
    
    return {
        "total_users": total_users,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "admin_users": admin_users,
        "regular_users": total_users - admin_users,
        "active_percentage": round((active_users / total_users) * 100, 2) if total_users > 0 else 0
    }

@router.delete("/users/{user_id}")
def delete_user(user_id: int, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Delete a user (admin only)"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    db.delete(user)
    db.commit()
    return {"message": "User deleted"}

@router.get("/system-info")
def get_system_info(current_user: dict = Depends(require_admin)):
    """Get system information (admin only)"""
    import platform
    import psutil
    
    return {
        "system": platform.system(),
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "cpu_count": psutil.cpu_count(),
        "memory_total": f"{psutil.virtual_memory().total / (1024**3):.2f} GB",
        "memory_available": f"{psutil.virtual_memory().available / (1024**3):.2f} GB",
        "disk_usage": f"{psutil.disk_usage('/').percent:.1f}%"
    } 