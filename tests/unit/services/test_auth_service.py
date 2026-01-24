"""Unit tests for auth_service."""

import os
import pytest
from unittest.mock import patch
from datetime import timedelta


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password_returns_bcrypt_hash(self):
        """Test that hash_password returns a valid bcrypt hash."""
        from services.auth_service import hash_password
        
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert hashed.startswith("$2b$")
        assert len(hashed) == 60

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        from services.auth_service import hash_password, verify_password
        
        password = "correct_password"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        from services.auth_service import hash_password, verify_password
        
        password = "correct_password"
        hashed = hash_password(password)
        
        assert verify_password("wrong_password", hashed) is False

    def test_verify_password_invalid_hash(self):
        """Test password verification with invalid hash returns False."""
        from services.auth_service import verify_password
        
        assert verify_password("password", "invalid_hash") is False


class TestDevModeCheck:
    """Tests for development mode detection."""

    def test_is_dev_mode_development(self):
        """Test dev mode detection for 'development' environment."""
        from services.auth_service import _is_dev_mode
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            assert _is_dev_mode() is True

    def test_is_dev_mode_production(self):
        """Test dev mode detection for 'production' environment."""
        from services.auth_service import _is_dev_mode
        
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
            assert _is_dev_mode() is False

    def test_is_dev_mode_test(self):
        """Test dev mode detection for 'test' environment."""
        from services.auth_service import _is_dev_mode
        
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            assert _is_dev_mode() is True

    def test_is_dev_mode_default(self):
        """Test dev mode defaults to True when ENVIRONMENT not set."""
        from services.auth_service import _is_dev_mode
        
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("ENVIRONMENT", None)
            assert _is_dev_mode() is True


class TestUserDatabase:
    """Tests for user database loading."""

    def test_get_users_db_returns_admin_and_user(self):
        """Test that user database contains admin and user."""
        from services.auth_service import get_users_db, _users_db_cache
        
        # Reset cache
        import services.auth_service as auth_module
        auth_module._users_db_cache = None
        
        users = get_users_db()
        
        assert "admin" in users
        assert "user" in users
        assert users["admin"]["role"] == "admin"
        assert users["user"]["role"] == "user"

    def test_get_users_db_caches_result(self):
        """Test that user database is cached."""
        import services.auth_service as auth_module
        auth_module._users_db_cache = None
        
        users1 = auth_module.get_users_db()
        users2 = auth_module.get_users_db()
        
        assert users1 is users2


class TestAuthentication:
    """Tests for user authentication."""

    def test_authenticate_user_valid_credentials(self):
        """Test authentication with valid credentials."""
        import services.auth_service as auth_module
        auth_module._users_db_cache = None
        
        with patch.dict(os.environ, {
            "ENVIRONMENT": "test",
            "AUTH_ADMIN_PASSWORD": "secret123"
        }):
            user = auth_module.authenticate_user("admin", "secret123")
            
            assert user is not None
            assert user["username"] == "admin"
            assert user["role"] == "admin"

    def test_authenticate_user_invalid_password(self):
        """Test authentication with invalid password."""
        import services.auth_service as auth_module
        auth_module._users_db_cache = None
        
        with patch.dict(os.environ, {"ENVIRONMENT": "test"}):
            user = auth_module.authenticate_user("admin", "wrong_password")
            
            assert user is None

    def test_authenticate_user_unknown_user(self):
        """Test authentication with unknown username."""
        import services.auth_service as auth_module
        
        user = auth_module.authenticate_user("unknown_user", "password")
        
        assert user is None


class TestJWTTokens:
    """Tests for JWT token creation and verification."""

    def test_create_access_token(self):
        """Test JWT token creation."""
        from services.auth_service import create_access_token
        
        token = create_access_token({"sub": "admin", "role": "admin"})
        
        assert token is not None
        assert len(token) > 0
        assert token.count(".") == 2  # JWT has 3 parts

    def test_create_access_token_with_expiry(self):
        """Test JWT token creation with custom expiry."""
        from services.auth_service import create_access_token
        
        token = create_access_token(
            {"sub": "admin"},
            expires_delta=timedelta(minutes=30)
        )
        
        assert token is not None
