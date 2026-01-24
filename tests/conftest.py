"""Shared pytest fixtures and configuration for all tests."""

import os
import sys
import pytest

# Add src/api to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "api"))

# Set test environment
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-for-testing-only-32chars!")
os.environ.setdefault("AUTH_ADMIN_PASSWORD", "secret123")
os.environ.setdefault("AUTH_USER_PASSWORD", "password123")


@pytest.fixture
def test_settings():
    """Provide test settings that can be overridden."""
    from config.settings import Settings, set_settings, reset_settings
    
    # Create test settings
    test_config = Settings(
        JWT_SECRET_KEY="test-secret-key-for-testing-only-32chars!",
        LITELLM_URL="http://localhost:8001",
        MLFLOW_TRACKING_URI="http://localhost:5001",
        QDRANT_URL="http://localhost:6333",
    )
    set_settings(test_config)
    yield test_config
    reset_settings()


@pytest.fixture
def auth_headers():
    """Provide valid auth headers for API tests."""
    from services.auth_service import create_access_token
    
    token = create_access_token({"sub": "admin", "role": "admin"})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_user():
    """Provide admin user data."""
    return {"username": "admin", "role": "admin"}


@pytest.fixture
def regular_user():
    """Provide regular user data."""
    return {"username": "user", "role": "user"}
