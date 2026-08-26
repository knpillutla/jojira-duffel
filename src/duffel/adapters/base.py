"""
Base Provider Adapter defining abstract interface for travel API operations.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class BaseProviderAdapter(ABC):
    """
    Abstract base class for provider adapters (e.g. Duffel, Amadeus, Sabre, Mock).
    All provider implementations must inherit from this class.
    """

    # --- Flight Operations ---

    @abstractmethod
    def search_flights(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a flight search / offer request on the provider API."""
        pass

    @abstractmethod
    def get_offer_request(self, offer_request_id: str) -> dict[str, Any]:
        """Fetch details of a specific offer request by ID."""
        pass

    @abstractmethod
    def list_offers(self, offer_request_id: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """List offers for a given offer request ID."""
        pass

    @abstractmethod
    def get_offer(self, offer_id: str) -> dict[str, Any]:
        """Fetch details of a specific flight offer by ID."""
        pass

    @abstractmethod
    def create_flight_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a flight order / booking."""
        pass

    @abstractmethod
    def pay_flight_order(self, order_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        """Pay for an existing flight order."""
        pass

    @abstractmethod
    def get_flight_order(self, order_id: str) -> dict[str, Any]:
        """Fetch details of a flight order by ID."""
        pass

    @abstractmethod
    def list_flight_orders(self, limit: int = 50) -> dict[str, Any]:
        """List recent flight orders."""
        pass

    @abstractmethod
    def cancel_flight_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Cancel a flight order."""
        pass

    @abstractmethod
    def tokenize_card(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Tokenize card payment details."""
        pass

    @abstractmethod
    def create_component_client_key(self) -> dict[str, Any]:
        """Create a client key for UI components."""
        pass

    @abstractmethod
    def create_three_d_secure_session(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Create a 3D Secure verification session."""
        pass

    # --- Stay Operations ---

    @abstractmethod
    def search_stays(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Search for hotel / stay availability."""
        pass

    @abstractmethod
    def get_stay_search_result(self, search_result_id: str) -> dict[str, Any]:
        """Get details of a stay search result."""
        pass

    @abstractmethod
    def get_stay_rates(self, search_result_id: str) -> dict[str, Any]:
        """Get rates for a stay search result."""
        pass

    @abstractmethod
    def create_stay_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Book a stay order."""
        pass

    @abstractmethod
    def get_stay_order(self, order_id: str) -> dict[str, Any]:
        """Fetch details of a stay order."""
        pass

    @abstractmethod
    def cancel_stay_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a stay order."""
        pass

    # --- Car Operations ---

    @abstractmethod
    def search_cars(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Search for car rental availability."""
        pass

    @abstractmethod
    def get_car_offer(self, offer_id: str) -> dict[str, Any]:
        """Fetch details of a car rental offer."""
        pass

    @abstractmethod
    def create_car_order(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Book a car rental order."""
        pass

    @abstractmethod
    def get_car_order(self, order_id: str) -> dict[str, Any]:
        """Fetch details of a car order."""
        pass

    @abstractmethod
    def cancel_car_order(self, order_id: str) -> dict[str, Any]:
        """Cancel a car rental order."""
        pass
