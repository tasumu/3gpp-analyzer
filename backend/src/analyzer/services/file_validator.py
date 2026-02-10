"""File validation service for security and error prevention."""

from pathlib import Path

import magic


class FileValidator:
    """Validate files for type, size, and other constraints."""

    # Allowed MIME types for documents
    ALLOWED_MIME_TYPES = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # docx
        "application/msword",  # doc
        "application/zip",
        "application/x-zip-compressed",
    }

    # Maximum file size: 100MB
    MAX_FILE_SIZE = 100 * 1024 * 1024

    @staticmethod
    def validate_file(file_path: Path) -> tuple[bool, str | None]:
        """
        Validate a file for type and size.

        Args:
            file_path: Path to the file to validate

        Returns:
            (is_valid, error_message): True if valid, False with error message if invalid
        """
        if not file_path.exists():
            return False, "File not found"

        # Check file size
        file_size = file_path.stat().st_size
        if file_size > FileValidator.MAX_FILE_SIZE:
            return False, f"File too large: {file_size} bytes (max {FileValidator.MAX_FILE_SIZE})"

        if file_size == 0:
            return False, "File is empty"

        # Check MIME type using magic numbers
        try:
            mime_type = magic.from_file(str(file_path), mime=True)
            if mime_type not in FileValidator.ALLOWED_MIME_TYPES:
                return False, f"Invalid file type: {mime_type}"
        except Exception as e:
            return False, f"Failed to detect file type: {e}"

        return True, None

    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename to prevent path traversal attacks.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename
        """
        # Remove path components (keep only basename)
        filename = Path(filename).name

        # Remove dangerous characters
        dangerous_chars = ["<", ">", ":", '"', "/", "\\", "|", "?", "*", "\x00"]
        for char in dangerous_chars:
            filename = filename.replace(char, "_")

        # Limit length to 255 characters (filesystem limit)
        if len(filename) > 255:
            # Keep extension
            if "." in filename:
                name, ext = filename.rsplit(".", 1)
                max_name_len = 255 - len(ext) - 1
                filename = f"{name[:max_name_len]}.{ext}"
            else:
                filename = filename[:255]

        return filename
