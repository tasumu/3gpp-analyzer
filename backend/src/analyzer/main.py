"""FastAPI application entry point."""

import logging
import os
from contextlib import asynccontextmanager

import firebase_admin
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from analyzer.api.router import api_router, internal_router
from analyzer.config import get_settings

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def _configure_adk_environment(settings) -> None:
    """Configure environment variables for Google ADK (Agent Development Kit).

    ADK expects specific environment variable names for Vertex AI configuration.
    This maps our settings to ADK's expected format.
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

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
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
