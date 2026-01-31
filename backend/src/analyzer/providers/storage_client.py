"""Google Cloud Storage client wrapper."""

import os
from pathlib import Path

from google.cloud import storage


class StorageClient:
    """
    Wrapper for Google Cloud Storage operations.

    Handles file upload/download, path management, and emulator support.
    """

    # GCS path prefixes
    ORIGINAL_PREFIX = "original"
    NORMALIZED_PREFIX = "normalized"
    OUTPUTS_PREFIX = "outputs"

    def __init__(
        self,
        bucket_name: str,
        use_emulator: bool = False,
        emulator_host: str = "localhost:9199",
    ):
        """
        Initialize Storage client.

        Args:
            bucket_name: GCS bucket name.
            use_emulator: Whether to use Firebase Storage Emulator.
            emulator_host: Emulator host:port.
        """
        self.bucket_name = bucket_name
        self.use_emulator = use_emulator

        if use_emulator:
            os.environ["STORAGE_EMULATOR_HOST"] = f"http://{emulator_host}"

        self._client = storage.Client()
        self._bucket = self._client.bucket(bucket_name)

    @property
    def bucket(self) -> storage.Bucket:
        """Get the storage bucket."""
        return self._bucket

    def get_original_path(self, meeting_id: str, filename: str) -> str:
        """Get GCS path for original file."""
        return f"{self.ORIGINAL_PREFIX}/{meeting_id}/{filename}"

    def get_normalized_path(self, meeting_id: str, filename: str) -> str:
        """Get GCS path for normalized file."""
        # Change extension to .docx for normalized files
        base_name = Path(filename).stem
        return f"{self.NORMALIZED_PREFIX}/{meeting_id}/{base_name}.docx"

    async def upload_file(
        self,
        local_path: str | Path,
        gcs_path: str,
        content_type: str | None = None,
    ) -> str:
        """
        Upload a file to GCS.

        Args:
            local_path: Local file path.
            gcs_path: Destination path in GCS.
            content_type: Optional MIME type.

        Returns:
            GCS URI (gs://bucket/path).
        """
        blob = self._bucket.blob(gcs_path)
        blob.upload_from_filename(str(local_path), content_type=content_type)
        return f"gs://{self.bucket_name}/{gcs_path}"

    async def upload_bytes(
        self,
        data: bytes,
        gcs_path: str,
        content_type: str | None = None,
    ) -> str:
        """
        Upload bytes to GCS.

        Args:
            data: File content as bytes.
            gcs_path: Destination path in GCS.
            content_type: Optional MIME type.

        Returns:
            GCS URI (gs://bucket/path).
        """
        blob = self._bucket.blob(gcs_path)
        blob.upload_from_string(data, content_type=content_type)
        return f"gs://{self.bucket_name}/{gcs_path}"

    async def download_file(self, gcs_path: str, local_path: str | Path) -> Path:
        """
        Download a file from GCS.

        Args:
            gcs_path: Source path in GCS.
            local_path: Local destination path.

        Returns:
            Path to downloaded file.
        """
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)

        blob = self._bucket.blob(gcs_path)
        blob.download_to_filename(str(local_path))
        return local_path

    async def download_bytes(self, gcs_path: str) -> bytes:
        """
        Download file content as bytes.

        Args:
            gcs_path: Source path in GCS.

        Returns:
            File content as bytes.
        """
        blob = self._bucket.blob(gcs_path)
        return blob.download_as_bytes()

    async def exists(self, gcs_path: str) -> bool:
        """Check if a file exists in GCS."""
        blob = self._bucket.blob(gcs_path)
        return blob.exists()

    async def delete(self, gcs_path: str) -> None:
        """Delete a file from GCS."""
        blob = self._bucket.blob(gcs_path)
        blob.delete()

    async def list_files(self, prefix: str) -> list[str]:
        """List files with a given prefix."""
        blobs = self._client.list_blobs(self._bucket, prefix=prefix)
        return [blob.name for blob in blobs]

    def get_public_url(self, gcs_path: str) -> str:
        """Get a public URL for a file (requires public access)."""
        return f"https://storage.googleapis.com/{self.bucket_name}/{gcs_path}"

    async def generate_signed_url(
        self,
        gcs_path: str,
        expiration_minutes: int = 60,
    ) -> str:
        """
        Generate a signed URL for temporary access.

        Uses IAM signing API when running on Cloud Run (no private key available).

        Args:
            gcs_path: File path in GCS.
            expiration_minutes: URL expiration time in minutes.

        Returns:
            Signed URL string.
        """
        from datetime import timedelta

        import google.auth
        from google.auth.transport import requests

        blob = self._bucket.blob(gcs_path)

        # Get default credentials and refresh to get the service account email
        credentials, project = google.auth.default()
        auth_request = requests.Request()
        credentials.refresh(auth_request)

        # Use IAM signing for Cloud Run (Compute Engine credentials)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(minutes=expiration_minutes),
            method="GET",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token,
        )
        return url
