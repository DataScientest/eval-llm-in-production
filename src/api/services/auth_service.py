"""Authentication service for user management and JWT tokens."""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from jose import JWTError, jwt

# Fix bcrypt compatibility issue with passlib
try:
    import bcrypt
    if not hasattr(bcrypt, '__about__'):
        # Create a mock __about__ object for bcrypt 4.0+ compatibility
        class MockAbout:
            __version__ = getattr(bcrypt, '__version__', 'unknown')
        bcrypt.__about__ = MockAbout()
except ImportError:
    pass

from passlib.context import CryptContext
from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from config.settings import settings

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()

# Simple user database (in production, use a real database)
fake_users_db = {
    "admin": {
        "username": "admin",
        "hashed_password": pwd_context.hash("secret123"),  # password: secret123
        "role": "admin"
    },
    "user": {
        "username": "user", 
        "hashed_password": pwd_context.hash("password123"),  # password: password123
        "role": "user"
    }
}

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate a user with username and password."""
    user = fake_users_db.get(username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """Verify and decode JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = jwt.decode(credentials.credentials, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
        
        # Check if user still exists
        user = fake_users_db.get(username)
        if user is None:
            raise credentials_exception
            
        return {"username": username, "role": user["role"]}
    except JWTError:
        raise credentials_exception