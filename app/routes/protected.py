from fastapi import APIRouter, Depends
from ..auth import verify_token

router = APIRouter(tags=["protected"])

@router.get("/")
def protected_route(current_user: str = Depends(verify_token)):
    """Example protected route that requires authentication"""
    return {"message": "This is a protected route", "current_user": current_user}

@router.get("/me")
def read_users_me(current_user: str = Depends(verify_token)):
    """Get current user information"""
    return {"current_user": current_user}

