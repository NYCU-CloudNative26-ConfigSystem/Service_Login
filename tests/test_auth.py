"""Tests for authentication endpoints"""
import pytest
from app.schemas.user import UserRegisterRequest, UserLoginRequest
from app.utils.security import SecurityUtils
from app.core.exceptions import PasswordTooLongException
from app.core.config import settings
from app.database.redis import redis_client


def _register(client, email="test@example.com", username="testuser", company="TestCo"):
    return client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "username": username,
            "password": "securepassword123",
            "company": company,
        },
    )


def _login(client, email="test@example.com", password="securepassword123"):
    return client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )


class TestAuthEndpoints:
    """Test cases for authentication endpoints"""

    def test_register_user_success(self, client):
        """Test successful user registration"""
        response = _register(client)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "test@example.com"
        assert data["username"] == "testuser"
        assert data["company"] == "TestCo"
        assert "id" in data

    def test_register_user_duplicate_email(self, client):
        """Test registration with duplicate email"""
        _register(client, username="testuser1")
        response = _register(client, username="testuser2")
        assert response.status_code == 400

    def test_login_success(self, client):
        """Test successful login"""
        _register(client)
        response = _login(client)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "test@example.com"

    def test_login_invalid_password(self, client):
        """Test login with invalid password"""
        _register(client)
        response = _login(client, password="wrongpassword")
        assert response.status_code == 401

    def test_get_current_user(self, client):
        """Test getting current user information"""
        _register(client)
        token = _login(client).json()["access_token"]

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "test@example.com"

    def test_five_times_failed_login_attempts(self, client):
        """Test account lockout after 5 failed login attempts"""
        _register(client)

        for _ in range(settings.max_login_attempts):
            response = _login(client, password="OR 1=1 --")
            assert response.status_code == 401

        response = _login(client)
        assert response.status_code == 429

    def test_get_current_user_without_token(self, client):
        """Test getting current user without authentication"""
        response = client.get("/api/v1/auth/me")
        assert response.status_code == 403

    def test_refresh_token(self, client):
        """Test token refresh"""
        _register(client)
        refresh_token = _login(client).json()["refresh_token"]

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )

        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_logout(self, client):
        """Test user logout"""
        _register(client, email="logout_test@example.com", username="logout_test")
        login_data = _login(client, email="logout_test@example.com").json()
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

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

    def test_login_jwt_contains_company_and_sid(self, client):
        """Test that login issues a JWT with company, sid, and role claims"""
        _register(client)
        token = _login(client).json()["access_token"]
        payload = SecurityUtils.decode_token(token)

        assert payload["company"] == "TestCo"
        assert payload["sid"] != ""
        assert payload["role"] == "user"  # default role at registration

    def test_register_with_reviewer_role(self, client):
        """Test that registering with role=reviewer is stored and reflected in JWT"""
        client.post("/api/v1/auth/register", json={
            "email": "rev@example.com",
            "username": "rev_user",
            "password": "securepassword123",
            "company": "RevCo",
            "role": "reviewer",
        })
        token = client.post("/api/v1/auth/login", json={
            "email": "rev@example.com",
            "password": "securepassword123",
        }).json()["access_token"]
        payload = SecurityUtils.decode_token(token)
        assert payload["role"] == "reviewer"

    def test_session_lifecycle(self, client):
        """Test that session is created on login and destroyed on logout"""
        _register(client)
        login_data = _login(client).json()
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

        sid = SecurityUtils.decode_token(access_token)["sid"]
        assert redis_client._client.exists(f"session:{sid}")

        client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )

        assert not redis_client._client.exists(f"session:{sid}")

    def test_refresh_token_contains_company_and_sid(self, client):
        """Test that a refreshed access token still carries company and sid"""
        _register(client)
        refresh_token = _login(client).json()["refresh_token"]

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code == 200

        payload = SecurityUtils.decode_token(response.json()["access_token"])
        assert payload["company"] == "TestCo"
        assert payload["sid"] != ""


class TestSecurityUtils:
    """Test cases for security utilities"""

    def test_password_hashing(self):
        """Test password hashing and verification"""
        password = "mySecurePassword123"
        hashed = SecurityUtils.hash_password(password)

        assert hashed != password
        assert SecurityUtils.verify_password(password, hashed)
        assert not SecurityUtils.verify_password("wrongpassword", hashed)

    def test_password_hashing_rejects_long_utf8_password(self):
        """Test hashing rejects passwords that exceed bcrypt's 72-byte limit"""
        password = "密" * 25

        assert len(password) <= 72
        assert len(password.encode("utf-8")) > 72

        with pytest.raises(PasswordTooLongException):
            SecurityUtils.hash_password(password)

    def test_token_creation_and_decoding(self):
        """Test token creation and decoding"""
        user_id = 123
        token = SecurityUtils.create_access_token(user_id, company="TestCo", session_id="abc-session")
        assert token is not None

        payload = SecurityUtils.decode_token(token)
        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["company"] == "TestCo"
        assert payload["sid"] == "abc-session"


class TestTokenRevocation:
    """Ensure tokens cannot be reused after logout."""

    def test_refresh_token_revoked_after_logout(self, client):
        """Refresh token used after logout must be rejected."""
        _register(client, email="revoke@example.com", username="revoke_user")
        login_data = _login(client, email="revoke@example.com").json()
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

        client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )

        response = client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert response.status_code in (401, 400)

    def test_access_token_rejected_after_logout(self, client):
        """Access token must be invalid immediately after logout."""
        _register(client, email="revoke2@example.com", username="revoke_user2")
        login_data = _login(client, email="revoke2@example.com").json()
        access_token = login_data["access_token"]
        refresh_token = login_data["refresh_token"]

        client.post(
            "/api/v1/auth/logout",
            headers={"Authorization": f"Bearer {access_token}"},
            json={"refresh_token": refresh_token},
        )

        response = client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert response.status_code == 401

    def test_admin_role_stored_in_jwt(self, client):
        """Registering with role=admin should reflect in JWT claims."""
        client.post("/api/v1/auth/register", json={
            "email": "admin@example.com",
            "username": "admin_user",
            "password": "securepassword123",
            "company": "AdminCo",
            "role": "admin",
        })
        token = client.post("/api/v1/auth/login", json={
            "email": "admin@example.com",
            "password": "securepassword123",
        }).json()["access_token"]
        payload = SecurityUtils.decode_token(token)
        assert payload["role"] == "admin"
        assert payload["company"] == "AdminCo"
