from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional
from .models import UserRole

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: UserRole = UserRole.USER

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
        orm_mode = True

