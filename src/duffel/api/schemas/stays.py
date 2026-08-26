"""
Stays (Hotels & Accommodations) Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from .common import PassengerInput, PaymentInput


class GuestInput(BaseModel):
    """Guest details for stay / hotel booking."""
    type: str = Field("adult", description="Guest type e.g. adult, child")
    given_name: Optional[str] = Field(None, description="Guest given / first name")
    family_name: Optional[str] = Field(None, description="Guest family / last name")
    email: Optional[str] = Field(None, description="Contact email address")
    age: Optional[int] = Field(None, description="Age of guest")


class StaySearchRequest(BaseModel):
    """Hotel availability search request."""
    check_in_date: str = Field(..., description="Check-in date in YYYY-MM-DD format")
    check_out_date: str = Field(..., description="Check-out date in YYYY-MM-DD format")
    rooms: int = Field(1, ge=1, le=10, description="Number of rooms requested")
    guests: Optional[list[dict[str, Any]]] = Field(
        None, 
        description="List of guest specification objects with 'type' field (e.g., [{'type': 'adult'}, {'type': 'child', 'age': 8}])"
    )
    guests_count: Optional[int] = Field(
        None,
        ge=1,
        le=9,
        description="Alternative: number of adult guests (will create list of adults). Use either 'guests' OR 'guests_count'"
    )
    location: Optional[dict[str, Any]] = Field(
        None, 
        description="Location filter: {'place_id': 'string'} OR {'geographic_coordinates': {'latitude': float, 'longitude': float}}"
    )
    location_string: Optional[str] = Field(
        None,
        description="Alternative: location as place name/city (e.g., 'delhi'). Will be converted to place_id"
    )
    accommodation_ids: Optional[list[str]] = Field(None, description="Optional list of specific Duffel accommodation IDs")


class StaySearchResponse(BaseModel):
    """Hotel availability search response."""
    status: str = Field("success", description="Response status")
    timestamp: str = Field(..., description="Search execution timestamp")
    meta_data: dict[str, Any] = Field(..., description="Search metadata section with input parameters, type=stays, and geo_location")
    data: dict[str, Any] = Field(..., description="Data section containing total_results and results list")


class StayBookingRequest(BaseModel):
    """Hotel stay order booking request matching Flights and Cars workflow."""
    quote_id: Optional[str] = Field(None, description="Duffel stay quote ID e.g. 'quo_0000B9...'")
    offer_id: Optional[str] = Field(None, description="Alias for quote_id")
    selected_offers: Optional[list[str]] = Field(None, description="List containing stay quote IDs (e.g. ['quo_0000B9...'])")
    guests: Optional[list[dict[str, Any]]] = Field(None, description="List of guest information objects")
    passengers: Optional[list[PassengerInput]] = Field(None, description="List of passenger detail objects (same schema as flights & cars booking)")
    payment: Optional[PaymentInput] = Field(None, description="Single payment object (type: 'balance' or 'card')")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")
    accommodation_id: Optional[str] = Field(None, description="Optional accommodation ID")
    idempotency_key: Optional[str] = Field(None, description="Optional Duffel-Idempotency-Key header for safe request retries")
    expected_price: Optional[str] = Field(None, description="Expected price user agreed to e.g. '600.00'. Raises 409 error if live price changed.")
    allow_price_change: bool = Field(False, description="Set True to accept supplier live price changes automatically")
    promo_code: Optional[str] = Field(None, description="Optional promo/discount code applied")
    discount_amount: Optional[str] = Field(None, description="Optional discount amount applied")


class StayBookingResponse(BaseModel):
    """Hotel stay order booking response confirmation envelope."""
    status: str = Field("confirmed", description="Stay order status e.g. confirmed")
    timestamp: str = Field(..., description="Booking execution timestamp")
    meta_data: dict[str, Any] = Field(..., description="Booking metadata section with input details, type=stays, promo_code, and geo_location")
    data: dict[str, Any] = Field(..., description="Booking confirmation details section containing order_id, booking_reference, amounts, and hotel info")


