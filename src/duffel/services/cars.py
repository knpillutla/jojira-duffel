"""
Service for Car Rentals API.
"""

from typing import Any, Optional, Union

from ..adapters.mock_adapter import MockProviderAdapter
from ..exceptions import DuffelException
from ..models.cars import (
    CarCancellation,
    CarOffer,
    CarOrder,
    CarSearchQuery,
)
from .base import BaseService
from .planner import DESTINATION_GEO_MAP

DEFAULT_SEARCH_RADIUS_KM = 5


def _split_iso_datetime(iso_str: str) -> tuple[str, str]:
    """Splits an ISO 8601 datetime (e.g. '2026-09-15T10:00:00Z') into Duffel's separate date + HH:MM time fields."""
    try:
        date_part, time_part = iso_str.split("T")
        return date_part, time_part.rstrip("Z")[:5]
    except Exception as err:
        raise DuffelException(
            f"Invalid datetime '{iso_str}'. Expected ISO 8601 format e.g. '2026-09-15T10:00:00Z'."
        ) from err


def _resolve_geo(location: str) -> dict[str, float]:
    """Resolves a free-text location (e.g. 'Paris CDG Airport') to geographic coordinates via known city lookup."""
    key = location.strip().upper()
    geo = DESTINATION_GEO_MAP.get(key)
    if not geo:
        geo = next((data for city, data in DESTINATION_GEO_MAP.items() if city in key or key in city), None)
    if not geo:
        raise DuffelException(
            f"Unable to resolve location '{location}' to coordinates. Duffel requires geographic_coordinates. "
            f"Supported city names: {sorted(DESTINATION_GEO_MAP.keys())}."
        )
    return {"latitude": geo["latitude"], "longitude": geo["longitude"]}


class CarsService(BaseService):
    """Integrates with Car Rental endpoints via Provider Adapter."""

    _mock_adapter: Optional[MockProviderAdapter] = None

    def _mock(self) -> MockProviderAdapter:
        """Lazily creates a shared mock adapter used only when test_mode is enabled."""
        if CarsService._mock_adapter is None:
            CarsService._mock_adapter = MockProviderAdapter()
        return CarsService._mock_adapter

    def _adapter_call(self, method_name: str, *args: Any, friendly_action: str) -> dict[str, Any]:
        """
        Calls the configured adapter's car method. If it fails: returns mock data when
        config.test_mode is enabled, otherwise raises a clear DuffelException.
        """
        try:
            return getattr(self.adapter, method_name)(*args)
        except Exception as err:
            if getattr(self.client.config, "test_mode", False):
                return getattr(self._mock(), method_name)(*args)
            raise DuffelException(f"Unable to {friendly_action}. {err}") from err

    def search(
        self,
        pickup_location: str,
        dropoff_location: str,
        pickup_datetime: str,
        dropoff_datetime: str,
        driver_age: int = 30,
    ) -> list[CarOffer]:
        """
        Search for rental cars.
        """
        import hashlib

        # 2-Tier Redis Cache Lookup
        hash_input = f"{pickup_location}_{dropoff_location}_{pickup_datetime}_{dropoff_datetime}_{driver_age}"
        hash_key = hashlib.md5(hash_input.encode("utf-8")).hexdigest()[:6]
        cache_key = f"duffel:cars:search:{hash_key}"

        if self.cache and self.cache.enabled:
            cached_res = self.cache.get(cache_key)
            if cached_res and isinstance(cached_res, list):
                print(f"[+] TIER-1 CARS CACHE HIT for key: {cache_key}")
                return [CarOffer.from_dict(o) for o in cached_res]

        query = CarSearchQuery(
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_datetime=pickup_datetime,
            dropoff_datetime=dropoff_datetime,
            driver_age=driver_age,
        )

        pickup_date, pickup_time = _split_iso_datetime(pickup_datetime)
        dropoff_date, dropoff_time = _split_iso_datetime(dropoff_datetime)
        payload = {
            "pickup_date": pickup_date,
            "pickup_time": pickup_time,
            "pickup_location": {
                "radius": DEFAULT_SEARCH_RADIUS_KM,
                "geographic_coordinates": _resolve_geo(pickup_location),
            },
            "dropoff_date": dropoff_date,
            "dropoff_time": dropoff_time,
            "dropoff_location": {
                "radius": DEFAULT_SEARCH_RADIUS_KM,
                "geographic_coordinates": _resolve_geo(dropoff_location),
            },
            "driver": {"age": driver_age},
        }

        res = self._adapter_call("search_cars", payload, friendly_action="search rental cars")
        data = res.get("data", {})
        if isinstance(data, dict):
            raw_offers = data.get("rates") or data.get("offers", [])
        elif isinstance(data, list):
            raw_offers = data
        else:
            raw_offers = []

        raw_list = [o if isinstance(o, dict) else getattr(o, "__dict__", {}) for o in raw_offers]
        if self.cache and self.cache.enabled:
            # 1. Record-Level Redis Caching (individual offer key with individual TTL)
            self.cache.set_records_batch("cars", raw_list, id_key="id")
            # 2. Query Index Caching
            dynamic_ttl = self.cache.calculate_earliest_ttl(raw_list)
            self.cache.set(cache_key, raw_list, ttl_seconds=dynamic_ttl)

        return [CarOffer.from_dict(o) for o in raw_offers]

    def get_offer(self, offer_id: str) -> CarOffer:
        """
        Retrieve details of a car rental offer.
        """
        res = self._adapter_call("get_car_offer", offer_id, friendly_action="fetch the car rental offer")
        return CarOffer.from_dict(res.get("data", {}))

    def create_quote(self, rate_id: str) -> dict[str, Any]:
        """
        Creates a priced, availability-confirmed quote from a search rate (required before booking).
        """
        res = self._adapter_call("create_car_quote", rate_id, friendly_action="create a car rental quote")
        return res.get("data", {})

    def create_order(
        self,
        offer_id: str,
        driver_details: dict[str, Any],
        payments: list[dict[str, Any]],
    ) -> CarOrder:
        """
        Create a car rental order.
        """
        payload = {
            "offer_id": offer_id,
            "driver_details": driver_details,
            "payments": payments,
        }

        res = self._adapter_call("create_car_order", payload, friendly_action="book the car rental")
        return CarOrder.from_dict(res.get("data", {}))

    def get_order(self, order_id: str) -> CarOrder:
        """
        Retrieve car order details.
        """
        res = self._adapter_call("get_car_order", order_id, friendly_action="fetch the car rental order")
        return CarOrder.from_dict(res.get("data", {}))

    def cancel_order(self, order_id: str) -> CarCancellation:
        """
        Cancel a car rental order.
        """
        res = self._adapter_call("cancel_car_order", order_id, friendly_action="cancel the car rental order")
        return CarCancellation.from_dict(res.get("data", {}))
