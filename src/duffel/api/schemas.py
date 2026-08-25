"""
Pydantic schemas and Data Transfer Objects for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class PassengerInput(BaseModel):
    """Passenger details for flight search and order booking as expected by Duffel API."""
    id: Optional[str] = Field(None, description="Passenger ID from offer (e.g. 'pas_00001')")
    type: str = Field("adult", description="Passenger type: adult, child, infant_without_seat")
    given_name: Optional[str] = Field(None, description="Given / First Name")
    first_name: Optional[str] = Field(None, description="Alias for given_name")
    family_name: Optional[str] = Field(None, description="Family / Last Name")
    last_name: Optional[str] = Field(None, description="Alias for family_name")
    email: Optional[str] = Field(None, description="Contact Email Address")
    phone_number: Optional[str] = Field(None, description="Phone Number with country code")
    born_on: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")
    title: Optional[str] = Field("mr", description="Title: mr, ms, mrs, dr")
    gender: Optional[str] = Field("m", description="Gender: m, f")


class PaymentInput(BaseModel):
    """Payment details for Duffel order creation supporting all Duffel payment methods."""
    type: str = Field("balance", description="Payment method: balance, card, arc_bsp_one_step, customer_card, bank_transfer, instant_bank_transfer")
    currency: Optional[str] = Field("USD", description="Payment currency code e.g. USD")
    amount: Optional[str] = Field(None, description="Total payment amount string e.g. '613.33'")
    card_token: Optional[str] = Field(None, description="Card token if paying via credit card")
    token: Optional[str] = Field(None, description="Alias for card_token or Duffel Payments token")
    card_id: Optional[str] = Field(None, description="Saved Card ID for card payment")
    customer_card_id: Optional[str] = Field(None, description="Saved customer card ID on file")
    payment_method_id: Optional[str] = Field(None, description="Generic payment method ID or token")


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
    type: str = Field("instant", description="Order type: 'instant' or 'hold'")
    passengers: list[PassengerInput] = Field(..., min_length=1, description="List of passenger detail objects")
    payment: Optional[PaymentInput] = Field(None, description="Single payment object")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")
    idempotency_key: Optional[str] = Field(None, description="Optional Duffel-Idempotency-Key header for safe request retries")
    expected_price: Optional[str] = Field(None, description="Expected price user agreed to e.g. '47.96'. Raises 409 error if live price changed.")
    allow_price_change: bool = Field(False, description="Set True to accept airline live price changes automatically")


class HealthCheckResponse(BaseModel):
    """System health check response status."""
    status: str
    service: str = Field("Jojira Duffel Integration API", description="Service name")
    version: str
    timestamp: str = Field(..., description="Current system timestamp")
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


class PaymentMethodOption(BaseModel):
    """Supported Duffel payment method option item."""
    id: str = Field(..., description="Payment method identifier e.g. 'balance', 'card', 'hold'")
    name: str = Field(..., description="Human-readable payment method display name")
    description: str = Field(..., description="Explanation of payment method")
    category: str = Field(..., description="Category: account, card, agency, bank, reservation")
    requires_card_details: bool = Field(False, description="Whether card token or credit card details are required")
    requires_customer_card_id: bool = Field(False, description="Whether customer card ID is required")
    is_hold_option: bool = Field(False, description="Whether this option reserves seats without immediate payment")


class PaymentMethodsResponse(BaseModel):
    """List of all Duffel-supported payment methods response."""
    status: str = Field("ok", description="Response status")
    default_method: str = Field("balance", description="Default recommended payment method")
    supported_payment_methods: list[PaymentMethodOption] = Field(..., description="Array of supported payment methods")


class ComponentClientKeyResponse(BaseModel):
    """Response payload containing generated Duffel Client Component Key for front-end Card Form."""
    status: str = Field("ok", description="Response status")
    client_key: str = Field(..., description="Short-lived Duffel Component Client Key JWT token")
    component_client_key: Optional[str] = Field(None, description="Alias for client_key")
    live_mode: bool = Field(True, description="Whether key is in live mode vs test mode")
    created_at: Optional[str] = Field(None, description="ISO timestamp of key creation")


class ApiEndpointHelp(BaseModel):
    """Help metadata for an API endpoint."""
    name: str = Field(..., description="API endpoint name / summary")
    method: str = Field(..., description="HTTP Method e.g. GET, POST")
    path: str = Field(..., description="API endpoint path")
    url: str = Field(..., description="Full API endpoint URL e.g. http://localhost:8000/api/v1/flights/search")
    description: str = Field(..., description="Description of endpoint functionality")
    request_schema: Optional[Any] = Field(None, description="Input request JSON schema or query parameters")
    response_schema: Optional[Any] = Field(None, description="Output response JSON schema")


class ApiHelpResponse(BaseModel):
    """Complete API help directory response."""
    service: str = Field(..., description="Service title")
    version: str = Field(..., description="API version")
    base_url: str = Field(..., description="Server base URL e.g. http://localhost:8000")
    interactive_docs_url: str = Field(..., description="Interactive OpenAPI docs URL")
    total_endpoints: int = Field(..., description="Total number of registered endpoints")
    endpoints: list[ApiEndpointHelp] = Field(..., description="List of all API endpoint specifications")
