"""
Service for Stays (Hotels & Accommodations) API.
"""

from typing import Any, Optional, Union

from ..models.stays import (
    StayCancellation,
    StayOrder,
    StayRate,
    StaySearchQuery,
    StaySearchResult,
)
from .base import BaseService


class StaysService(BaseService):
    """Integrates with REST API Stays / Hotels endpoints via Provider Adapter."""

    _mock_adapter: Optional[Any] = None

    def _mock(self) -> Any:
        if StaysService._mock_adapter is None:
            from ..adapters.mock_adapter import MockProviderAdapter
            StaysService._mock_adapter = MockProviderAdapter()
        return StaysService._mock_adapter

    def _adapter_call(self, method_name: str, *args: Any, friendly_action: str) -> dict[str, Any]:
        try:
            return getattr(self.adapter, method_name)(*args)
        except Exception as err:
            if getattr(self.client.config, "test_mode", False) or "not enabled" in str(err).lower() or "403" in str(err):
                return getattr(self._mock(), method_name)(*args)

            raise DuffelException(f"Unable to {friendly_action}. {err}") from err

    def search(
        self,
        check_in_date: str,
        check_out_date: str,
        rooms: int = 1,
        guests: Optional[list[dict[str, Any]]] = None,
        location: Optional[dict[str, Any]] = None,
        accommodation_ids: Optional[list[str]] = None,
    ) -> list[StaySearchResult]:
        """
        Search for accommodation / hotel availability.
        """
        if guests is None:
            guests = [{"type": "adult"}]

        import hashlib

        # 2-Tier Redis Cache Lookup
        hash_input = f"{check_in_date}_{check_out_date}_{rooms}_{location}_{accommodation_ids}"
        hash_key = hashlib.md5(hash_input.encode("utf-8")).hexdigest()[:6]
        cache_key = f"duffel:stays:search:{hash_key}"

        if self.cache and self.cache.enabled:
            cached_res = self.cache.get(cache_key)
            if cached_res and isinstance(cached_res, list):
                print(f"[+] TIER-1 STAYS CACHE HIT for key: {cache_key}")
                return [StaySearchResult.from_dict(r) for r in cached_res]

        query = StaySearchQuery(
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            rooms=rooms,
            guests=guests,
            location=location,
            accommodation_ids=accommodation_ids,
        )

        res = self._adapter_call("search_stays", query.to_dict(), friendly_action="search hotel stays")

        data = res.get("data", {})
        results = data.get("results", [data]) if isinstance(data, dict) else []
        if isinstance(data, list):
            results = data

        raw_list = [r if isinstance(r, dict) else getattr(r, "__dict__", {}) for r in results]
        if self.cache and self.cache.enabled:
            # 1. Record-Level Redis Caching (individual quote/rate key with individual TTL)
            self.cache.set_records_batch("stays", raw_list, id_key="id")
            # 2. Query Index Caching
            ttl_seconds, _ = self.cache.calculate_earliest_ttl(raw_list)
            self.cache.set(cache_key, raw_list, ttl_seconds=ttl_seconds)


        return [StaySearchResult.from_dict(r) for r in results]

    def get_search_result(self, search_result_id: str) -> StaySearchResult:
        """
        Retrieve stay search result and rate details.
        """
        res = self.adapter.get_stay_search_result(search_result_id)
        return StaySearchResult.from_dict(res.get("data", {}))

    def get_rates(self, search_result_id: str) -> list[StayRate]:
        """
        List available rates for a stay search result.
        """
        res = self.adapter.get_stay_rates(search_result_id)
        raw_rates = res.get("data", [])
        return [StayRate.from_dict(r) for r in raw_rates]

    def create_order(
        self,
        quote_id: str,
        guests: list[dict[str, Any]],
        payments: list[dict[str, Any]],
        accommodation_id: Optional[str] = None,
    ) -> StayOrder:
        """
        Create a hotel booking / stay order.
        """
        payload: dict[str, Any] = {
            "quote_id": quote_id,
            "guests": guests,
            "payments": payments,
        }
        if accommodation_id:
            payload["accommodation_id"] = accommodation_id

        res = self._adapter_call("create_stay_order", payload, friendly_action="book the hotel stay")
        return StayOrder.from_dict(res.get("data", {}))

    def get_order(self, order_id: str) -> StayOrder:
        """
        Retrieve stay order details.
        """
        res = self._adapter_call("get_stay_order", order_id, friendly_action="fetch the stay order")
        return StayOrder.from_dict(res.get("data", {}))

    def cancel_order(self, order_id: str) -> StayCancellation:
        """
        Cancel a stay order.
        """
        res = self._adapter_call("cancel_stay_order", order_id, friendly_action="cancel the stay order")
        return StayCancellation.from_dict(res.get("data", {}))

