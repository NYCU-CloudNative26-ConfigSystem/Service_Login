"""Redis connection management"""
import token

import redis
import json
from typing import Optional, Any
from app.core.config import settings
from app.core.logging import logger


class RedisClient:
    """Singleton Redis client for session and cache management"""
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RedisClient, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            try:
                self._client = redis.from_url(settings.redis_url, decode_responses=True)
                self._client.ping()
                logger.info("Connected to Redis successfully")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")
                raise
    
    def set_session(self, session_id: str, user_id: int, ttl: int = None):
        """Store session in Redis"""
        if ttl is None:
            ttl = settings.session_expire_seconds
        
        try:
            key = f"session:{session_id}"
            self._client.setex(key, ttl, str(user_id))
            logger.debug(f"Session created: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error setting session: {e}")
            return False
    
    def get_session(self, session_id: str) -> Optional[int]:
        """Retrieve session from Redis"""
        try:
            key = f"session:{session_id}"
            user_id = self._client.get(key)
            return int(user_id) if user_id else None
        except Exception as e:
            logger.error(f"Error getting session: {e}")
            return None
    
    def delete_session(self, session_id: str):
        """Delete session from Redis"""
        try:
            key = f"session:{session_id}"
            self._client.delete(key)
            logger.debug(f"Session deleted: {session_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting session: {e}")
            return False
    
    def set_login_attempt(self, user_id: int, attempts: int):
        """Store login attempt counter"""
        try:
            key = f"login_attempts:{user_id}"
            self._client.setex(key, settings.lockout_duration_seconds, str(attempts))
            return True
        except Exception as e:
            logger.error(f"Error setting login attempt: {e}")
            return False
    
    def get_login_attempts(self, user_id: int) -> int:
        """Get login attempt counter"""
        try:
            key = f"login_attempts:{user_id}"
            attempts = self._client.get(key)
            return int(attempts) if attempts else 0
        except Exception as e:
            logger.error(f"Error getting login attempts: {e}")
            return 0
    
    def increment_login_attempts(self, user_id: int) -> int:
        """Increment login attempts and return new count"""
        try:
            key = f"login_attempts:{user_id}"
            attempts = self._client.incr(key)
            if attempts == 1:
                self._client.expire(key, settings.lockout_duration_seconds)
            return attempts
        except Exception as e:
            logger.error(f"Error incrementing login attempts: {e}")
            return 0
    
    def clear_login_attempts(self, user_id: int):
        """Clear login attempts for user"""
        try:
            key = f"login_attempts:{user_id}"
            self._client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Error clearing login attempts: {e}")
            return False
    
    def set_cache(self, key: str, value: Any, ttl: int = 3600):
        """Set generic cache key-value"""
        try:
            cache_key = f"cache:{key}"
            self._client.setex(cache_key, ttl, json.dumps(value))
            return True
        except Exception as e:
            logger.error(f"Error setting cache: {e}")
            return False
    
    def get_cache(self, key: str) -> Optional[Any]:
        """Get generic cache value"""
        try:
            cache_key = f"cache:{key}"
            value = self._client.get(cache_key)
            return json.loads(value) if value else None
        except Exception as e:
            logger.error(f"Error getting cache: {e}")
            return None
    
    def delete_cache(self, key: str):
        """Delete cache key"""
        try:
            cache_key = f"cache:{key}"
            self._client.delete(cache_key)
            return True
        except Exception as e:
            logger.error(f"Error deleting cache: {e}")
            return False
        
    def add_token_to_blacklist(self, access_token: str, refresh_token: str, ttl_access: int, ttl_refresh: int):
        """Add JWT token to blacklist with expiration"""
        try:
            key = f"blacklist:{refresh_token}"
            self._client.setex(key, ttl_refresh, "true")
            logger.debug(f"Token blacklisted: {refresh_token}")
            key = f"blacklist:{access_token}"
            self._client.setex(key, ttl_access, "true")
            logger.debug(f"Token blacklisted: {access_token}")
            return True
        except Exception as e:
            logger.error(f"Error blacklisting token: {e}")
            return False
        
    def is_token_blacklisted(self, token: str) -> bool:
        """Check if JWT token is blacklisted"""
        try:
            key = f"blacklist:{token}"
            return self._client.exists(key) == 1
        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")
            return False


# Singleton instance
redis_client = RedisClient()
