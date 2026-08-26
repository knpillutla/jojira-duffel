"""
Duffel API Provider Adapter.
"""

from typing import Any, Optional

from ..config import DuffelConfig
from ..http_client import HTTPClient
from .base import BaseProviderAdapter


class DuffelProviderAdapter(BaseProviderAdapter):
    """
    Concrete provider adapter for interacting with the Duffel REST API.
    Handles HTTP communications with api.duffel.com.
    """

    def __init__(self, http_client: Optional[HTTPClient] = None, config: Optional[DuffelConfig] = None):
        if http_client is not None:
            self.http_client = http_client
        elif config is not None:
            self.http_client = HTTPClient(config)
        else:
            self.http_client = HTTPClient(DuffelConfig())

    # --- Flight Operations ---

    def search_flights(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/air/offer_requests", data={"data": payload})

    def get_offer_request(self, offer_request_id: str) -> dict[str, Any]:
        return self.http_client.request("GET", f"/air/offer_requests/{offer_request_id}")

    def list_offers(self, offer_request_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        p = dict(params) if params else {}
        p["offer_request_id"] = offer_request_id
        return self.http_client.request("GET", "/air/offers", params=p)

    def get_offer(self, offer_id: str) -> dict[str, Any]:
        return self.http_client.request("GET", f"/air/offers/{offer_id}")

    def create_flight_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/air/orders", data={"data": payload})

    def pay_flight_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", f"/air/orders/{order_id}/actions/pay", data={"data": payload})

    def get_flight_order(self, order_id: str) -> dict[str, Any]:
        return self.http_client.request("GET", f"/air/orders/{order_id}")

    def list_flight_orders(self, limit: int = 50) -> dict[str, Any]:
        return self.http_client.request("GET", "/air/orders", params={"limit": limit})

    def cancel_flight_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/air/order_cancellations", data={"data": payload})

    def tokenize_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/air/card_tokens", data={"data": payload})

    def create_component_client_key(self) -> dict[str, Any]:
        return self.http_client.request("POST", "/air/component_client_keys")

    def create_three_d_secure_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/air/three_d_secure_sessions", data={"data": payload})

    # --- Stay Operations ---

    def search_stays(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/stays/search", data={"data": payload})

    def get_stay_search_result(self, search_result_id: str) -> dict[str, Any]:
        return self.http_client.request("GET", f"/stays/search_requests/{search_result_id}")

    def get_stay_rates(self, search_result_id: str) -> dict[str, Any]:
        return self.http_client.request("POST", f"/stays/search_results/{search_result_id}/actions/fetch_all_rates")

    def create_stay_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/stays/bookings", data={"data": payload})

    def get_stay_order(self, order_id: str) -> dict[str, Any]:
        return self.http_client.request("GET", f"/stays/bookings/{order_id}")

    def cancel_stay_order(self, order_id: str) -> dict[str, Any]:
        return self.http_client.request("POST", f"/stays/bookings/{order_id}/actions/cancel")

    # --- Car Operations ---
    # Verified against https://duffel.com/docs/api/v2/cars-search, cars-quotes, cars-bookings

    def search_cars(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/cars/search", data={"data": payload})

    def create_car_quote(self, rate_id: str) -> dict[str, Any]:
        return self.http_client.request("POST", "/cars/quotes", data={"data": {"rate_id": rate_id}})

    def get_car_offer(self, offer_id: str) -> dict[str, Any]:
        return self.http_client.request("GET", f"/cars/quotes/{offer_id}")

    def create_car_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.http_client.request("POST", "/cars/bookings", data={"data": payload})

    def get_car_order(self, order_id: str) -> dict[str, Any]:
        return self.http_client.request("GET", f"/cars/bookings/{order_id}")

    def cancel_car_order(self, offer_id_or_order_id: str) -> dict[str, Any]:
        return self.http_client.request("POST", f"/cars/bookings/{offer_id_or_order_id}/actions/cancel")

    # --- Places & Airports Operations ---

    def list_airports(self, limit: int = 200) -> dict[str, Any]:
        return self.http_client.request("GET", "/air/airports", params={"limit": limit})

    def list_cities(self, limit: int = 200) -> dict[str, Any]:
        return self.http_client.request("GET", "/air/cities", params={"limit": limit})

    def search_places(self, query: str) -> dict[str, Any]:
        return self.http_client.request("GET", "/places/suggestions", params={"query": query})

