"""Environment validation utilities for startup checks."""

import os
import sys
from typing import List, Tuple


def validate_required_env_vars() -> Tuple[bool, List[str]]:
    """
    Validate that all required environment variables are set.

    Returns:
        Tuple of (is_valid, list_of_errors)
    """
    errors = []

    # Required variables
    required_vars = [
        ("JWT_SECRET_KEY", "Required for JWT token signing"),
    ]

    # Optional but recommended variables
    recommended_vars = [
        ("OPENAI_API_KEY", "Required for OpenAI models"),
        ("GROQ_API_KEY", "Required for Groq models"),
    ]

    for var_name, description in required_vars:
        value = os.getenv(var_name)
        if not value:
            errors.append(f"Missing required: {var_name} - {description}")

    # Check for insecure defaults
    jwt_secret = os.getenv("JWT_SECRET_KEY", "")
    insecure_defaults = [
        "your-secret-key-change-in-production",
        "secret",
        "changeme",
        "your-secret-key",
    ]
    if jwt_secret.lower() in [d.lower() for d in insecure_defaults]:
        errors.append(
            "JWT_SECRET_KEY is set to an insecure default value. "
            "Please set a secure, random value of at least 32 characters."
        )
    elif jwt_secret and len(jwt_secret) < 32:
        errors.append(
            f"JWT_SECRET_KEY is too short ({len(jwt_secret)} chars). "
            "Please use at least 32 characters for security."
        )

    # Warnings for missing optional vars (don't fail, just log)
    warnings = []
    for var_name, description in recommended_vars:
        if not os.getenv(var_name):
            warnings.append(f"Missing optional: {var_name} - {description}")

    return len(errors) == 0, errors, warnings


def validate_environment_on_startup():
    """
    Validate environment on application startup.
    Exits the application if critical configuration is missing.
    """
    is_valid, errors, warnings = validate_required_env_vars()

    # Print warnings (non-fatal)
    for warning in warnings:
        print(f"WARNING: {warning}")

    # Print errors and exit if invalid
    if not is_valid:
        print("\n" + "=" * 60)
        print("CONFIGURATION ERROR - Application cannot start")
        print("=" * 60)
        for error in errors:
            print(f"  - {error}")
        print("=" * 60)
        print("\nPlease set the required environment variables and try again.")
        print("You can use a .env file or set them in your environment.")
        print("\nExample .env file:")
        print("  JWT_SECRET_KEY=your-secure-random-key-at-least-32-chars")
        print("=" * 60 + "\n")
        sys.exit(1)

    print("Environment validation passed")
