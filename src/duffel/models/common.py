"""
Common data models used across Flights, Stays, and Cars modules.
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Optional


class CabinClass(str, Enum):
    ECONOMY = "economy"
    PREMIUM_ECONOMY = "premium_economy"
    BUSINESS = "business"
    FIRST = "first"


class PassengerType(str, Enum):
    ADULT = "adult"
    CHILD = "child"
    INFANT_WITHOUT_SEAT = "infant_without_seat"


@dataclass
class MoneyAmount:
    amount: str
    currency: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Location:
    iata_code: Optional[str] = None
    city_name: Optional[str] = None
    country_name: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    address: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class Passenger:
    id: Optional[str] = None
    type: PassengerType = PassengerType.ADULT
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    born_on: Optional[str] = None  # YYYY-MM-DD
    email: Optional[str] = None
    phone_number: Optional[str] = None
    title: Optional[str] = None
    gender: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d = {"type": self.type.value if isinstance(self.type, PassengerType) else self.type}
        if self.id:
            d["id"] = self.id
        if self.given_name:
            d["given_name"] = self.given_name
        if self.family_name:
            d["family_name"] = self.family_name
        if self.born_on:
            d["born_on"] = self.born_on
        if self.email:
            d["email"] = self.email
        if self.phone_number:
            d["phone_number"] = self.phone_number
        if self.title:
            d["title"] = self.title
        if self.gender:
            d["gender"] = self.gender
        return d


@dataclass
class Payment:
    type: str = "balance"  # balance, card, or arc_bsp
    currency: str = "USD"
    amount: str = "0.00"

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "currency": self.currency,
            "amount": self.amount,
        }
