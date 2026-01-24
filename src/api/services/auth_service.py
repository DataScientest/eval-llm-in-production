"""Authentication service for user management and JWT tokens."""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from jose import JWTError, jwt
import hashlib
import hmac

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.settings import settings

# Use HMAC instead of bcrypt for testing to avoid initialization issues
# In production, use bcrypt or a proper password hashing library
def simple_hash(password: str) -> str:
    """Simple hash for testing (NOT for production!)."""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_hash(password: str, hash_value: str) -> bool:
    """Verify password against hash."""
    return simple_hash(password) == hash_value

# Test users with simple hashes
_TEST_USERS = {
    "admin": {
        "username": "admin",
        "hashed_password": simple_hash("secret123"),
        "role": "admin"
    },
    "user": {
        "username": "user",
        "hashed_password": simple_hash("password123"),
        "role": "user"
    }
}

def get_fake_users_db():
    """Get user database."""
    return _TEST_USERS.copy()

_fake_users_db_cache = None

def get_fake_users_db_cached():
    global _fake_users_db_cache
    if _fake_users_db_cache is None:
        _fake_users_db_cache = get_fake_users_db()
    return _fake_users_db_cache

fake_users_db = property(lambda self: get_fake_users_db_cached())

security = HTTPBearer()

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return verify_hash(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return simple_hash(password)

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate a user with username and password."""
    user = get_fake_users_db_cached().get(username)
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
        
        user = get_fake_users_db_cached().get(username)
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
