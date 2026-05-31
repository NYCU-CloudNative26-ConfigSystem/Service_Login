"""Application configuration management"""
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # App
    app_name: str = "Login Service"
    debug: bool = False
    log_level: str = "INFO"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_host_port: Optional[int] = None
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str
    
    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    max_password_length: int = 72
    
    # Session
    session_expire_seconds: int = 86400  # 24 hours
    max_login_attempts: int = 5
    lockout_duration_seconds: int = 900  # 15 minutes

    # Internal service-to-service auth
    internal_api_key: str = ""

    # CORS — restrict to this origin in production (leave empty to allow all during dev)
    app_base_url: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
