"""
Stays (Hotels & Accommodations) Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from .common import PaymentInput


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
    total_results: int = Field(..., description="Total accommodation results returned")
    results: list[dict[str, Any]] = Field(..., description="List of stay search result objects")


class StayBookingRequest(BaseModel):
    """Hotel stay order booking request."""
    quote_id: str = Field(..., description="Duffel stay quote ID e.g. 'quo_0000B9...'")
    guests: list[dict[str, Any]] = Field(..., min_length=1, description="List of guest information objects")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")
    payment: Optional[PaymentInput] = Field(None, description="Single payment object")
    accommodation_id: Optional[str] = Field(None, description="Optional accommodation ID")
    promo_code: Optional[str] = Field(None, description="Optional promo/discount code applied")
    discount_amount: Optional[str] = Field(None, description="Optional discount amount applied")


class StayBookingResponse(BaseModel):
    """Hotel stay order booking response confirmation."""
    status: str = Field("confirmed", description="Stay order status e.g. confirmed")
    message: str = Field("Hotel stay booked successfully.", description="Status message")
    order_id: str = Field(..., description="Duffel stay order ID e.g. 'ord_0000B9...'")
    booking_reference: str = Field(..., description="Hotel confirmation / booking reference code")
    total_amount: str = Field(..., description="Total stay price amount string")
    total_currency: str = Field(..., description="Currency code e.g. USD")
    created_at: str = Field(..., description="ISO creation timestamp")
    accommodation_name: Optional[str] = Field(None, description="Hotel / accommodation name")
    check_in_date: Optional[str] = Field(None, description="Confirmed check-in date")
    check_out_date: Optional[str] = Field(None, description="Confirmed check-out date")
    gross_amount: Optional[str] = Field(None, description="Gross amount before discount")
    discount_amount: Optional[str] = Field(None, description="Discount amount applied")
    promo_code: Optional[str] = Field(None, description="Promo code applied")
