"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

import firebase_admin
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from analyzer.api.router import api_router, internal_router
from analyzer.config import get_settings
from analyzer.logging_config import setup_logging
from analyzer.middleware.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def _configure_adk_environment(settings) -> None:
    """Configure environment variables for Google ADK (Agent Development Kit).

    ADK expects specific environment variable names for Vertex AI configuration.
    This maps our settings to ADK's expected format.

    Note: All Vertex AI services now use unified 'global' region (vertex_ai_location)
    for better availability and consistency across all Gemini models.
    """
    if settings.gcp_project_id:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.gcp_project_id)
    if settings.vertex_ai_location:
        os.environ.setdefault("GOOGLE_CLOUD_LOCATION", settings.vertex_ai_location)
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "true")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()

    # Setup logging with sensitive data filtering
    setup_logging(settings)

    if settings.debug:
        print(f"Starting {settings.app_name} in debug mode")

    # Configure ADK environment variables
    _configure_adk_environment(settings)

    # Initialize Firebase Admin SDK (for auth token verification)
    # Uses Application Default Credentials on Cloud Run
    if not firebase_admin._apps:
        firebase_admin.initialize_app()

    yield
    # Shutdown
    pass


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        description="AI-powered document analysis system for 3GPP standardization documents",
        lifespan=lifespan,
    )

    # Add rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "User-Agent",
            "DNT",
            "Cache-Control",
            "X-Requested-With",
        ],
        expose_headers=["Content-Disposition"],
        max_age=3600,
    )

    # Global exception handlers
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Handle all unhandled exceptions."""
        logger = logging.getLogger(__name__)
        logger.error(
            f"Unhandled exception: {type(exc).__name__}",
            exc_info=exc,
            extra={
                "path": request.url.path,
                "method": request.method,
            },
        )

        if settings.debug:
            # Development: Return detailed error
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": str(exc),
                    "type": type(exc).__name__,
                },
            )
        else:
            # Production: Return generic error
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "detail": "An internal error occurred. Please contact support.",
                },
            )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions - safe to expose."""
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Handle validation errors."""
        logger = logging.getLogger(__name__)
        logger.warning(
            f"Validation error: {exc.errors()}",
            extra={
                "path": request.url.path,
                "method": request.method,
            },
        )

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors()},
        )

    # Include routers
    app.include_router(api_router, prefix=settings.api_prefix)
    app.include_router(internal_router, prefix="/internal")

    @app.get("/health")
    async def health_check():
        """Health check endpoint."""
        return {"status": "healthy"}

    return app


app = create_app()
