"""Authentication service - handles session and token management"""
from app.database.redis import redis_client
from app.utils.security import SecurityUtils
from app.core.exceptions import InvalidTokenException, AccountLockedException
from app.core.config import settings
from app.core.logging import logger
import uuid


class AuthService:
    """Service class for authentication operations"""
    
    @staticmethod
    def create_session(user_id: int) -> str:
        """Create a session for authenticated user"""
        logger.info(f"Creating session for user: {user_id}")
        
        session_id = str(uuid.uuid4())
        success = redis_client.set_session(session_id, user_id)
        
        if not success:
            logger.error(f"Failed to create session for user: {user_id}")
            raise Exception("Failed to create session")
        
        return session_id
    
    @staticmethod
    def validate_session(session_id: str) -> int:
        """Validate session and return user_id"""
        user_id = redis_client.get_session(session_id)
        
        if not user_id:
            logger.warning(f"Invalid or expired session: {session_id}")
            raise InvalidTokenException()
        
        logger.debug(f"Session validated for user: {user_id}")
        return user_id
    
    @staticmethod
    def destroy_session(session_id: str) -> bool:
        """Destroy a session (logout)"""
        logger.info(f"Destroying session: {session_id}")
        return redis_client.delete_session(session_id)
    
    @staticmethod
    def record_failed_login(user_id: int) -> None:
        """Record failed login attempt"""
        logger.warning(f"Failed login attempt for user: {user_id}")
        
        attempts = redis_client.increment_login_attempts(user_id)
        logger.info(f"Login attempts for user {user_id}: {attempts}/{settings.max_login_attempts}")
        
        if attempts >= settings.max_login_attempts:
            logger.warning(f"Account locked: User {user_id} exceeded max login attempts")
            raise AccountLockedException()
    
    @staticmethod
    def record_successful_login(user_id: int) -> None:
        """Clear failed login attempts on successful login"""
        logger.info(f"Successful login for user: {user_id}")
        redis_client.clear_login_attempts(user_id)
    
    @staticmethod
    def check_account_locked(user_id: int) -> None:
        """Check if account is locked"""
        attempts = redis_client.get_login_attempts(user_id)
        
        if attempts >= settings.max_login_attempts:
            logger.warning(f"Account locked: User {user_id}")
            raise AccountLockedException()
    
    @staticmethod
    def create_tokens(user_id: int) -> dict:
        """Create both access and refresh tokens"""
        logger.info(f"Creating tokens for user: {user_id}")
        
        access_token = SecurityUtils.create_access_token(user_id)
        refresh_token = SecurityUtils.create_refresh_token(user_id)
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }
    
    @staticmethod
    def refresh_access_token(refresh_token: str) -> str:
        """Create new access token from refresh token"""
        logger.info("Refreshing access token")
        
        payload = SecurityUtils.decode_token(refresh_token, token_type="refresh")
        
        if not payload:
            logger.warning("Invalid refresh token")
            raise InvalidTokenException()
        
        user_id = payload.get("sub")
        if not user_id:
            logger.warning("Invalid refresh token payload")
            raise InvalidTokenException()
        
        new_access_token = SecurityUtils.create_access_token(user_id)
        logger.info(f"Access token refreshed for user: {user_id}")
        
        return new_access_token

    @staticmethod
    def set_blacklist_token(refresh_token: str, access_token: str) -> bool:
        """Blacklist a token (e.g. on logout)"""
        logger.info("Blacklisting token")
        try:
            redis_client.add_token_to_blacklist(
                access_token=access_token, 
                refresh_token=refresh_token, 
                ttl_access=settings.access_token_expire_minutes * 60, 
                ttl_refresh=settings.refresh_token_expire_days * 24 * 3600
            )
            logger.debug("Token blacklisted successfully")
            return True
        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")
            return False
    
    @staticmethod
    def is_token_blacklisted(token: str) -> bool:
        """Check if token is blacklisted"""
        return redis_client.is_token_blacklisted(token)