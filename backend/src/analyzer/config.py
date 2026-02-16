"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Application
    app_name: str = "3GPP Analyzer"
    debug: bool = False

    # Firebase/GCP
    gcp_project_id: str = ""
    firebase_credentials_path: str = ""
    use_firebase_emulator: bool = False
    firebase_auth_emulator_host: str = ""

    # Firestore
    firestore_emulator_host: str = "localhost:8080"

    # Storage
    gcs_bucket_name: str = ""
    storage_emulator_host: str = "localhost:9199"

    # FTP (3GPP)
    ftp_host: str = "ftp.3gpp.org"
    ftp_user: str = "anonymous"
    ftp_password: str = ""
    ftp_base_path: str = "/Meetings"
    ftp_mock_mode: bool = False  # Use mock data for development

    # Vertex AI - Unified global location for all services
    # Note: All Gemini models (embedding, 2.5-flash, 3-pro-preview) are available in global region
    # Global region provides better availability and reduces 429 errors
    vertex_ai_location: str = "global"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 100

    # Processing
    libreoffice_timeout: int = 60
    chunk_max_tokens: int = 1000

    # Analysis (Phase 2)
    analysis_model: str = "gemini-2.5-flash"
    analysis_strategy_version: str = "v1"
    review_sheet_expiration_minutes: int = 60

    # Phase 3: Meeting Analysis & Q&A
    meeting_flash_model: str = "gemini-2.5-flash"  # Lightweight model for individual summaries
    meeting_pro_model: str = "gemini-3-pro-preview"  # High-performance model for overall reports
    qa_model: str = "gemini-3-pro-preview"  # Model for Q&A agents
    meeting_summary_strategy_version: str = "v1"

    # Context Caching (cost optimization for agentic search)
    context_cache_enabled: bool = True
    context_cache_ttl_seconds: int = 1800
    context_cache_min_tokens: int = 4096
    context_cache_intervals: int = 10

    # API
    api_prefix: str = "/api"
    # CORS_ORIGINS env var should be comma-separated list of allowed origins
    # e.g., "http://localhost:3000,https://example.com"
    cors_origins_str: str = "http://localhost:3000"

    # Admin Approval
    initial_admin_emails_str: str = Field(
        default="", validation_alias="INITIAL_ADMIN_EMAILS"
    )  # Comma-separated admin emails

    @property
    def cors_origins(self) -> list[str]:
        """Parse CORS origins from comma-separated string."""
        return [origin.strip() for origin in self.cors_origins_str.split(",") if origin.strip()]

    @property
    def initial_admin_emails(self) -> list[str]:
        """Parse initial admin emails from comma-separated string."""
        if not self.initial_admin_emails_str:
            return []
        return [
            email.strip() for email in self.initial_admin_emails_str.split(",") if email.strip()
        ]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
