"""Authentication models."""

from pydantic import BaseModel, Field
from typing import Dict


class UserLogin(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    password: str = Field(..., min_length=1, max_length=100)


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: Dict[str, str]


class UserInfo(BaseModel):
    username: str
    role: str