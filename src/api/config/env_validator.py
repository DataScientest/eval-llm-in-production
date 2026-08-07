"""Minimal environment checks for the student branch.

This module keeps startup usable without giving away the Exercise 1 solution.
It only emits warnings for obviously unsafe values instead of failing fast.
"""

import logging

from config.settings import JWT_SECRET_KEY

logger = logging.getLogger(__name__)

INSECURE_DEFAULTS = {
    "your-secret-key-change-in-production",
    "secret",
    "changeme",
    "",
}


def validate_environment_on_startup() -> None:
    """Warn about obviously unsafe configuration values."""
    if JWT_SECRET_KEY in INSECURE_DEFAULTS:
        logger.warning(
            "JWT_SECRET_KEY is using an insecure placeholder value. "
            "Exercise 1 expects students to replace this with proper validation."
        )
