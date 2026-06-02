"""Authentication endpoints"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.database.connection import get_db
from app.schemas.user import (
    UserLoginRequest,
    UserLogoutRequest,
    UserRegisterRequest,
    LoginResponse,
    LogoutResponse,
    UserResponse,
    RefreshTokenRequest,
)
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.utils.security import SecurityUtils
from app.core.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    TokenBlacklistedException,
    UserNotFoundException,
)
from app.core.logging import logger

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security = HTTPBearer()


def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """Dependency to get current user ID from Bearer token"""
    token = credentials.credentials
    payload = SecurityUtils.decode_token(token, token_type="access")
    
    if not payload:
        logger.warning("Invalid or expired access token")
        raise InvalidTokenException()
    
    user_id = payload.get("sub")
    if not user_id:
        logger.warning("Invalid token payload")
        raise InvalidTokenException()
    
    if AuthService.is_token_blacklisted(token):
        logger.warning("Access token is blacklisted")
        raise TokenBlacklistedException()
    
    return user_id


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegisterRequest,
    db: Session = Depends(get_db),
):
    """Register a new user"""
    logger.info(f"Register request for: {user_data.email}")
    
    user_service = UserService(db)
    user = user_service.register_user(user_data)
    
    return UserResponse.model_validate(user)


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: UserLoginRequest,
    db: Session = Depends(get_db),
):
    """Login user and return access and refresh tokens"""
    logger.info(f"Login request for: {login_data.email}")
    
    user_service = UserService(db)
    
    existing_user = None
    try:
        # Check if account is locked (also confirms user exists)
        try:
            existing_user = user_service.get_user_by_email(login_data.email)
        except UserNotFoundException:
            raise InvalidCredentialsException()
        AuthService.check_account_locked(existing_user.id)

        # Authenticate
        user = user_service.authenticate_user(login_data)

        # Record successful login
        AuthService.record_successful_login(user.id)

        # Update last login timestamp
        user_service.update_last_login(user.id)

        # Create tokens
        tokens = AuthService.create_tokens(user.id, company=user.company, username=user.username, role=user.role)

        logger.info(f"Login successful for user: {user.id}")
        access_token = tokens["access_token"]
        return LoginResponse(
            access_token=access_token,
            refresh_token=tokens["refresh_token"],
            user=UserResponse.model_validate(user),
        )
    except InvalidCredentialsException:
        if existing_user is not None:
            try:
                AuthService.record_failed_login(existing_user.id)
            except Exception:
                pass
        raise


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: UserLogoutRequest,
    http_request: Request,
    current_user_id: int = Depends(get_current_user_id),
):
    """Logout user"""
    logger.info(f"Logout request for user: {current_user_id}")
    
    # In this implementation, logout just invalidates the JWT token
    # If you want to maintain a blacklist, you can store the token in Redis with expiration
    try:
        access_token = http_request.headers.get("Authorization", "").replace("Bearer ", "")
        AuthService.set_blacklist_token(request.refresh_token, access_token)
        payload = SecurityUtils.decode_token(access_token)
        session_id = payload.get("sid", "") if payload else ""
        if session_id:
            AuthService.destroy_session(session_id)
    except Exception as e:
        logger.error(f"Logout failed for user {current_user_id}: {e}")
        raise Exception("Failed to logout")
    
    return LogoutResponse(message="Logged out successfully")


@router.post("/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
):
    """Refresh access token using refresh token"""
    logger.info("Token refresh request")
    
    try:
        if AuthService.is_token_blacklisted(request.refresh_token):
            logger.warning("Refresh token is blacklisted")
            raise TokenBlacklistedException()
        new_access_token = AuthService.refresh_access_token(request.refresh_token)
        return {
            "access_token": new_access_token,
            "token_type": "bearer",
        }
    except Exception as e:
        logger.error(f"Token refresh failed: {e}")
        raise InvalidTokenException()


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Get current user information"""

    try:
        logger.info(f"Get current user request for user: {current_user_id}")
        
        user_service = UserService(db)
        user = user_service.get_user_by_id(current_user_id)
        
        return UserResponse.model_validate(user)
    except Exception as e:
        logger.error(f"Failed to get current user: {e}")
        raise Exception("Failed to get current user information")
