"""
Pydantic schemas and Data Transfer Objects for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class PassengerInput(BaseModel):
    """Passenger details for flight search and order booking."""
    type: str = Field("adult", description="Passenger type: adult, child, infant_without_seat")
    first_name: Optional[str] = Field(None, description="Given / First Name")
    last_name: Optional[str] = Field(None, description="Family / Last Name")
    email: Optional[str] = Field(None, description="Contact Email Address")
    phone_number: Optional[str] = Field(None, description="Phone Number with country code")
    born_on: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")
    title: Optional[str] = Field("mr", description="Title: mr, ms, mrs, dr")
    gender: Optional[str] = Field("m", description="Gender: m, f")


class PaymentInput(BaseModel):
    """Payment details for Duffel order creation."""
    type: str = Field("balance", description="Payment method: balance, card, arc_bsp_one_step")
    currency: str = Field("USD", description="Payment currency code")
    amount: str = Field(..., description="Total payment amount string e.g. '613.33'")


class OptimizedFlightSearchRequest(BaseModel):
    """Flexible multi-day flight search optimization request."""
    prompt: Optional[str] = Field(None, description="Natural-language flight request")
    origin: Optional[str] = Field(None, description="Origin Airport IATA code e.g. LHR")
    destination: Optional[str] = Field(None, description="Destination Airport IATA code e.g. JFK")
    target_date: Optional[str] = Field(None, description="Target departure date in YYYY-MM-DD format")
    target_return_date: Optional[str] = Field(None, description="Target return date in YYYY-MM-DD format")
    min_duration_days: int = Field(4, ge=1, le=30, description="Minimum trip duration in days")
    max_duration_days: int = Field(7, ge=1, le=30, description="Maximum trip duration in days")
    flex_days: int = Field(0, ge=0, le=7, description="Flexible departure/return window +/- days")
    passengers_count: int = Field(1, ge=1, le=9, description="Number of adult passengers")
    cabin_class: str = Field("economy", description="Cabin class: economy, premium_economy, business, first")
    favorite_airline: Optional[str] = Field(None, description="Preferred favorite airline (e.g. 'Virgin Atlantic', 'BA')")
    force_refresh: bool = Field(False, description="Set true to bypass cache and query Duffel live")


class NaturalLanguageFlightSearchRequest(BaseModel):
    """Natural-language flight search request resolved by the configured Gemini model."""
    prompt: str = Field(..., min_length=1, description="Natural-language flight request")
    favorite_airline: Optional[str] = Field(None, description="Preferred favorite airline")
    force_refresh: bool = Field(False, description="Set true to bypass cache and query Duffel live")


class FlightBookingRequest(BaseModel):
    """Flight offer booking request."""
    offer_id: str = Field(..., description="Duffel Flight Offer ID to book e.g. 'off_0000B9...'")
    passengers: list[PassengerInput] = Field(..., min_items=1, description="List of passenger detail objects")
    payment: Optional[PaymentInput] = Field(None, description="Payment object (defaults to balance payment)")


class HealthCheckResponse(BaseModel):
    """System health check response status."""
    status: str
    version: str
    duffel_token_configured: bool
    redis_cache_enabled: bool
    redis_cache_status: str


class AnalyzeQueriesResponse(BaseModel):
    """Pre-analysis candidate queries summary."""
    is_tier1_hit: bool
    tier1_cache_key: Optional[str] = None
    total_batches: int
    duffel_api_calls: int
    redis_cache_hits: int
    aggregated_cache_hits: int
    individual_cache_hits: int
    details: list[Any]


class FlightOfferSummary(BaseModel):
    """Summarized flight offer details."""
    offer_id: str
    price: str
    total_amount: float
    currency: str
    airline: str
    max_stops: int
    duration: str
    duration_minutes: Optional[int] = None


class OptimizedFlightSearchResponse(BaseModel):
    """Comprehensive flexible multi-day flight search response payload."""
    timestamp: str
    search_prompt: str = ""
    search_params: dict[str, Any]
    category_highlights: dict[str, Any]
    total_offers_found: int
    cheapest_non_stop_offers: list[dict[str, Any]]
    shortest_non_stop_offers: list[dict[str, Any]]
    top_offers: list[dict[str, Any]]
    performance_metrics: dict[str, Any]
    cache_metrics: dict[str, Any]
    output_file: str


class FlightBookingResponse(BaseModel):
    """Flight booking order confirmation response."""
    status: str
    message: str
    order_id: str
    booking_reference: str
    total_amount: str
    total_currency: str
    created_at: str
    passengers: list[dict[str, Any]]
    slices: list[dict[str, Any]]
