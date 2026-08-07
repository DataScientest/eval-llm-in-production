"""Basic logging setup for the student branch.

This file exists so the application can start and students can iterate on
Exercise 6. The implementation is intentionally minimal and not structured.
"""

import logging
import os


def setup_logging() -> None:
    """Configure a simple non-structured logger for local development."""
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,
    )

