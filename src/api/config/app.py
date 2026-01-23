"""Application factory for creating FastAPI instances."""

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from middleware.metrics import metrics_middleware
from middleware.request_id import request_id_middleware
from middleware.request_limits import request_limits_middleware
from middleware.security import security_middleware
from middleware.shutdown import shutdown_middleware
from routers.auth import router as auth_router
from routers.llm import router as llm_router
from routers.monitoring import router as monitoring_router
from routers.system import router as system_router
from utils.exceptions import validation_exception_handler

from config.lifespan import lifespan
from config.settings import settings


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""

    # Create FastAPI application with custom docs URLs to ensure CDN resources load
    app = FastAPI(
        title=settings.API_TITLE,
        description=settings.API_DESCRIPTION,
        version=settings.API_VERSION,
        lifespan=lifespan,
        # Configure Swagger UI to work better with different environments
        swagger_ui_parameters={
            "deepLinking": True,
            "displayRequestDuration": True,
            "defaultModelsExpandDepth": 2,
            "defaultModelExpandDepth": 2,
            "displayOperationId": False,
            "tryItOutEnabled": True,
        },
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_CREDENTIALS,
        allow_methods=settings.CORS_METHODS,
        allow_headers=settings.CORS_HEADERS,
    )

    # Add shutdown middleware FIRST (outermost layer for graceful shutdown)
    app.middleware("http")(shutdown_middleware)

    # Add request ID middleware (for tracing)
    app.middleware("http")(request_id_middleware)

    # Add request limits middleware (body size, etc.)
    app.middleware("http")(request_limits_middleware)

    # Add metrics middleware
    app.middleware("http")(metrics_middleware)

    # Add security middleware
    app.middleware("http")(security_middleware)

    # Add exception handlers
    app.add_exception_handler(RequestValidationError, validation_exception_handler)

    # Add root endpoint for Swagger access
    from datetime import datetime

    @app.get("/")
    async def root():
        """Root endpoint providing a welcome message and API information."""
        return {
            "message": "LLMOps Secure API is running!",
            "version": settings.API_VERSION,
            "docs": "/docs",
            "redoc": "/redoc",
            "health": "/health",
            "health_detailed": "/health/detailed",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    # Root-level health endpoints for Docker/Kubernetes
    @app.get("/health", tags=["health"])
    async def root_health():
        """
        Basic liveness check at root level.

        For Docker healthcheck and load balancer probes.
        Always returns 200 if the application is running.
        """
        return {
            "status": "alive",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

    @app.get("/health/detailed", tags=["health"])
    async def root_health_detailed():
        """
        Detailed readiness check at root level.

        Redirects to /system/health/detailed for full dependency checks.
        """
        from fastapi.responses import JSONResponse
        from services.health_checker import health_checker

        results = await health_checker.check_all(use_cache=True)

        checks = {}
        for service_name, result in results.items():
            checks[service_name] = {
                "healthy": result.healthy,
                "latency_ms": round(result.latency_ms, 2)
                if result.latency_ms
                else None,
                "message": result.message,
            }

        all_healthy = all(r.healthy for r in results.values())

        response_data = {
            "status": "healthy" if all_healthy else "degraded",
            "checks": checks,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }

        return JSONResponse(
            status_code=200 if all_healthy else 503,
            content=response_data,
        )

    # Add OpenAI-compatible endpoint at root level
    @app.get("/v1/models")
    async def v1_models():
        """OpenAI-compatible models endpoint at root level."""
        try:
            import requests

            from config.settings import settings

            response = requests.get(f"{settings.LITELLM_URL}/models")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            from fastapi import HTTPException

            raise HTTPException(status_code=500, detail=f"Error fetching models: {e}")

    # Include routers
    app.include_router(auth_router)
    app.include_router(llm_router)
    app.include_router(system_router)
    app.include_router(monitoring_router)

    return app
