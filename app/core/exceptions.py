"""Custom exceptions for the application"""
from fastapi import HTTPException, status

class TokenBlacklistedException(HTTPException):
    """Raised when token is blacklisted (e.g. after logout)"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is blacklisted",
            headers={"WWW-Authenticate": "Bearer"},
        )

class InvalidCredentialsException(HTTPException):
    """Raised when login credentials are invalid"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )


class PasswordTooLongException(HTTPException):
    """Raised when a password exceeds bcrypt's 72-byte limit"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password cannot exceed 72 bytes when encoded as UTF-8",
        )


class UserNotFoundException(HTTPException):
    """Raised when user is not found"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )


class UserAlreadyExistsException(HTTPException):
    """Raised when user already exists"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists",
        )


class AccountLockedException(HTTPException):
    """Raised when account is locked due to too many login attempts"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account locked due to too many failed login attempts. Please try later.",
        )


class InvalidTokenException(HTTPException):
    """Raised when token is invalid or expired"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


class NotAuthorizedException(HTTPException):
    """Raised when user is not authorized"""
    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )


class EmailNotVerifiedException(HTTPException):
    """Raised when user attempts login before verifying email."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email is not verified",
        )


class VerificationCodeInvalidException(HTTPException):
    """Raised when one-time verification code does not match."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid verification code",
        )


class VerificationCodeExpiredException(HTTPException):
    """Raised when one-time verification code has expired or not found."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verification code expired or not found",
        )


class EmailDeliveryFailedException(HTTPException):
    """Raised when email provider cannot send messages."""

    def __init__(self):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to send verification email",
        )
