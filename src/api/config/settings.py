"""Application settings and configuration.

TODO Exercise 1: This configuration has security issues!
- JWT_SECRET_KEY has an insecure default value
- CORS_ORIGINS allows all origins with ["*"]
- No validation of environment variables at startup

Students should:
- Migrate to pydantic.BaseSettings with proper validation
- Remove insecure defaults and require JWT_SECRET_KEY via environment
- Restrict CORS to specific origins
- Add fail-fast validation for required secrets
"""

import os
from typing import List


# INSECURE: Hardcoded secret key visible in source code!
JWT_SECRET_KEY = "your-secret-key-change-in-production"
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60

# INSECURE: Allows ALL origins - vulnerable to CSRF attacks!
CORS_ORIGINS = ["*"]
CORS_CREDENTIALS = True
CORS_METHODS = ["GET", "POST", "PUT", "DELETE"]
CORS_HEADERS = ["*"]

# API Settings
API_TITLE = "LLMOps Secure API"
API_DESCRIPTION = "Secure API for interacting with LLMs via LiteLLM with built-in security guardrails."
API_VERSION = "1.0.0"

# External Services
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:8000")
MLFLOW_TRACKING_URI = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")

# Qdrant Settings
QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
TEI_URL = os.getenv("TEI_URL", "http://tei-embeddings:80")
CACHE_TTL = 1800


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


def get_default_model(litellm_url: str) -> str:
    """Get the best available model based on priority."""
    import requests
    try:
        response = requests.get(f"{litellm_url}/models", timeout=5)
        response.raise_for_status()
        available_models = [model["id"] for model in response.json().get("data", [])]

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


# Simple settings object for compatibility
class _Settings:
    """Simple settings wrapper - TODO Exercise 1: Replace with pydantic BaseSettings."""
    JWT_SECRET_KEY = JWT_SECRET_KEY
    JWT_ALGORITHM = JWT_ALGORITHM
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    CORS_ORIGINS = CORS_ORIGINS
    CORS_CREDENTIALS = CORS_CREDENTIALS
    CORS_METHODS = CORS_METHODS
    CORS_HEADERS = CORS_HEADERS
    API_TITLE = API_TITLE
    API_DESCRIPTION = API_DESCRIPTION
    API_VERSION = API_VERSION
    LITELLM_URL = LITELLM_URL
    MLFLOW_TRACKING_URI = MLFLOW_TRACKING_URI
    QDRANT_URL = QDRANT_URL
    TEI_URL = TEI_URL
    CACHE_TTL = CACHE_TTL


settings = _Settings()
