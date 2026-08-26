"""
Factory and registry for Travel Provider Adapters.
"""

import os
from typing import Any, Dict, Optional, Type

from ..config import DuffelConfig
from ..http_client import HTTPClient
from .base import BaseProviderAdapter
from .duffel_adapter import DuffelProviderAdapter
from .mock_adapter import MockProviderAdapter


class ProviderFactory:
    """
    Factory to register and retrieve Provider Adapters.
    Allows switching backend travel providers (Duffel, Mock, Amadeus, etc.) dynamically.
    """

    _registry: Dict[str, Type[BaseProviderAdapter]] = {
        "duffel": DuffelProviderAdapter,
        "mock": MockProviderAdapter,
        "stub": MockProviderAdapter,
    }

    @classmethod
    def register_provider(cls, name: str, adapter_cls: Type[BaseProviderAdapter]) -> None:
        """Register a custom provider adapter class."""
        cls._registry[name.lower().strip()] = adapter_cls

    @classmethod
    def get_adapter(
        cls,
        provider_name: Optional[str] = None,
        config: Optional[DuffelConfig] = None,
        http_client: Optional[HTTPClient] = None,
    ) -> BaseProviderAdapter:
        """
        Instantiate and return the requested provider adapter.

        :param provider_name: Explicit provider key (e.g., 'duffel', 'mock'). If None, checks TRAVEL_PROVIDER env var, defaulting to 'duffel'.
        :param config: Optional DuffelConfig instance.
        :param http_client: Optional HTTPClient instance.
        :return: Instance of BaseProviderAdapter.
        """
        if not provider_name:
            provider_name = os.environ.get("TRAVEL_PROVIDER") or os.environ.get("DUFFEL_PROVIDER") or "duffel"

        key = provider_name.lower().strip()
        if key not in cls._registry:
            raise ValueError(f"Unknown travel provider adapter: '{provider_name}'. Registered providers: {list(cls._registry.keys())}")

        adapter_cls = cls._registry[key]
        if issubclass(adapter_cls, DuffelProviderAdapter):
            return adapter_cls(http_client=http_client, config=config)
        
        # For MockProviderAdapter or generic adapters taking default args
        try:
            return adapter_cls(provider_id=key)  # type: ignore
        except TypeError:
            return adapter_cls()  # type: ignore
