"""
Flight data models for search, offer selection, order creation and cancellation.
"""

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
from .common import CabinClass, MoneyAmount, Passenger


@dataclass
class FlightSliceQuery:
    origin: str  # IATA code, airport ID, or city code e.g. "LHR"
    destination: str  # IATA code e.g. "JFK"
    departure_date: str  # YYYY-MM-DD

    def to_dict(self) -> dict[str, Any]:
        return {
            "origin": self.origin,
            "destination": self.destination,
            "departure_date": self.departure_date,
        }


@dataclass
class FlightSearchQuery:
    slices: list[FlightSliceQuery]
    passengers: list[Passenger]
    cabin_class: CabinClass = CabinClass.ECONOMY
    max_connections: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        res: dict[str, Any] = {
            "slices": [s.to_dict() for s in self.slices],
            "passengers": [p.to_dict() for p in self.passengers],
            "cabin_class": self.cabin_class.value if isinstance(self.cabin_class, CabinClass) else self.cabin_class,
        }
        if self.max_connections is not None:
            res["max_connections"] = self.max_connections
        return res


@dataclass
class FlightSegment:
    id: str
    origin: dict[str, Any]
    destination: dict[str, Any]
    departing_at: str
    arriving_at: str
    marketing_carrier: dict[str, Any]
    operating_carrier: dict[str, Any]
    flight_number: str
    aircraft: Optional[dict[str, Any]] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlightSegment":
        return cls(
            id=data.get("id", ""),
            origin=data.get("origin", {}),
            destination=data.get("destination", {}),
            departing_at=data.get("departing_at", ""),
            arriving_at=data.get("arriving_at", ""),
            marketing_carrier=data.get("marketing_carrier", {}),
            operating_carrier=data.get("operating_carrier", {}),
            flight_number=data.get("marketing_carrier_flight_number", data.get("flight_number", "")),
            aircraft=data.get("aircraft"),
        )


@dataclass
class FlightSlice:
    id: str
    origin: dict[str, Any]
    destination: dict[str, Any]
    duration: Optional[str]
    segments: list[FlightSegment]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlightSlice":
        segments = [FlightSegment.from_dict(seg) for seg in data.get("segments", [])]
        return cls(
            id=data.get("id", ""),
            origin=data.get("origin", {}),
            destination=data.get("destination", {}),
            duration=data.get("duration"),
            segments=segments,
        )


@dataclass
class FlightOffer:
    id: str
    total_amount: str
    total_currency: str
    tax_amount: Optional[str]
    tax_currency: Optional[str]
    owner: dict[str, Any]
    slices: list[FlightSlice]
    passengers: list[dict[str, Any]]
    expires_at: str
    created_at: str
    payment_requirements: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlightOffer":
        slices = [FlightSlice.from_dict(s) for s in data.get("slices", [])]
        return cls(
            id=data.get("id", ""),
            total_amount=data.get("total_amount", "0.00"),
            total_currency=data.get("total_currency", "USD"),
            tax_amount=data.get("tax_amount"),
            tax_currency=data.get("tax_currency"),
            owner=data.get("owner", {}),
            slices=slices,
            passengers=data.get("passengers", []),
            expires_at=data.get("expires_at", ""),
            created_at=data.get("created_at", ""),
            payment_requirements=data.get("payment_requirements", {}),
            raw=data,
        )


@dataclass
class FlightOrder:
    id: str
    booking_reference: str
    total_amount: str
    total_currency: str
    passengers: list[dict[str, Any]]
    slices: list[FlightSlice]
    created_at: str
    live_mode: bool
    status: str
    payment_status: Optional[dict[str, Any]] = field(default_factory=dict)
    documents: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlightOrder":
        slices = [FlightSlice.from_dict(s) for s in data.get("slices", [])]
        return cls(
            id=data.get("id", ""),
            booking_reference=data.get("booking_reference", ""),
            total_amount=data.get("total_amount", "0.00"),
            total_currency=data.get("total_currency", "USD"),
            passengers=data.get("passengers", []),
            slices=slices,
            created_at=data.get("created_at", ""),
            live_mode=data.get("live_mode", False),
            status=data.get("status", "confirmed"),
            payment_status=data.get("payment_status", {}),
            documents=data.get("documents", []),
            raw=data,
        )


@dataclass
class FlightCancellation:
    id: str
    order_id: str
    refund_amount: str
    refund_currency: str
    status: str
    created_at: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FlightCancellation":
        return cls(
            id=data.get("id", ""),
            order_id=data.get("order_id", ""),
            refund_amount=data.get("refund_amount", "0.00"),
            refund_currency=data.get("refund_currency", "USD"),
            status=data.get("status", "pending"),
            created_at=data.get("created_at", ""),
            raw=data,
        )


class OfferList(list):
    """List subclass that supports attaching category highlights and metadata."""

    def __init__(self, iterable=(), category_highlights=None):
        super().__init__(iterable)
        self.category_highlights = category_highlights or {}

