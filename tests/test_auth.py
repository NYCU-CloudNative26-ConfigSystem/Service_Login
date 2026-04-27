"""Tests for authentication endpoints."""
import pytest

from app.core.config import settings
from app.core.exceptions import PasswordTooLongException
from app.database.redis import redis_client
from app.models.audit_log import AuditLog
from app.utils.security import SecurityUtils


class TestAuthEndpoints:
    """Test cases for authentication endpoints."""

    @staticmethod
    def _register_user(client, email: str = "test@example.com", username: str = "testuser"):
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": "securepassword123",
                "full_name": "Test User",
            },
        )
        assert response.status_code == 201
        return response

    @staticmethod
    def _verify_user_email(client, email: str = "test@example.com"):
        code = redis_client.get_email_code("register", email)
        assert code is not None
        response = client.post(
            "/api/v1/auth/verify-email/confirm",
            json={"email": email, "code": code},
        )
        assert response.status_code == 200

    def test_register_user_success(self, client):
        """Test successful user registration and verification code issuance."""
        response = self._register_user(client)

        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert data["is_verified"] is False
        assert "id" in data

        code = redis_client.get_email_code("register", "test@example.com")
        assert code is not None

    def test_register_user_duplicate_email(self, client):
        """Test registration with duplicate email."""
        self._register_user(client, email="test@example.com", username="testuser1")

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "test@example.com",
                "username": "testuser2",
                "password": "securepassword123",
            },
        )

        assert response.status_code == 400

    def test_login_blocked_before_email_verification(self, client):
        """Login should be blocked when email is not verified."""
        self._register_user(client)

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "securepassword123"},
        )

        assert response.status_code == 403

    def test_email_verification_then_login_success(self, client):
        """User can login after confirming email verification code."""
        self._register_user(client)
        self._verify_user_email(client)

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "securepassword123"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"
        assert data["user"]["is_verified"] is True

    def test_login_invalid_password(self, client):
        """Test login with invalid password."""
        self._register_user(client)
        self._verify_user_email(client)

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "wrongpassword"},
        )

        assert response.status_code == 401

    def test_get_current_user(self, client):
        """Test getting current user information."""
        self._register_user(client)
        self._verify_user_email(client)

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "securepassword123"},
        )
        token = login_response.json()["access_token"]

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        assert response.json()["email"] == "test@example.com"

    def test_five_times_failed_login_attempts(self, client):
        """Test account lockout after configured failed login attempts."""
        self._register_user(client)
        self._verify_user_email(client)

        wrong_login_json = {
            "email": "test@example.com",
            "password": "OR 1=1 --",
        }

        for _ in range(settings.max_login_attempts-1):
            response = client.post("/api/v1/auth/login", json=wrong_login_json)
            assert response.status_code == 401

        response = client.post("/api/v1/auth/login", json=wrong_login_json)
        assert response.status_code == 429

        response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "securepassword123"},
        )
        assert response.status_code == 429

    def test_get_current_user_without_token(self, client):
        """Test getting current user without authentication."""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403

    def test_refresh_token(self, client):
        """Test token refresh."""
        self._register_user(client)
        self._verify_user_email(client)

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "test@example.com", "password": "securepassword123"},
        )
        refresh_token = login_response.json()["refresh_token"]

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_logout(self, client):
        """Test user logout."""
        self._register_user(client, email="logout_test@example.com", username="logout_test")
        self._verify_user_email(client, email="logout_test@example.com")

        login_response = client.post(
            "/api/v1/auth/login",
            json={"email": "logout_test@example.com", "password": "securepassword123"},
        )
        access_token = login_response.json()["access_token"]
        refresh_token = login_response.json()["refresh_token"]

        response = client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 401

    def test_forgot_password_reset_flow(self, client):
        """Forgot-password flow should reset password with Redis-stored email code."""
        self._register_user(client, email="reset@example.com", username="reset_user")
        self._verify_user_email(client, email="reset@example.com")

        response = client.post(
            "/api/v1/auth/forgot-password/request",
            json={"email": "reset@example.com"},
        )
        assert response.status_code == 200

        reset_code = redis_client.get_email_code("password_reset", "reset@example.com")
        assert reset_code is not None

        reset_response = client.post(
            "/api/v1/auth/forgot-password/reset",
            json={
                "email": "reset@example.com",
                "code": reset_code,
                "new_password": "newsecurepassword123",
            },
        )
        assert reset_response.status_code == 200

        old_login = client.post(
            "/api/v1/auth/login",
            json={"email": "reset@example.com", "password": "securepassword123"},
        )
        assert old_login.status_code == 401

        new_login = client.post(
            "/api/v1/auth/login",
            json={"email": "reset@example.com", "password": "newsecurepassword123"},
        )
        assert new_login.status_code == 200

    def test_audit_logs_created_for_security_events(self, client, db_session):
        """Register and verification should write audit rows to PostgreSQL."""
        self._register_user(client, email="audit@example.com", username="audit_user")
        self._verify_user_email(client, email="audit@example.com")

        actions = {
            row.action
            for row in db_session.query(AuditLog)
            .filter(AuditLog.email == "audit@example.com")
            .all()
        }

        assert "REGISTER" in actions
        assert "EMAIL_VERIFIED" in actions


class TestSecurityUtils:
    """Test cases for security utilities."""

    def test_password_hashing(self):
        """Test password hashing and verification."""
        password = "mySecurePassword123"

        hashed = SecurityUtils.hash_password(password)

        assert hashed != password
        assert SecurityUtils.verify_password(password, hashed)
        assert not SecurityUtils.verify_password("wrongpassword", hashed)

    def test_password_hashing_rejects_long_utf8_password(self):
        """Test hashing rejects passwords that exceed bcrypt's 72-byte limit."""
        password = "密" * 25

        assert len(password) <= 72
        assert len(password.encode("utf-8")) > 72

        with pytest.raises(PasswordTooLongException):
            SecurityUtils.hash_password(password)

    def test_token_creation_and_decoding(self):
        """Test token creation and decoding."""
        user_id = 123

        token = SecurityUtils.create_access_token(user_id)
        assert token is not None

        payload = SecurityUtils.decode_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
