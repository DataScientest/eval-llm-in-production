"""Main FastAPI application entry point."""

from config.app import create_app

# Create FastAPI application using factory pattern
app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
