"""Security utilities for password and token management"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import bcrypt
import jwt
from app.core.config import settings
from app.core.exceptions import PasswordTooLongException
from app.core.logging import logger


class SecurityUtils:
    """Utility class for security operations"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash password using bcrypt"""
        if len(password.encode("utf-8")) > settings.max_password_length:
            raise PasswordTooLongException()

        hashed_password = bcrypt.hashpw(
            password.encode("utf-8"),
            bcrypt.gensalt(rounds=12),
        )
        return hashed_password.decode("utf-8")
    
    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against hashed password"""
        try:
            return bcrypt.checkpw(
                plain_password.encode("utf-8"),
                hashed_password.encode("utf-8"),
            )
        except ValueError:
            return False
    
    @staticmethod
    def create_access_token(user_id: int, company: str = "", session_id: str = "", expires_delta: Optional[timedelta] = None) -> str:
        """Create JWT access token"""
        if expires_delta is None:
            expires_delta = timedelta(minutes=settings.access_token_expire_minutes)

        now = datetime.now(timezone.utc)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "access",
            "company": company,
            "sid": session_id,
        }
        
        try:
            encoded_jwt = jwt.encode(
                payload,
                settings.secret_key,
                algorithm=settings.algorithm,
            )
            logger.debug(f"Access token created for user {user_id}")
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating access token: {e}")
            raise
    
    @staticmethod
    def create_refresh_token(user_id: int, company: str = "") -> str:
        """Create JWT refresh token"""
        expires_delta = timedelta(days=settings.refresh_token_expire_days)
        now = datetime.now(timezone.utc)
        expire = now + expires_delta

        payload = {
            "sub": str(user_id),
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "type": "refresh",
            "company": company,
        }
        
        try:
            encoded_jwt = jwt.encode(
                payload,
                settings.secret_key,
                algorithm=settings.algorithm,
            )
            logger.debug(f"Refresh token created for user {user_id}")
            return encoded_jwt
        except Exception as e:
            logger.error(f"Error creating refresh token: {e}")
            raise
    
    @staticmethod
    def decode_token(token: str, token_type: str = "access") -> Optional[dict]:
        """Decode and validate JWT token"""
        try:
            payload = jwt.decode(
                token,
                settings.secret_key,
                algorithms=[settings.algorithm],
            )
            
            # Verify token type
            if payload.get("type") != token_type:
                logger.warning(f"Invalid token type: {payload.get('type')}")
                return None

            subject = payload.get("sub")
            if isinstance(subject, str) and subject.isdigit():
                payload["sub"] = int(subject)
            
            return payload
        except jwt.ExpiredSignatureError:
            logger.warning("Token has expired")
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid token: {e}")
            return None
        except Exception as e:
            logger.error(f"Error decoding token: {e}")
            return None