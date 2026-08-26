"""
Duffel REST API Client Library for Python.
"""

from .adapters import (
    BaseProviderAdapter,
    DuffelProviderAdapter,
    MockProviderAdapter,
    ProviderFactory,
)
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
    "BaseProviderAdapter",
    "DuffelProviderAdapter",
    "MockProviderAdapter",
    "ProviderFactory",
    "DuffelException",
    "DuffelAPIError",
    "DuffelAuthenticationError",
    "DuffelNotFoundError",
    "DuffelValidationError",
    "DuffelRateLimitError",
]
