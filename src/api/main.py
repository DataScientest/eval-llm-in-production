"""Main FastAPI application entry point."""

# Configure logging FIRST (before any other imports that might log)
from config.logging_config import setup_logging

setup_logging()

# Validate environment before anything else
from config.env_validator import validate_environment_on_startup

validate_environment_on_startup()

from config.app import create_app

# Create FastAPI application using factory pattern
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
