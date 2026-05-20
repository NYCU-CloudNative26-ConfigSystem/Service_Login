"""User database model"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func
from sqlalchemy.exc import IntegrityError
from datetime import datetime
from app.database.connection import Base
from app.core.logging import logger


class User(Base):
    """User model for storing user identity and authentication data"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(255), nullable=True)
    company = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True, index=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', username='{self.username}')>"
    
    def update_last_login(self):
        """Update last login timestamp"""
        self.last_login_at = datetime.utcnow()
    
    @classmethod
    def create_from_dict(cls, **kwargs):
        """Factory method to create user from dictionary"""
        return cls(**kwargs)
