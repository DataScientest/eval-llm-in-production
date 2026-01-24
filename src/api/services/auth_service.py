"""Authentication service for user management and JWT tokens."""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from jose import JWTError, jwt
import bcrypt

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.settings import settings


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())
    except Exception:
        return False


def _is_dev_mode() -> bool:
    """Check if running in development mode."""
    env = os.getenv("ENVIRONMENT", "development").lower()
    return env in ("development", "dev", "local", "test")


def _get_users_from_env() -> Dict[str, Dict]:
    """
    Load users from environment variables.
    
    Production mode (ENVIRONMENT != dev/development/local/test):
      - Requires AUTH_ADMIN_HASH and AUTH_USER_HASH (pre-computed bcrypt hashes)
      - Fails fast if missing
    
    Development mode:
      - Falls back to AUTH_ADMIN_PASSWORD/AUTH_USER_PASSWORD
      - Uses default passwords if not set (secret123, password123)
    """
    admin_hash = os.getenv("AUTH_ADMIN_HASH")
    user_hash = os.getenv("AUTH_USER_HASH")
    
    if not _is_dev_mode():
        # Production: require pre-computed hashes
        if not admin_hash or not user_hash:
            raise RuntimeError(
                "Production mode requires AUTH_ADMIN_HASH and AUTH_USER_HASH. "
                "Set ENVIRONMENT=development for dev mode with password fallbacks."
            )
    else:
        # Development: allow password fallbacks
        if not admin_hash:
            admin_password = os.getenv("AUTH_ADMIN_PASSWORD", "secret123")
            admin_hash = hash_password(admin_password)
        if not user_hash:
            user_password = os.getenv("AUTH_USER_PASSWORD", "password123")
            user_hash = hash_password(user_password)
    
    return {
        "admin": {
            "username": "admin",
            "hashed_password": admin_hash,
            "role": "admin"
        },
        "user": {
            "username": "user", 
            "hashed_password": user_hash,
            "role": "user"
        }
    }


_users_db_cache: Optional[Dict] = None


def get_users_db() -> Dict[str, Dict]:
    """Get user database (cached)."""
    global _users_db_cache
    if _users_db_cache is None:
        _users_db_cache = _get_users_from_env()
    return _users_db_cache

security = HTTPBearer()


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate a user with username and password."""
    user = get_users_db().get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode, 
        settings.JWT_SECRET_KEY, 
        algorithm="HS256"
    )
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify JWT token and return user data."""
    token = credentials.credentials
    try:
        payload = jwt.decode(
            token, 
            settings.JWT_SECRET_KEY, 
            algorithms=["HS256"]
        )
        username: str = payload.get("sub")
        if username is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
        
        user = get_users_db().get(username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        return user
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials"
        )
