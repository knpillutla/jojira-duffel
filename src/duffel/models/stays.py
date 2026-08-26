"""
Stays (Hotels) data models for search, rate retrieval, booking, and cancellation.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class StaySearchQuery:
    check_in_date: str  # YYYY-MM-DD
    check_out_date: str  # YYYY-MM-DD
    rooms: int = 1
    guests: list[dict[str, Any]] = field(default_factory=lambda: [{"type": "adult"}])
    location: Optional[dict[str, Any]] = None  # {"geographic_coordinates": {"latitude": ..., "longitude": ...}} or {"place_id": ...}
    accommodation_ids: Optional[list[str]] = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "check_in_date": self.check_in_date,
            "check_out_date": self.check_out_date,
            "rooms": self.rooms,
            "guests": self.guests,
        }
        if self.location:
            data["location"] = self.location
        if self.accommodation_ids:
            data["accommodation_ids"] = self.accommodation_ids
        return data


@dataclass
class StayRate:
    id: str
    total_amount: str
    total_currency: str
    board_type: str
    description: str
    cancellation_timeline: list[dict[str, Any]]
    available_rooms: int
    quote_id: Optional[str] = None  # Duffel quote ID needed for booking
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StayRate":
        return cls(
            id=data.get("id", ""),
            total_amount=data.get("total_amount", "0.00"),
            total_currency=data.get("total_currency", "USD"),
            board_type=data.get("board_type", "room_only"),
            description=data.get("description", ""),
            cancellation_timeline=data.get("cancellation_timeline", []),
            available_rooms=data.get("available_rooms", 1),
            quote_id=data.get("quote_id"),
            raw=data,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to API response format."""
        result = {
            "id": self.id,
            "total_amount": self.total_amount,
            "total_currency": self.total_currency,
            "board_type": self.board_type,
            "description": self.description,
            "cancellation_timeline": self.cancellation_timeline,
            "available_rooms": self.available_rooms,
        }
        if self.quote_id:
            result["quote_id"] = self.quote_id  # Include for booking
        return result


@dataclass
class StaySearchResult:
    id: str
    accommodation: dict[str, Any]
    rates: list[StayRate]
    created_at: str
    search_request_id: Optional[str] = None  # Duffel search request ID for fetching rates
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StaySearchResult":
        rates = [StayRate.from_dict(r) for r in data.get("rates", [])]
        return cls(
            id=data.get("id", ""),
            accommodation=data.get("accommodation", {}),
            rates=rates,
            created_at=data.get("created_at", ""),
            search_request_id=data.get("search_request_id"),
            raw=data,
        )
    
    def to_dict(self) -> dict[str, Any]:
        """Serialize to API response format."""
        result = {
            "id": self.id,
            "accommodation": self.accommodation,
            "rates": [r.to_dict() for r in self.rates],
            "created_at": self.created_at,
        }
        if self.search_request_id:
            result["search_request_id"] = self.search_request_id
        return result


@dataclass
class StayOrder:
    id: str
    booking_reference: str
    accommodation: dict[str, Any]
    check_in_date: str
    check_out_date: str
    guests: list[dict[str, Any]]
    total_amount: str
    total_currency: str
    status: str
    created_at: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StayOrder":
        return cls(
            id=data.get("id", ""),
            booking_reference=data.get("booking_reference", ""),
            accommodation=data.get("accommodation", {}),
            check_in_date=data.get("check_in_date", ""),
            check_out_date=data.get("check_out_date", ""),
            guests=data.get("guests", []),
            total_amount=data.get("total_amount", "0.00"),
            total_currency=data.get("total_currency", "USD"),
            status=data.get("status", "confirmed"),
            created_at=data.get("created_at", ""),
            raw=data,
        )


@dataclass
class StayCancellation:
    id: str
    order_id: str
    refund_amount: str
    refund_currency: str
    status: str
    created_at: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StayCancellation":
        return cls(
            id=data.get("id", ""),
            order_id=data.get("order_id", ""),
            refund_amount=data.get("refund_amount", "0.00"),
            refund_currency=data.get("refund_currency", "USD"),
            status=data.get("status", "cancelled"),
            created_at=data.get("created_at", ""),
            raw=data,
        )
