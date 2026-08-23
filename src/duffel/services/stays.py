"""
Service for Duffel Stays (Hotels & Accommodations) API.
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
    """Integrates with Duffel REST API Stays / Hotels endpoints."""

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

        Endpoint: POST /stays/search_requests
        """
        if guests is None:
            guests = [{"type": "adult"}]

        query = StaySearchQuery(
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            rooms=rooms,
            guests=guests,
            location=location,
            accommodation_ids=accommodation_ids,
        )

        res = self.client.post("/stays/search_requests", data={"data": query.to_dict()})
        data = res.get("data", {})
        results = data.get("results", [data]) if isinstance(data, dict) else []
        if isinstance(data, list):
            results = data

        return [StaySearchResult.from_dict(r) for r in results]

    def get_search_result(self, search_result_id: str) -> StaySearchResult:
        """
        Retrieve stay search result and rate details.

        Endpoint: GET /stays/search_requests/{id} or /stays/results/{id}
        """
        res = self.client.get(f"/stays/search_requests/{search_result_id}")
        return StaySearchResult.from_dict(res.get("data", {}))

    def get_rates(self, search_result_id: str) -> list[StayRate]:
        """
        List available rates for a stay search result.

        Endpoint: GET /stays/results/{id}/rates
        """
        res = self.client.get(f"/stays/results/{search_result_id}/rates")
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

        Endpoint: POST /stays/orders
        """
        payload: dict[str, Any] = {
            "quote_id": quote_id,
            "guests": guests,
            "payments": payments,
        }
        if accommodation_id:
            payload["accommodation_id"] = accommodation_id

        res = self.client.post("/stays/orders", data={"data": payload})
        return StayOrder.from_dict(res.get("data", {}))

    def get_order(self, order_id: str) -> StayOrder:
        """
        Retrieve stay order details.

        Endpoint: GET /stays/orders/{id}
        """
        res = self.client.get(f"/stays/orders/{order_id}")
        return StayOrder.from_dict(res.get("data", {}))

    def cancel_order(self, order_id: str) -> StayCancellation:
        """
        Cancel a stay order.

        Endpoint: POST /stays/orders/{id}/actions/cancel or POST /stays/cancellations
        """
        res = self.client.post(f"/stays/orders/{order_id}/actions/cancel")
        return StayCancellation.from_dict(res.get("data", {}))
