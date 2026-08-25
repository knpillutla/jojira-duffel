"""
Main Duffel Client orchestrator.
"""

from typing import Optional, Union

from .cache import DuffelCache
from .config import DuffelConfig
from .http_client import HTTPClient
from .services.cars import CarsService
from .services.flights import FlightsService
from .services.stays import StaysService


class DuffelClient:
    """
    Main entry point for interacting with the Duffel REST API.

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

        # Service instances
        self.flights = FlightsService(self.http_client, cache=self.cache)
        self.stays = StaysService(self.http_client, cache=self.cache)
        self.cars = CarsService(self.http_client, cache=self.cache)
