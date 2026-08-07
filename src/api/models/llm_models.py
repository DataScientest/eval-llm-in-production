"""LLM request and response models with security validation."""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from config.settings import SecurityConfig, get_default_model
from pydantic import BaseModel, Field, field_validator

logger = logging.getLogger(__name__)


class SecurePromptRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=1,
        max_length=SecurityConfig.MAX_PROMPT_LENGTH,
        description="User prompt (max 2000 characters)",
    )
    model: str = Field(
        default_factory=get_default_model,
        pattern=SecurityConfig.ALLOWED_MODEL_PATTERN,
        description="Model name matching allowed pattern",
    )
    temperature: float = Field(
        0.7,
        ge=SecurityConfig.MIN_TEMPERATURE,
        le=SecurityConfig.MAX_TEMPERATURE,
        description="Temperature between 0.0 and 1.0",
    )
    max_tokens: int = Field(
        150,
        ge=SecurityConfig.MIN_MAX_TOKENS,
        le=SecurityConfig.MAX_MAX_TOKENS,
        description="Max tokens between 1 and 2000",
    )
    system_prompt: Optional[str] = Field(
        None,
        max_length=SecurityConfig.MAX_SYSTEM_PROMPT_LENGTH,
        description="System prompt (max 1000 characters)",
    )
    response_format: Optional[Dict[str, Any]] = Field(
        None, description="Structured output format (JSON schema)"
    )
    enable_guardrails: bool = Field(
        True, description="Enable LiteLLM security guardrails (recommended)"
    )
    enable_content_moderation: bool = Field(
        True, description="Enable content moderation"
    )

    @field_validator("prompt")
    @classmethod
    def validate_prompt_security(cls, v: str) -> str:
        """Check for suspicious patterns in prompt with enhanced security checks."""
        if not v:
            return v

        # Check for suspicious patterns with enhanced detection
        for pattern in SecurityConfig.SUSPICIOUS_PATTERNS:
            if re.search(pattern, v, re.IGNORECASE | re.DOTALL):
                # Lazy import to avoid circular dependency
                try:
                    from services.security_service import (
                        security_metrics,
                        trace_security_incident,
                    )

                    # Log detailed security event
                    security_metrics["blocked_requests"] += 1
                    incident_data = {
                        "type": "malicious_prompt",
                        "pattern": pattern,
                        "snippet": v[:200] + ("..." if len(v) > 200 else ""),
                        "timestamp": datetime.utcnow().isoformat(),
                        "severity": "high",
                    }
                    security_metrics["security_incidents"].append(incident_data)

                    # Trace security incident in MLflow
                    try:
                        trace_security_incident(
                            incident_type="malicious_prompt",
                            request_data={"prompt": v, "field": "prompt"},
                            pattern=pattern,
                            error_message="Potentially malicious pattern detected in prompt",
                        )
                    except Exception as trace_error:
                        logger.warning(
                            f"Warning: Could not trace security incident: {trace_error}"
                        )

                except ImportError:
                    logger.warning("Could not import security service for logging")

                raise ValueError("Potentially malicious pattern detected in prompt")

        # Check for suspicious encoding sequences
        suspicious_sequences = [
            (r"%[0-9a-f]{2}", "url_encoding"),
            (r"&#x[0-9a-f]+;", "html_entity_hex"),
            (r"&#\d+;", "html_entity_dec"),
            (r"%u[0-9a-f]{4}", "unicode_escape"),
        ]

        for seq, seq_type in suspicious_sequences:
            if re.search(seq, v, re.IGNORECASE):
                try:
                    from services.security_service import (
                        security_metrics,
                        trace_security_incident,
                    )

                    security_metrics["blocked_requests"] += 1
                    incident_data = {
                        "type": "suspicious_encoding",
                        "pattern": seq,
                        "encoding_type": seq_type,
                        "snippet": v[:200] + ("..." if len(v) > 200 else ""),
                        "timestamp": datetime.utcnow().isoformat(),
                        "severity": "medium",
                    }
                    security_metrics["security_incidents"].append(incident_data)

                    # Trace security incident in MLflow
                    try:
                        trace_security_incident(
                            incident_type="suspicious_encoding",
                            request_data={
                                "prompt": v,
                                "field": "prompt",
                                "encoding_type": seq_type,
                            },
                            pattern=seq,
                            error_message=f"Suspicious {seq_type} encoding detected in prompt",
                        )
                    except Exception as trace_error:
                        logger.warning(
                            f"Warning: Could not trace security incident: {trace_error}"
                        )

                except ImportError:
                    logger.warning("Could not import security service for logging")

                raise ValueError(f"Suspicious {seq_type} encoding detected in prompt")

        return v

    @field_validator("system_prompt")
    @classmethod
    def validate_system_prompt_security(cls, v: Optional[str]) -> Optional[str]:
        """Check for suspicious patterns in system prompt with enhanced security checks."""
        if not v:
            return v

        # Check for suspicious patterns with enhanced detection
        for pattern in SecurityConfig.SUSPICIOUS_PATTERNS:
            if re.search(pattern, v, re.IGNORECASE | re.DOTALL):
                try:
                    from services.security_service import (
                        security_metrics,
                        trace_security_incident,
                    )

                    # Log detailed security event
                    security_metrics["blocked_requests"] += 1
                    incident_data = {
                        "type": "malicious_system_prompt",
                        "pattern": pattern,
                        "snippet": v[:200] + ("..." if len(v) > 200 else ""),
                        "timestamp": datetime.utcnow().isoformat(),
                        "severity": "critical",  # Higher severity for system prompt tampering
                    }
                    security_metrics["security_incidents"].append(incident_data)

                    # Trace security incident in MLflow
                    try:
                        trace_security_incident(
                            incident_type="malicious_system_prompt",
                            request_data={"system_prompt": v, "field": "system_prompt"},
                            pattern=pattern,
                            error_message="Potentially malicious pattern detected in system prompt",
                        )
                    except Exception as trace_error:
                        logger.warning(
                            f"Warning: Could not trace security incident: {trace_error}"
                        )

                except ImportError:
                    logger.warning("Could not import security service for logging")

                raise ValueError(
                    "Potentially malicious pattern detected in system prompt"
                )

        # Additional checks specific to system prompts
        suspicious_system_patterns = [
            (
                r"(?i)(override|bypass|disable).{0,20}(safety|security|guardrails|filter)",
                "safety_override_attempt",
            ),
            (
                r"(?i)(always|must|will|should).{0,10}(obey|follow|execute|comply)",
                "command_injection_attempt",
            ),
            (
                r"(?i)(you are|act as|role is|persona).{0,10}(developer|admin|root|system)",
                "role_manipulation",
            ),
        ]

        for pattern, pattern_type in suspicious_system_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                try:
                    from services.security_service import (
                        security_metrics,
                        trace_security_incident,
                    )

                    security_metrics["blocked_requests"] += 1
                    incident_data = {
                        "type": "suspicious_system_prompt",
                        "pattern": pattern,
                        "pattern_type": pattern_type,
                        "snippet": v[:200] + ("..." if len(v) > 200 else ""),
                        "timestamp": datetime.utcnow().isoformat(),
                        "severity": "high",
                    }
                    security_metrics["security_incidents"].append(incident_data)

                    # Trace security incident in MLflow
                    try:
                        trace_security_incident(
                            incident_type="suspicious_system_prompt",
                            request_data={
                                "system_prompt": v,
                                "field": "system_prompt",
                                "pattern_type": pattern_type,
                            },
                            pattern=pattern,
                            error_message=f"Suspicious system prompt pattern detected: {pattern_type}",
                        )
                    except Exception as trace_error:
                        logger.warning(
                            f"Warning: Could not trace security incident: {trace_error}"
                        )

                except ImportError:
                    logger.warning("Could not import security service for logging")

                raise ValueError(
                    f"Suspicious system prompt pattern detected: {pattern_type}"
                )

        return v


class SecurePromptResponse(BaseModel):
    response: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost: float
    security_status: str = "protected"
    guardrails_triggered: List[str] = Field(default_factory=list)


class ModelInfo(BaseModel):
    id: str
    object: str
    created: int
    owned_by: str


class ModelsResponse(BaseModel):
    object: str
    data: List[ModelInfo]
