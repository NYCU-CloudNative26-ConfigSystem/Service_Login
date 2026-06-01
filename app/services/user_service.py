"""User service - business logic layer"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.user import User
from app.schemas.user import UserRegisterRequest, UserLoginRequest
from app.utils.security import SecurityUtils
from app.core.exceptions import (
    InvalidCredentialsException,
    UserNotFoundException,
    UserAlreadyExistsException,
)
from app.core.logging import logger
from datetime import datetime, timezone


class UserService:
    """Service class for user-related operations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def register_user(self, user_data: UserRegisterRequest) -> User:
        """Register a new user"""
        logger.info(f"Registering new user: {user_data.email}")
        
        # Check if user already exists
        existing_user = self.db.query(User).filter(
            (User.email == user_data.email) | (User.username == user_data.username)
        ).first()
        
        if existing_user:
            logger.warning(f"Registration failed: User {user_data.email} already exists")
            raise UserAlreadyExistsException()
        
        # Hash password
        hashed_password = SecurityUtils.hash_password(user_data.password)
        
        # Create new user
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
            full_name=user_data.full_name,
            company=user_data.company,
            role=user_data.role or "user",
        )
        
        try:
            self.db.add(new_user)
            self.db.commit()
            self.db.refresh(new_user)
            logger.info(f"User registered successfully: {new_user.id}")
            return new_user
        except IntegrityError:
            self.db.rollback()
            logger.error(f"Database error while registering user: {user_data.email}")
            raise UserAlreadyExistsException()
    
    def authenticate_user(self, login_data: UserLoginRequest) -> User:
        """Authenticate user with email and password"""
        logger.info(f"Authenticating user: {login_data.email}")
        
        # Find user by email
        user = self.db.query(User).filter(User.email == login_data.email).first()
        
        if not user:
            logger.warning(f"Authentication failed: User {login_data.email} not found")
            raise InvalidCredentialsException()
        
        # Verify password
        if not SecurityUtils.verify_password(login_data.password, user.hashed_password):
            logger.warning(f"Authentication failed: Invalid password for {login_data.email}")
            raise InvalidCredentialsException()
        
        # Check if user is active
        if not user.is_active:
            logger.warning(f"Authentication failed: User {login_data.email} is not active")
            raise InvalidCredentialsException()
        
        logger.info(f"User authenticated successfully: {user.id}")
        return user
    
    def get_user_by_id(self, user_id: int) -> User:
        """Get user by ID"""
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if not user:
            logger.warning(f"User not found: {user_id}")
            raise UserNotFoundException()
        
        return user
    
    def get_user_by_email(self, email: str) -> User:
        """Get user by email"""
        user = self.db.query(User).filter(User.email == email).first()
        
        if not user:
            logger.warning(f"User not found: {email}")
            raise UserNotFoundException()
        
        return user
    
    def update_last_login(self, user_id: int) -> bool:
        """Update user's last login timestamp"""
        try:
            user = self.get_user_by_id(user_id)
            user.last_login_at = datetime.now(timezone.utc)
            self.db.commit()
            logger.debug(f"Last login updated for user: {user_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error updating last login: {e}")
            return False
    
    def change_password(self, user_id: int, old_password: str, new_password: str) -> bool:
        """Change user password"""
        logger.info(f"Changing password for user: {user_id}")
        
        try:
            user = self.get_user_by_id(user_id)
            
            # Verify old password
            if not SecurityUtils.verify_password(old_password, user.hashed_password):
                logger.warning(f"Password change failed: Invalid old password for user {user_id}")
                raise InvalidCredentialsException()
            
            # Hash new password
            user.hashed_password = SecurityUtils.hash_password(new_password)
            self.db.commit()
            logger.info(f"Password changed successfully for user: {user_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error changing password: {e}")
            raise
    
    def deactivate_user(self, user_id: int) -> bool:
        """Deactivate a user account"""
        logger.info(f"Deactivating user: {user_id}")
        
        try:
            user = self.get_user_by_id(user_id)
            user.is_active = False
            self.db.commit()
            logger.info(f"User deactivated successfully: {user_id}")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error deactivating user: {e}")
            return False
