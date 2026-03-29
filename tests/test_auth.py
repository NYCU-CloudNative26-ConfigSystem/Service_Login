"""Tests for authentication endpoints"""
import pytest
from app.schemas.user import UserRegisterRequest, UserLoginRequest
from app.utils.security import SecurityUtils


class TestAuthEndpoints:
    """Test cases for authentication endpoints"""
    
    def test_register_user_success(self, client):
        """Test successful user registration"""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "securepassword123",
                "full_name": "Test User",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert "id" in data
    
    def test_register_user_duplicate_email(self, client):
        """Test registration with duplicate email"""
        # First registration
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser1",
                "password": "securepassword123",
            },
        )
        
        # Second registration with same email
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser2",
                "password": "securepassword123",
            },
        )
        
        assert response.status_code == 400
    
    def test_login_success(self, client):
        """Test successful login"""
        # Register user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "securepassword123",
            },
        )
        
        # Login
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"
    
    def test_login_invalid_password(self, client):
        """Test login with invalid password"""
        # Register user first
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "securepassword123",
            },
        )
        
        # Login with wrong password
        response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "wrongpassword",
            },
        )
        
        assert response.status_code == 401
    
    def test_get_current_user(self, client):
        """Test getting current user information"""
        # Register user
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "securepassword123",
            },
        )
        
        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )
        
        token = login_response.json()["access_token"]
        
        # Get current user
        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"
    
    def test_get_current_user_without_token(self, client):
        """Test getting current user without authentication"""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 403
    
    def test_refresh_token(self, client):
        """Test token refresh"""
        # Register and login
        client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser",
                "password": "securepassword123",
            },
        )
        
        login_response = client.post(
            "/api/v1/auth/login",
            json={
                "email": "test@example.com",
                "password": "securepassword123",
            },
        )
        
        refresh_token = login_response.json()["refresh_token"]
        
        # Refresh token
        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        
        assert response.status_code == 200
        assert "access_token" in response.json()


class TestSecurityUtils:
    """Test cases for security utilities"""
    
    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "mySecurePassword123"
        
        hashed = SecurityUtils.hash_password(password)
        
        assert hashed != password
        assert SecurityUtils.verify_password(password, hashed)
        assert not SecurityUtils.verify_password("wrongpassword", hashed)
    
    def test_token_creation_and_decoding(self):
        """Test token creation and decoding"""
        user_id = 123
        
        token = SecurityUtils.create_access_token(user_id)
        assert token is not None
        
        payload = SecurityUtils.decode_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
