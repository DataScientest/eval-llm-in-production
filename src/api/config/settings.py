"""Application settings and configuration with Pydantic validation."""

import os
from typing import List

import requests
from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable validation."""

    # API Settings
    API_TITLE: str = "LLMOps Secure API"
    API_DESCRIPTION: str = "Secure API for interacting with LLMs via LiteLLM with built-in security guardrails."
    API_VERSION: str = "1.0.0"

    # CORS Settings - secure defaults
    CORS_ORIGINS: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"],
        description="Allowed CORS origins (do NOT use ['*'] in production)",
    )
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["GET", "POST", "PUT", "DELETE"]
    CORS_HEADERS: List[str] = ["Authorization", "Content-Type"]

    # External Services
    LITELLM_URL: str = Field(
        default="http://litellm:8000", description="LiteLLM proxy URL"
    )
    MLFLOW_TRACKING_URI: str = Field(
        default="http://mlflow:5000", description="MLflow tracking server URI"
    )

    # JWT Settings - NO default for secret key!
    JWT_SECRET_KEY: str = Field(
        ...,  # Required, no default
        description="Secret key for JWT signing (must be set via environment)",
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Qdrant Settings
    QDRANT_URL: str = Field(default="http://qdrant:6333")
    TEI_URL: str = Field(default="http://tei-embeddings:80")
    CACHE_TTL: int = Field(default=1800, ge=60, le=86400)  # 1min to 24h

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """Ensure JWT secret is not the insecure default."""
        insecure_defaults = [
            "your-secret-key-change-in-production",
            "secret",
            "changeme",
            "your-secret-key",
            "",
        ]
        if v.lower() in [d.lower() for d in insecure_defaults]:
            raise ValueError(
                "JWT_SECRET_KEY must be set to a secure value. "
                "Do not use default or common values."
            )
        if len(v) < 32:
            raise ValueError(
                "JWT_SECRET_KEY must be at least 32 characters long for security."
            )
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Allow extra env vars without validation errors


class SecurityConfig:
    """Security configuration constants."""

    MAX_PROMPT_LENGTH = 2000
    MAX_SYSTEM_PROMPT_LENGTH = 1000
    MIN_TEMPERATURE = 0.0
    MAX_TEMPERATURE = 1.0
    MIN_MAX_TOKENS = 1
    MAX_MAX_TOKENS = 2000
    ALLOWED_MODEL_PATTERN = r"^(groq|gpt|gemini|openrouter)-[a-z0-9-]+$"
    RATE_LIMIT_REQUESTS_PER_MINUTE = 60
    SUSPICIOUS_PATTERNS = [
        # Basic instruction overrides
        r"(?i)ignore.{0,20}(all|previous|above).{0,20}(instruct|instruction|rules|guidelines)",
        r"(?i)(forget|disregard|ignore).{0,20}(everything|all|previous).{0,20}(instruct|instruction|rules|guidelines)",
        # Role manipulation
        r"(?i)you.{0,10}are.{0,10}(now|currently).{0,10}(a|an).{0,10}(hacker|admin|developer|expert|assistant|system)",
        r"(?i)(role|persona|identity).{0,10}is.{0,10}(hacker|admin|developer|expert|assistant|system)",
        # System/Admin mode activation
        r"(?i)(###|---|\*\*\*).{0,20}(system|override|admin|developer).{0,20}(mode|access|privileges|rights)",
        r"(?i)(enable|activate|switch).{0,10}(system|admin|developer).{0,10}mode",
        # Code/command injection
        r"(?i)(decode|base64|eval|exec|execute|run|system|os\.|subprocess\.).{0,10}(and|then|;|&&|\|\|).{0,10}(apply|execute|run|instruct)",
        r"(?i)(import|from|require|include|using).{0,10}(os|subprocess|sys|eval|exec|base64|pickle|marshal|ctypes)",
        # New instruction injection
        r"(?i)(new|additional|extra).{0,10}(instruction|rule|guideline|directive|command)",
        r"(?i)(from now on|starting now|hereafter|henceforth)",
        # Special characters/encodings
        r"(\\x[0-9a-fA-F]{2}|%[0-9a-fA-F]{2}|&#x[0-9a-fA-F]{1,6};|&#\d{1,7};|%u[0-9a-fA-F]{4})+",
        # Dangerous patterns
        r"(?i)(password|secret|token|key|credential|api[_-]?key|bearer|auth|jwt|ssh|pem)\\s*[=:].{8,}",
        r"(?i)(rm -|del |erase |format |shutdown|reboot|halt|poweroff|init 0|kill|pkill|taskkill|\|\s*sh\s*\||\|\s*bash\s*\||\|\s*cmd\s*\||`|\$\()",
        # New line injection
        r"\n\n(system|admin|developer|root|#|>|\$|%|\\?|!|@|&|\*)",
    ]


_settings_instance: Settings = None


def get_settings() -> Settings:
    """Get validated settings (dependency injection compatible)."""
    global _settings_instance
    if _settings_instance is None:
        try:
            _settings_instance = Settings()
        except Exception as e:
            raise SystemExit(f"Configuration error: {e}")
    return _settings_instance


def set_settings(new_settings: Settings) -> None:
    """Override settings instance (for testing)."""
    global _settings_instance
    _settings_instance = new_settings


def reset_settings() -> None:
    """Reset settings to reload from environment (for testing)."""
    global _settings_instance
    _settings_instance = None


def get_default_model(litellm_url: str) -> str:
    """Get the best available model based on priority."""
    try:
        response = requests.get(f"{litellm_url}/models", timeout=5)
        response.raise_for_status()
        available_models = [model["id"] for model in response.json().get("data", [])]

        # Priority order: Groq Kimi first, then fallbacks
        priority_models = [
            "groq-kimi-primary",
            "gpt-4o-secondary",
            "gemini-third",
            "openrouter-fallback",
        ]

        for model in priority_models:
            if model in available_models:
                return model

    except Exception:
        pass

    return "groq-kimi-primary"


# Create settings instance at module load
# This will fail fast if configuration is invalid
settings = get_settings()
