"""User request and response schemas"""
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import Optional


class UserRegisterRequest(BaseModel):
    """Request schema for user registration"""
    email: EmailStr
    username: str = Field(..., min_length=3, max_length=100)
    password: str = Field(..., min_length=8)
    full_name: Optional[str] = Field(None, max_length=255)
    company: str = Field(..., min_length=1, max_length=255)
    role: Optional[str] = Field(default="user", pattern="^(user|reviewer|admin)$")


class UserLoginRequest(BaseModel):
    """Request schema for user login"""
    email: EmailStr
    password: str

class UserLogoutRequest(BaseModel):
    """Request schema for user logout"""
    refresh_token: str


class UserResponse(BaseModel):
    """Response schema for user data"""
    id: int
    email: str
    username: str
    full_name: Optional[str]
    company: str
    role: str = "user"
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime]
    
    class Config:
        from_attributes = True


class LoginResponse(BaseModel):
    """Response schema for login"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: UserResponse


class LogoutResponse(BaseModel):
    """Response schema for logout"""
    message: str = "Logged out successfully"


class TokenPayload(BaseModel):
    """JWT token payload"""
    sub: int  # user_id
    iat: int  # issued at
    exp: int  # expiration time


class RefreshTokenRequest(BaseModel):
    """Request schema for token refresh"""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """Request schema for changing password"""
    old_password: str
    new_password: str = Field(..., min_length=8)
