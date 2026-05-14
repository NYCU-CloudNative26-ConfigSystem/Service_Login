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
    MessageResponse,
    EmailRequest,
    EmailVerificationRequest,
    ForgotPasswordResetRequest,
)
from app.services.user_service import UserService
from app.services.auth_service import AuthService
from app.services.audit_service import AuditService
from app.utils.security import SecurityUtils
from app.core.exceptions import (
    InvalidCredentialsException,
    InvalidTokenException,
    TokenBlacklistedException,
    EmailNotVerifiedException,
    UserNotFoundException,
    AccountLockedException,
)
from app.core.logging import logger

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])
security = HTTPBearer()


def _get_client_ip(http_request: Request) -> str:
    if http_request.client and http_request.client.host:
        return http_request.client.host
    return "unknown"


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
    request: Request,
    db: Session = Depends(get_db),
):
    """Register a new user"""
    logger.info(f"Register request for: {user_data.email}")
    
    user_service = UserService(db)
    audit_service = AuditService(db)
    user = user_service.register_user(user_data)

    AuthService.send_email_verification_code(user.email)
    audit_service.log_action(
        action="REGISTER",
        user_id=user.id,
        email=user.email,
        ip_address=_get_client_ip(request),
        details={"username": user.username},
    )
    
    return UserResponse.model_validate(user)


@router.post("/verify-email/request", response_model=MessageResponse)
async def request_email_verification(
    data: EmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Request or resend verification code for registration."""
    user_service = UserService(db)
    audit_service = AuditService(db)

    user = user_service.get_user_by_email(data.email)
    AuthService.send_email_verification_code(data.email)
    audit_service.log_action(
        action="EMAIL_VERIFICATION_CODE_SENT",
        user_id=user.id,
        email=data.email,
        ip_address=_get_client_ip(request),
    )

    return MessageResponse(message="Verification code sent")


@router.post("/verify-email/confirm", response_model=MessageResponse)
async def confirm_email_verification(
    data: EmailVerificationRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Confirm email verification code and activate verified state."""
    user_service = UserService(db)
    audit_service = AuditService(db)

    AuthService.verify_email_code(data.email, data.code)
    user = user_service.verify_user_email(data.email)
    audit_service.log_action(
        action="EMAIL_VERIFIED",
        user_id=user.id,
        email=data.email,
        ip_address=_get_client_ip(request),
    )

    return MessageResponse(message="Email verified successfully")


@router.post("/login", response_model=LoginResponse)
async def login(
    login_data: UserLoginRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Login user and return access and refresh tokens"""
    logger.info(f"Login request for: {login_data.email}")
    
    user_service = UserService(db)
    audit_service = AuditService(db)
    
    try:
        # Check if account is locked
        user = user_service.get_user_by_email(login_data.email)
        AuthService.check_account_locked(user.id)
        
        # Authenticate
        user = user_service.authenticate_user(login_data)
        
        # Record successful login
        AuthService.record_successful_login(user.id)
        
        # Update last login timestamp
        user_service.update_last_login(user.id)
        
        # Create tokens
        tokens = AuthService.create_tokens(user.id)
        
        logger.info(f"Login successful for user: {user.id}")
        audit_service.log_action(
            action="LOGIN_SUCCESS",
            user_id=user.id,
            email=user.email,
            ip_address=_get_client_ip(request),
        )
        
        return LoginResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            user=UserResponse.model_validate(user),
        )
    except InvalidCredentialsException:
        # Record failed login attempt
        try:
            user = user_service.get_user_by_email(login_data.email)
            try:
                AuthService.record_failed_login(user.id)
            except AccountLockedException:
                audit_service.log_action(
                    action="LOGIN_LOCKED",
                    user_id=user.id,
                    email=user.email,
                    ip_address=_get_client_ip(request),
                )
                raise
            audit_service.log_action(
                action="LOGIN_FAILED",
                user_id=user.id,
                email=user.email,
                ip_address=_get_client_ip(request),
            )
        except UserNotFoundException:
            audit_service.log_action(
                action="LOGIN_FAILED_UNKNOWN_EMAIL",
                email=login_data.email,
                ip_address=_get_client_ip(request),
            )
        raise
    except EmailNotVerifiedException:
        audit_service.log_action(
            action="LOGIN_BLOCKED_EMAIL_NOT_VERIFIED",
            email=login_data.email,
            ip_address=_get_client_ip(request),
        )
        raise


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: UserLogoutRequest,
    http_request: Request,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Logout user"""
    logger.info(f"Logout request for user: {current_user_id}")
    
    # In this implementation, logout just invalidates the JWT token
    # If you want to maintain a blacklist, you can store the token in Redis with expiration
    audit_service = AuditService(db)
    try: 
        access_token = http_request.headers.get("Authorization", "").replace("Bearer ", "")
        AuthService.set_blacklist_token(request.refresh_token, access_token)
        audit_service.log_action(
            action="LOGOUT",
            user_id=current_user_id,
            ip_address=_get_client_ip(http_request),
        )
    except Exception as e:
        logger.error(f"Logout failed for user {current_user_id}: {e}")
        raise Exception("Failed to logout")
    
    return LogoutResponse(message="Logged out successfully")


@router.post("/refresh")
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
):
    """Refresh access token using refresh token"""
    logger.info("Token refresh request")
    
    try:
        if AuthService.is_token_blacklisted(request.refresh_token):
            logger.warning("Refresh token is blacklisted")
            raise TokenBlacklistedException()
        payload = SecurityUtils.decode_token(request.refresh_token, token_type="refresh")
        if not payload:
            raise InvalidTokenException()
        new_access_token = AuthService.refresh_access_token(request.refresh_token)
        AuditService(db).log_action(
            action="TOKEN_REFRESH",
            user_id=payload.get("sub"),
        )
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


@router.post("/forgot-password/request", response_model=MessageResponse)
async def forgot_password_request(
    data: EmailRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Send password reset code to the target email if user exists."""
    user_service = UserService(db)
    audit_service = AuditService(db)

    try:
        user = user_service.get_user_by_email(data.email)
        AuthService.send_password_reset_code(data.email)
        audit_service.log_action(
            action="PASSWORD_RESET_CODE_SENT",
            user_id=user.id,
            email=data.email,
            ip_address=_get_client_ip(request),
        )
    except UserNotFoundException:
        audit_service.log_action(
            action="PASSWORD_RESET_CODE_REQUESTED_UNKNOWN_EMAIL",
            email=data.email,
            ip_address=_get_client_ip(request),
        )

    return MessageResponse(message="If the email exists, a reset code has been sent")


@router.post("/forgot-password/reset", response_model=MessageResponse)
async def forgot_password_reset(
    data: ForgotPasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    """Reset password directly with email verification code."""
    user_service = UserService(db)
    audit_service = AuditService(db)

    AuthService.verify_password_reset_code(data.email, data.code)
    user = user_service.reset_password_by_email(data.email, data.new_password)
    audit_service.log_action(
        action="PASSWORD_RESET_SUCCESS",
        user_id=user.id,
        email=data.email,
        ip_address=_get_client_ip(request),
    )

    return MessageResponse(message="Password reset successfully")
