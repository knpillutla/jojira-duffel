"""
Car rental data models for search, offer retrieval, booking, and cancellation.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class CarSearchQuery:
    pickup_location: str  # IATA airport code, place ID, or location code
    dropoff_location: str
    pickup_datetime: str  # ISO 8601 string, e.g. "2026-09-01T10:00:00Z"
    dropoff_datetime: str  # ISO 8601 string, e.g. "2026-09-05T10:00:00Z"
    driver_age: int = 30

    def to_dict(self) -> dict[str, Any]:
        return {
            "pickup_location": self.pickup_location,
            "dropoff_location": self.dropoff_location,
            "pickup_datetime": self.pickup_datetime,
            "dropoff_datetime": self.dropoff_datetime,
            "driver_age": self.driver_age,
        }


@dataclass
class CarOffer:
    id: str
    supplier: dict[str, Any]
    vehicle: dict[str, Any]  # name, category, transmission, seats, image_url
    pickup_location: dict[str, Any]
    dropoff_location: dict[str, Any]
    pickup_datetime: str
    dropoff_datetime: str
    total_amount: str
    total_currency: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CarOffer":
        return cls(
            id=data.get("id", ""),
            supplier=data.get("supplier", {}),
            vehicle=data.get("vehicle", {}),
            pickup_location=data.get("pickup_location", {}),
            dropoff_location=data.get("dropoff_location", {}),
            pickup_datetime=data.get("pickup_datetime", ""),
            dropoff_datetime=data.get("dropoff_datetime", ""),
            total_amount=data.get("total_amount", "0.00"),
            total_currency=data.get("total_currency", "USD"),
            raw=data,
        )


@dataclass
class CarOrder:
    id: str
    booking_reference: str
    offer_id: str
    driver_details: dict[str, Any]
    pickup_datetime: str
    dropoff_datetime: str
    total_amount: str
    total_currency: str
    status: str
    created_at: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CarOrder":
        return cls(
            id=data.get("id", ""),
            booking_reference=data.get("booking_reference", ""),
            offer_id=data.get("offer_id", ""),
            driver_details=data.get("driver_details", {}),
            pickup_datetime=data.get("pickup_datetime", ""),
            dropoff_datetime=data.get("dropoff_datetime", ""),
            total_amount=data.get("total_amount", "0.00"),
            total_currency=data.get("total_currency", "USD"),
            status=data.get("status", "confirmed"),
            created_at=data.get("created_at", ""),
            raw=data,
        )


@dataclass
class CarCancellation:
    id: str
    order_id: str
    refund_amount: str
    refund_currency: str
    status: str
    created_at: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CarCancellation":
        return cls(
            id=data.get("id", ""),
            order_id=data.get("order_id", ""),
            refund_amount=data.get("refund_amount", "0.00"),
            refund_currency=data.get("refund_currency", "USD"),
            status=data.get("status", "cancelled"),
            created_at=data.get("created_at", ""),
            raw=data,
        )
