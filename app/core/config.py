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

    # Email verification and reset code TTL
    email_verification_code_ttl_seconds: int = 600
    password_reset_code_ttl_seconds: int = 600

    # Email provider configuration
    email_provider: str = "mock"  # mock | mailtrap | brevo | ses
    email_from: str = "no-reply@example.com"

    # Mailtrap (SMTP)
    mailtrap_host: str = "sandbox.smtp.mailtrap.io"
    mailtrap_port: int = 2525
    mailtrap_username: Optional[str] = None
    mailtrap_password: Optional[str] = None
    mailtrap_use_tls: bool = True

    # Brevo (SMTP API)
    brevo_api_key: Optional[str] = None

    # Amazon SES
    ses_region: str = "us-east-1"
    ses_access_key_id: Optional[str] = None
    ses_secret_access_key: Optional[str] = None
    
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
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
