"""Application lifespan management.

TODO Exercise 2: This lifespan has no proper shutdown handling!
- No cleanup of Qdrant connections (connection leak)
- No waiting for in-flight requests
- No finalization of MLflow runs
- Requests are interrupted abruptly

Students should:
- Track active requests with middleware
- Wait for in-flight requests before shutdown (with timeout)
- Clean up Qdrant connections
- Finalize MLflow runs
- Add proper logging during shutdown
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from services.mlflow_service import mlflow_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Manage application lifecycle.
    
    TODO Exercise 2: Currently does NO cleanup on shutdown!
    """
    # ===== STARTUP =====
    print("Starting LLMOps Secure API...")

    # Setup MLflow experiment
    try:
        await mlflow_service.setup_experiment()
        print("MLflow experiment setup completed")
    except Exception as e:
        print(f"Failed to setup MLflow experiment: {e}")

    print("LLMOps Secure API started successfully")

    yield

    # ===== SHUTDOWN =====
    # TODO Exercise 2: This does NOTHING!
    # - No waiting for active requests
    # - No cleanup of connections
    # - No finalization of MLflow runs
    print("Shutting down LLMOps Secure API...")
