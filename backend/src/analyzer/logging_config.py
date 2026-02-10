"""Logging configuration with sensitive data filtering."""

import logging
import re


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data in logs."""

    # Patterns to match and replace sensitive data
    SENSITIVE_PATTERNS = [
        # Password fields
        (r'password["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', r'password=***REDACTED***'),
        # API keys
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?([^"\'\s,}]+)', r'api_key=***REDACTED***'),
        # Bearer tokens in Authorization headers
        (r'Bearer\s+([A-Za-z0-9\-._~+/]+=*)', r'Bearer ***REDACTED***'),
        # JWT tokens (starting with eyJ)
        (r'eyJ[A-Za-z0-9\-._~+/]+=*', r'***JWT_REDACTED***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Filter and mask sensitive data in log messages."""
        # Filter message
        if isinstance(record.msg, str):
            for pattern, replacement in self.SENSITIVE_PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg, flags=re.IGNORECASE)

        # Filter args
        if record.args:
            cleaned_args = []
            for arg in record.args:
                if isinstance(arg, str):
                    for pattern, replacement in self.SENSITIVE_PATTERNS:
                        arg = re.sub(pattern, replacement, arg, flags=re.IGNORECASE)
                cleaned_args.append(arg)
            record.args = tuple(cleaned_args)

        return True


def setup_logging(settings):
    """
    Setup logging configuration with sensitive data filtering.

    Args:
        settings: Application settings instance
    """
    # Get root logger
    root_logger = logging.getLogger()

    # Add sensitive data filter to all handlers
    for handler in root_logger.handlers:
        handler.addFilter(SensitiveDataFilter())

    # Configure logging level
    log_level = logging.DEBUG if settings.debug else logging.INFO

    # Configure basic logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
        force=True,  # Override any existing configuration
    )
