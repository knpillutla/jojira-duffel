"""
Main Duffel Client orchestrator.
"""

from typing import Optional, Union

from .adapters import BaseProviderAdapter, ProviderFactory
from .cache import DuffelCache
from .config import DuffelConfig
from .http_client import HTTPClient
from .services.cars import CarsService
from .services.flights import FlightsService
from .services.stays import StaysService


class DuffelClient:
    """
    Main entry point for interacting with the Duffel REST API (or configured provider adapter).

    Usage:
        client = DuffelClient(api_token="duffel_test_...")
        offers = client.flights.search_optimized(...)
        stays = client.stays.search(...)
        cars = client.cars.search(...)
    """

    def __init__(
        self,
        api_token: Optional[str] = None,
        config: Optional[DuffelConfig] = None,
        base_url: str = "https://api.duffel.com",
        api_version: str = "v2",
        timeout: float = 5.0,
        debug: bool = False,
        provider_name: Optional[str] = None,
        adapter: Optional[BaseProviderAdapter] = None,
    ):
        if config is not None:
            self.config = config
        else:
            self.config = DuffelConfig(
                api_token=api_token or "",
                base_url=base_url,
                api_version=api_version,
                timeout=timeout,
                debug=debug,
            )

        self.cache = DuffelCache(self.config)
        self.http_client = HTTPClient(self.config)

        if adapter is not None:
            self.adapter = adapter
        else:
            self.adapter = ProviderFactory.get_adapter(
                provider_name=provider_name,
                config=self.config,
                http_client=self.http_client,
            )

        from .services.bundles import BundlesService
        from .services.natural_search import NaturalSearchService
        from .services.planner import TravelPlannerService

        # Service instances
        self.flights = FlightsService(self.http_client, cache=self.cache, adapter=self.adapter)
        self.stays = StaysService(self.http_client, cache=self.cache, adapter=self.adapter)
        self.cars = CarsService(self.http_client, cache=self.cache, adapter=self.adapter)
        self.bundles = BundlesService(self.http_client, cache=self.cache, adapter=self.adapter, client=self)
        self.planner = TravelPlannerService(self.http_client, cache=self.cache, adapter=self.adapter, client=self)
        self.natural_search = NaturalSearchService(self.http_client, cache=self.cache, adapter=self.adapter, client=self)


