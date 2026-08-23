"""
Duffel REST API Client Library for Python.
"""

from .client import DuffelClient
from .config import DuffelConfig
from .exceptions import (
    DuffelAPIError,
    DuffelAuthenticationError,
    DuffelException,
    DuffelNotFoundError,
    DuffelRateLimitError,
    DuffelValidationError,
)

__version__ = "1.0.0"
__all__ = [
    "DuffelClient",
    "DuffelConfig",
    "DuffelException",
    "DuffelAPIError",
    "DuffelAuthenticationError",
    "DuffelNotFoundError",
    "DuffelValidationError",
    "DuffelRateLimitError",
]
