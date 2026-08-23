"""
Service for Duffel Car Rentals API.
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
    """Integrates with Duffel REST API Car Rental endpoints."""

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

        Endpoint: POST /cars/search_requests or GET /cars/offers
        """
        query = CarSearchQuery(
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_datetime=pickup_datetime,
            dropoff_datetime=dropoff_datetime,
            driver_age=driver_age,
        )

        res = self.client.post("/cars/search_requests", data={"data": query.to_dict()})
        data = res.get("data", {})
        raw_offers = data.get("offers", []) if isinstance(data, dict) else []

        return [CarOffer.from_dict(o) for o in raw_offers]

    def get_offer(self, offer_id: str) -> CarOffer:
        """
        Retrieve details of a car rental offer.

        Endpoint: GET /cars/offers/{id}
        """
        res = self.client.get(f"/cars/offers/{offer_id}")
        return CarOffer.from_dict(res.get("data", {}))

    def create_order(
        self,
        offer_id: str,
        driver_details: dict[str, Any],
        payments: list[dict[str, Any]],
    ) -> CarOrder:
        """
        Create a car rental order.

        Endpoint: POST /cars/orders
        """
        payload = {
            "offer_id": offer_id,
            "driver_details": driver_details,
            "payments": payments,
        }

        res = self.client.post("/cars/orders", data={"data": payload})
        return CarOrder.from_dict(res.get("data", {}))

    def get_order(self, order_id: str) -> CarOrder:
        """
        Retrieve car order details.

        Endpoint: GET /cars/orders/{id}
        """
        res = self.client.get(f"/cars/orders/{order_id}")
        return CarOrder.from_dict(res.get("data", {}))

    def cancel_order(self, order_id: str) -> CarCancellation:
        """
        Cancel a car rental order.

        Endpoint: POST /cars/orders/{id}/actions/cancel
        """
        res = self.client.post(f"/cars/orders/{order_id}/actions/cancel")
        return CarCancellation.from_dict(res.get("data", {}))
