"""Application configuration using pydantic-settings."""

from functools import lru_cache

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

    # Vertex AI / Embedding
    embedding_model: str = "text-embedding-004"
    embedding_dimensions: int = 768
    embedding_batch_size: int = 100

    # Processing
    libreoffice_timeout: int = 60
    chunk_max_tokens: int = 1000

    # API
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:3000"]


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
