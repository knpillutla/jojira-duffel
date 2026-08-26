"""
Bundled Travel Package Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional, Union
from pydantic import BaseModel, Field

from .common import PassengerInput, PaymentInput
from .stays import GuestInput


class BundleSearchRequest(BaseModel):
    """Bundled travel search request for Flights + Hotels + Car Rentals."""
    origin: str = Field(..., description="Origin Airport IATA code e.g. 'ATL'")
    destination: str = Field(..., description="Destination Airport IATA code e.g. 'CDG'")
    departure_date: str = Field(..., description="Departure date in YYYY-MM-DD format")
    return_date: str = Field(..., description="Return date in YYYY-MM-DD format")
    passengers_count: int = Field(1, ge=1, le=9, description="Number of adult passengers")
    cabin_class: str = Field("economy", description="Cabin class: economy, business, etc.")
    rooms: int = Field(1, ge=1, le=10, description="Number of hotel rooms requested")
    driver_age: int = Field(30, ge=18, le=99, description="Driver age for car rental")
    bundle_types: Union[list[str], str] = Field(
        "all",
        description="Which components to include: a list containing any of 'flights', 'hotels', 'cars', "
        "or the string 'all' to include every component.",
    )
    force_refresh: bool = Field(False, description="Set true to bypass cache and query live")


class BundleItem(BaseModel):
    """Summarized bundled package offer item."""
    bundle_id: str = Field(..., description="Unique bundle ID e.g. 'bnd_0001'")
    total_package_price: float = Field(..., description="Combined package total price with 5% bundle savings")
    individual_price_sum: float = Field(..., description="Sum of individual flight, hotel, and car prices")
    bundle_savings: float = Field(..., description="Total discount savings amount string/float")
    currency: str = Field("USD", description="Currency code e.g. USD")
    flight_offer: dict[str, Any] = Field(..., description="Flight offer details summary")
    hotel_stay: dict[str, Any] = Field(..., description="Hotel stay result details summary")
    car_rental: dict[str, Any] = Field(..., description="Car rental offer details summary")


class BundleCategoryHighlights(BaseModel):
    """Category highlights for travel package bundles."""
    overall_cheapest: dict[str, Any]
    nonstop_flight_bundle: dict[str, Any]
    best_value_bundle: dict[str, Any]
    luxury_bundle: dict[str, Any]


class BundleSearchResponse(BaseModel):
    """Bundled travel search response."""
    status: str = Field("success", description="Response status")
    timestamp: str = Field(..., description="Search execution timestamp")
    meta_data: dict[str, Any] = Field(..., description="Metadata section with type=bundles, search_params, and geo_location")
    data: dict[str, Any] = Field(..., description="Data section containing top_bundles, total_bundles_found, category_highlights, metrics")



class BundleBookingRequest(BaseModel):
    """Bundled travel package booking request."""
    flight_offer_id: str = Field(..., description="Flight offer ID")
    stay_quote_id: str = Field(..., description="Stay quote ID")
    car_offer_id: str = Field(..., description="Car rental offer ID")
    passengers: list[PassengerInput] = Field(..., min_length=1, description="List of passengers")
    guests: list[dict[str, Any]] = Field(..., min_length=1, description="List of hotel guests")
    driver_details: dict[str, Any] = Field(..., description="Driver details object")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")
    payment: Optional[PaymentInput] = Field(None, description="Single payment object")
    promo_code: Optional[str] = Field(None, description="Optional promo/discount code applied")
    discount_amount: Optional[str] = Field(None, description="Optional discount amount applied")


class BundleBookingResponse(BaseModel):
    """Bundled travel package booking confirmation response envelope."""
    status: str = Field("confirmed", description="Bundle order status")
    timestamp: str = Field(..., description="Booking execution timestamp")
    meta_data: dict[str, Any] = Field(..., description="Booking metadata section with input details, type=bundles, promo_code, and geo_location")
    data: dict[str, Any] = Field(..., description="Booking confirmation details section containing bundle_order_id, component order IDs, and totals")

