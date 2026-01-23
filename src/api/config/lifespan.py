"""Application lifespan management."""

from contextlib import asynccontextmanager
from fastapi import FastAPI

from services.mlflow_service import mlflow_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage MLflow experiment tracking and security setup."""
    print("Starting LLMOps Secure API...")
    
    # Setup MLflow experiment
    await mlflow_service.setup_experiment()
    print("MLflow experiment setup completed")
    
    # Cache is now handled directly in the LLM router with Qdrant
    print("Qdrant semantic cache initialized in LLM router")
    
    yield
    
    print("Shutting down LLMOps Secure API...")