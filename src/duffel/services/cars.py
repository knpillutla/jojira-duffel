"""
Service for Car Rentals API.
"""

from typing import Any, Optional, Union

from ..models.cars import (
    CarCancellation,
    CarOffer,
    CarOrder,
    CarSearchQuery,
)
from .base import BaseService


class CarsService(BaseService):
    """Integrates with Car Rental endpoints via Provider Adapter."""

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

        res = self.adapter.search_cars(query.to_dict())
        data = res.get("data", {})
        if isinstance(data, dict):
            raw_offers = data.get("offers", [])
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
        res = self.adapter.get_car_offer(offer_id)
        return CarOffer.from_dict(res.get("data", {}))

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

        res = self.adapter.create_car_order(payload)
        return CarOrder.from_dict(res.get("data", {}))

    def get_order(self, order_id: str) -> CarOrder:
        """
        Retrieve car order details.
        """
        res = self.adapter.get_car_order(order_id)
        return CarOrder.from_dict(res.get("data", {}))

    def cancel_order(self, order_id: str) -> CarCancellation:
        """
        Cancel a car rental order.
        """
        res = self.adapter.cancel_car_order(order_id)
        return CarCancellation.from_dict(res.get("data", {}))
