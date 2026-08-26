"""
Cars (Car Rentals) Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from .common import PaymentInput


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
    total_offers: int = Field(..., description="Total car rental offers returned")
    offers: list[dict[str, Any]] = Field(..., description="List of car rental offer objects")


class CarBookingRequest(BaseModel):
    """Car rental booking request."""
    offer_id: str = Field(..., description="Duffel car rental offer ID e.g. 'off_car_0000B9...'")
    driver_details: dict[str, Any] = Field(..., description="Primary driver information object")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")
    payment: Optional[PaymentInput] = Field(None, description="Single payment object")
    promo_code: Optional[str] = Field(None, description="Optional promo/discount code applied")
    discount_amount: Optional[str] = Field(None, description="Optional discount amount applied")


class CarBookingResponse(BaseModel):
    """Car rental booking confirmation response."""
    status: str = Field("confirmed", description="Car rental order status")
    message: str = Field("Car rental booked successfully.", description="Status message")
    order_id: str = Field(..., description="Duffel car order ID e.g. 'ord_car_0000B9...'")
    booking_reference: str = Field(..., description="Rental confirmation / booking reference code")
    total_amount: str = Field(..., description="Total rental price amount string")
    total_currency: str = Field(..., description="Currency code e.g. USD")
    created_at: str = Field(..., description="ISO creation timestamp")
    vehicle_name: Optional[str] = Field(None, description="Rental vehicle model / description")
    supplier_name: Optional[str] = Field(None, description="Car rental supplier name")
    gross_amount: Optional[str] = Field(None, description="Gross amount before discount")
    discount_amount: Optional[str] = Field(None, description="Discount amount applied")
    promo_code: Optional[str] = Field(None, description="Promo code applied")
