"""
Cars (Car Rentals) Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from .common import PassengerInput, PaymentInput


class DriverInput(BaseModel):
    """Driver details for car rental booking."""
    given_name: str = Field(..., description="Driver given / first name")
    family_name: str = Field(..., description="Driver family / last name")
    email: str = Field(..., description="Contact email address")
    phone_number: Optional[str] = Field(None, description="Contact phone number")
    age: int = Field(30, ge=18, le=99, description="Driver age in years")


class CarSearchRequest(BaseModel):
    """Car rental search request."""
    pickup_location: str = Field(..., description="Pickup location IATA code or city name e.g. 'LHR'")
    dropoff_location: str = Field(..., description="Dropoff location IATA code or city name e.g. 'LHR'")
    pickup_datetime: str = Field(..., description="Pickup datetime in ISO format e.g. '2026-10-01T10:00:00Z'")
    dropoff_datetime: str = Field(..., description="Dropoff datetime in ISO format e.g. '2026-10-05T10:00:00Z'")
    driver_age: int = Field(30, ge=18, le=99, description="Driver age in years")


class CarSearchResponse(BaseModel):
    """Car rental search response."""
    status: str = Field("success", description="Response status")
    timestamp: str = Field(..., description="Search execution timestamp")
    meta_data: dict[str, Any] = Field(..., description="Search metadata section with input parameters, type=cars, and geo_location")
    data: dict[str, Any] = Field(..., description="Data section containing total_offers and offers list")


class CarBookingRequest(BaseModel):
    """Car rental booking request matching FlightBookingRequest workflow."""
    offer_id: Optional[str] = Field(None, description="Duffel car rental offer ID e.g. 'off_car_0000B9...'")
    selected_offers: Optional[list[str]] = Field(None, description="List of car offer IDs (e.g. ['off_car_0000B9...'])")
    passengers: Optional[list[PassengerInput]] = Field(None, description="List of passenger detail objects (same schema as flight booking)")
    driver_details: Optional[dict[str, Any]] = Field(None, description="Primary driver information object")
    driver: Optional[dict[str, Any]] = Field(None, description="Alias for driver_details")
    payment: Optional[PaymentInput] = Field(None, description="Single payment object (type: 'balance' or 'card')")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")
    idempotency_key: Optional[str] = Field(None, description="Optional Duffel-Idempotency-Key header for safe request retries")
    expected_price: Optional[str] = Field(None, description="Expected price user agreed to e.g. '250.00'. Raises 409 error if live price changed.")
    allow_price_change: bool = Field(False, description="Set True to accept supplier live price changes automatically")
    promo_code: Optional[str] = Field(None, description="Optional promo/discount code applied")
    discount_amount: Optional[str] = Field(None, description="Optional discount amount applied")




class CarBookingResponse(BaseModel):
    """Car rental booking confirmation response envelope."""
    status: str = Field("confirmed", description="Car rental order status")
    timestamp: str = Field(..., description="Booking execution timestamp")
    meta_data: dict[str, Any] = Field(..., description="Booking metadata section with input details, type=cars, promo_code, and geo_location")
    data: dict[str, Any] = Field(..., description="Booking confirmation details section containing order_id, booking_reference, amounts, and vehicle info")


