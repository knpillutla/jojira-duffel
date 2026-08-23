"""
Exceptions for the Duffel API client.
"""

from typing import Any, Optional


class DuffelException(Exception):
    """Base exception for Duffel API client errors."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class DuffelAPIError(DuffelException):
    """Exception raised when Duffel API returns an error HTTP status response."""

    def __init__(
        self,
        message: str,
        status_code: int,
        errors: Optional[list[dict[str, Any]]] = None,
        raw_response: Optional[dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.errors = errors or []
        self.raw_response = raw_response or {}

    def __str__(self) -> str:
        error_details = ""
        if self.errors:
            error_details = f" - Errors: {self.errors}"
        return f"[{self.status_code}] {self.message}{error_details}"


class DuffelAuthenticationError(DuffelAPIError):
    """Raised on 401 Unauthorized errors."""
    pass


class DuffelNotFoundError(DuffelAPIError):
    """Raised on 404 Not Found errors."""
    pass


class DuffelValidationError(DuffelAPIError):
    """Raised on 422 Unprocessable Entity / validation errors."""
    pass


class DuffelRateLimitError(DuffelAPIError):
    """Raised on 429 Rate Limit Exceeded errors."""
    pass
