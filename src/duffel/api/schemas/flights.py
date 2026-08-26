"""
Flight Pydantic schemas and Data Transfer Objects for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from .common import PassengerInput, PaymentInput


class StandardFlightSearchRequest(BaseModel):
    """Standard flight search request for exact departure and optional return dates."""
    prompt: Optional[str] = Field(None, description="Natural-language flight request")
    origin: Optional[str] = Field(None, description="Origin Airport IATA code e.g. LHR or ATL")
    destination: Optional[str] = Field(None, description="Destination Airport IATA code e.g. JFK or CDG")
    departure_date: Optional[str] = Field(None, description="Exact departure date in YYYY-MM-DD format (alias for target_date)")
    target_date: Optional[str] = Field(None, description="Exact departure date in YYYY-MM-DD format")
    return_date: Optional[str] = Field(None, description="Exact return date in YYYY-MM-DD format for round-trip (alias for target_return_date)")
    target_return_date: Optional[str] = Field(None, description="Exact return date in YYYY-MM-DD format")
    passengers_count: int = Field(1, ge=1, le=9, description="Number of adult passengers")
    cabin_class: str = Field("economy", description="Cabin class: economy, premium_economy, business, first")
    max_connections: Optional[int] = Field(None, description="Maximum connections / stops allowed")
    favorite_airline: Optional[str] = Field(None, description="Preferred favorite airline (e.g. 'Virgin Atlantic', 'BA')")
    force_refresh: bool = Field(False, description="Set true to bypass cache and query Duffel live")


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
    max_connections: Optional[int] = Field(None, description="Maximum connections / stops allowed")
    favorite_airline: Optional[str] = Field(None, description="Preferred favorite airline (e.g. 'Virgin Atlantic', 'BA')")
    force_refresh: bool = Field(False, description="Set true to bypass cache and query Duffel live")


class NaturalLanguageFlightSearchRequest(BaseModel):
    """Natural-language flight search request resolved by the configured Gemini model."""
    prompt: str = Field(..., min_length=1, description="Natural-language flight request")
    favorite_airline: Optional[str] = Field(None, description="Preferred favorite airline")
    force_refresh: bool = Field(False, description="Set true to bypass cache and query Duffel live")


class FlightBookingRequest(BaseModel):
    """Flight offer booking request matching Duffel POST /air/orders schema."""
    offer_id: Optional[str] = Field(None, description="Duffel Flight Offer ID to book e.g. 'off_0000B9...'")
    selected_offers: Optional[list[str]] = Field(None, description="List of Duffel Flight Offer IDs (e.g. ['off_0000B9...'])")
    type: Optional[str] = Field(None, description="Order type: 'hold' (Strategy A, default if offer supports hold) or 'instant' (Strategy B, fallback for budget airlines)")
    passengers: list[PassengerInput] = Field(..., min_length=1, description="List of passenger detail objects")
    payment: Optional[PaymentInput] = Field(None, description="Single payment object")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")
    idempotency_key: Optional[str] = Field(None, description="Optional Duffel-Idempotency-Key header for safe request retries")
    expected_price: Optional[str] = Field(None, description="Expected price user agreed to e.g. '47.96'. Raises 409 error if live price changed.")
    allow_price_change: bool = Field(False, description="Set True to accept airline live price changes automatically")
    promo_code: Optional[str] = Field(None, description="Optional promo/discount code applied")
    discount_amount: Optional[str] = Field(None, description="Optional discount amount applied")


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
    origin: Optional[str] = None
    origin_name: Optional[str] = None
    origin_code: Optional[str] = None
    destination: Optional[str] = None
    destination_name: Optional[str] = None
    destination_code: Optional[str] = None
    max_stops: int
    legs: Optional[str] = None
    leg_names: Optional[str] = None
    leg_codes: Optional[str] = None
    duration: str
    duration_minutes: Optional[int] = None
    duration_hours: Optional[float] = None
    departure_at: Optional[str] = None
    departure_date: Optional[str] = None
    departure_time: Optional[str] = None
    arrival_at: Optional[str] = None
    arrival_date: Optional[str] = None
    arrival_time: Optional[str] = None
    return_departure_at: Optional[str] = None
    return_departure_date: Optional[str] = None
    return_departure_time: Optional[str] = None
    return_arrival_at: Optional[str] = None
    return_arrival_date: Optional[str] = None
    return_arrival_time: Optional[str] = None
    slice_details: Optional[list[dict[str, Any]]] = None


class OptimizedFlightSearchResponse(BaseModel):
    """Comprehensive flexible multi-day flight search response payload."""
    timestamp: str
    search_prompt: str = ""
    search_params: dict[str, Any]
    category_highlights: dict[str, Any]
    total_offers_found: int
    lowest_non_stop_offers: list[dict[str, Any]]
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
    gross_amount: Optional[str] = None
    discount_amount: Optional[str] = None
    promo_code: Optional[str] = None
