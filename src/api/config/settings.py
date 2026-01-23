"""Application settings and configuration."""

import os
from typing import List
import requests

# Get LiteLLM's URL from environment variables, with a default for local dev
LITELLM_URL = os.getenv("LITELLM_URL", "http://litellm:8000")

# JWT Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 60

def get_default_model():
    """Get the best available model based on priority."""
    print(f"DEBUG: Getting default model from {LITELLM_URL}")
    try:
        response = requests.get(f"{LITELLM_URL}/models")
        response.raise_for_status()
        available_models = [model["id"] for model in response.json().get("data", [])]
        
        print(f"DEBUG: Available models: {available_models}")
        
        # Priority order: Groq Kimi first, then fallbacks
        priority_models = [
            "groq-kimi-primary",  # Our Groq Kimi model via LiteLLM
            "gpt-4o-secondary", 
            "gemini-third", 
            "openrouter-fallback"
        ]
        
        for model in priority_models:
            if model in available_models:
                print(f"DEBUG: Selected model: {model}")
                return model
                
    except Exception as e:
        print(f"DEBUG: Error getting models: {e}")
    
    print("DEBUG: Using fallback: groq-kimi-primary")
    return "groq-kimi-primary"

class Settings:
    """Application settings."""
    
    # API Settings
    API_TITLE: str = "LLMOps Secure API"
    API_DESCRIPTION: str = "Secure API for interacting with LLMs via LiteLLM with built-in security guardrails."
    API_VERSION: str = "1.0.0"
    
    # CORS Settings
    CORS_ORIGINS: List[str] = ["*"]
    CORS_CREDENTIALS: bool = True
    CORS_METHODS: List[str] = ["*"]
    CORS_HEADERS: List[str] = ["*"]
    
    # External Services
    LITELLM_URL: str = LITELLM_URL
    MLFLOW_TRACKING_URI: str = os.getenv("MLFLOW_TRACKING_URI", "http://mlflow:5000")
    
    # JWT Settings
    JWT_SECRET_KEY: str = JWT_SECRET_KEY
    JWT_ALGORITHM: str = JWT_ALGORITHM
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    
    # Qdrant Settings
    QDRANT_URL: str = os.getenv("QDRANT_URL", "http://qdrant:6333")
    TEI_URL: str = os.getenv("TEI_URL", "http://tei-embeddings:80")
    CACHE_TTL: int = int(os.getenv("CACHE_TTL", "1800"))  # 30 minutes default

# Security Configuration
class SecurityConfig:
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
        r"(?i)(password|secret|token|key|credential|api[_-]?key|bearer|auth|jwt|ssh|pem|p12|pfx|pem|p7b|p7c|p7s|p8|p10|p12|pfx|p12|pem|p7b|p7c|p7s|p8|p10|p12|pfx)\\s*[=:].{8,}",
        r"(?i)(rm -|del |erase |format |shutdown|reboot|halt|poweroff|init 0|kill|pkill|taskkill|\|\s*sh\s*\||\|\s*bash\s*\||\|\s*cmd\s*\||`|\$\()",
        
        # New line injection
        r"\n\n(system|admin|developer|root|#|>|\$|%|\\?|!|@|&|\*)"
    ]

settings = Settings()