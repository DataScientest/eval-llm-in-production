"""Authentication router."""

from datetime import timedelta
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Any

from models.auth_models import UserLogin, Token, UserInfo
from services.auth_service import authenticate_user, create_access_token, verify_token
from config.settings import settings

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin):
    """Authenticate user and return JWT token."""
    user = authenticate_user(user_credentials.username, user_credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"], "role": user["role"]}, 
        expires_delta=access_token_expires
    )
    
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,  # Convert to seconds
        user={"username": user["username"], "role": user["role"]}
    )


@router.get("/me", response_model=UserInfo)
async def get_current_user(current_user: Dict[str, Any] = Depends(verify_token)):
    """Get current authenticated user information."""
    return UserInfo(username=current_user["username"], role=current_user["role"])


@router.get("/health")
async def auth_health():
    """Auth service health check."""
    return {"status": "healthy", "service": "auth"}