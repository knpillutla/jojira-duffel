"""
Base service class for API operations.
"""

from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..http_client import HTTPClient


class BaseService:
    """Base class for domain specific services."""

    def __init__(
        self,
        http_client: "HTTPClient",
        cache: Optional[Any] = None,
        adapter: Optional[Any] = None,
    ):
        self.client = http_client
        self.cache = cache
        if adapter is not None:
            self.adapter = adapter
        else:
            from ..adapters.duffel_adapter import DuffelProviderAdapter
            self.adapter = DuffelProviderAdapter(http_client=http_client)
