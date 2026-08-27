"""
AI Search Pydantic schemas for Duffel REST API.
AI Search is an intelligent router that parses natural language and delegates to services.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field

from .flights import FlightBookingRequest
from .stays import StayBookingRequest
from .cars import CarBookingRequest
from .bundles import BundleBookingRequest


class AISearchRequest(BaseModel):
    """Intelligent AI-powered travel search request."""
    prompt: str = Field(..., description="Natural language search prompt e.g. 'Flight and hotel from NYC to Paris for 5 days'")
    favorite_airline: Optional[str] = Field(None, description="Optional preferred airline name or code")
    force_refresh: bool = Field(False, description="Set true to bypass cache and query live")
    
    # Optional overrides to explicit parameters (LLM extraction can be overridden)
    selected_types: Optional[list[str]] = Field(None, description="Override extracted types: flights, hotels, cars, or combinations")
    origin: Optional[str] = Field(None, description="Override extracted origin airport/city IATA code")
    destination: Optional[str] = Field(None, description="Override extracted destination airport/city IATA code")
    departure_date: Optional[str] = Field(None, description="Override extracted departure/check-in date YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="Override extracted return/check-out date YYYY-MM-DD")
    passengers_count: Optional[int] = Field(None, ge=1, le=9, description="Override extracted passenger count")
    cabin_class: Optional[str] = Field(None, description="Override extracted cabin class: economy, business, etc.")
    rooms: Optional[int] = Field(None, ge=1, le=10, description="Override extracted hotel rooms count")
    driver_age: Optional[int] = Field(None, ge=18, le=99, description="Override extracted car rental driver age")


class AISearchResponse(BaseModel):
    """
    AI Search Response Envelope matching generic search response structure.
    
    Contains:
    - status: "success" or "error"
    - timestamp: Execution timestamp
    - meta_data: Includes search_type ('flights'|'hotels'|'cars'|'bundle'), parsed_intent, prompt, geo_location
    - data: Includes ai_summary, category_highlights, and total items list (offers or top_bundles)
    """
    status: str = Field("success", description="Response status: success or error")
    timestamp: str = Field(..., description="Execution timestamp YYYY-MM-DD HH:MM:SS")
    meta_data: dict[str, Any] = Field(..., description="Metadata section with type=ai_search, search_type, parsed_intent, and geo_location")
    data: dict[str, Any] = Field(..., description="Data section containing ai_summary, category_highlights, and items list")
    
    class Config:
        extra = "allow"



class AIBookingRequest(BaseModel):
    """
    Booking request for an AI Search result. Carries whichever type-specific booking
    payload matches the search that was performed, plus enough context (search_type/source)
    for the API to auto-route to the correct underlying book endpoint.
    """
    search_type: Optional[str] = Field(
        None, description="Explicit type to book: 'flights', 'hotels', 'cars', or 'bundle'. "
        "If omitted, inferred from 'source' or from which of flight/hotel/car/bundle payload is populated."
    )
    source: Optional[str] = Field(None, description="Echo of AISearchResponse.source e.g. 'ai_search_flights', used to infer search_type")

    flight: Optional[FlightBookingRequest] = Field(None, description="Flight booking payload (required when booking a flights-only AI search result)")
    hotel: Optional[StayBookingRequest] = Field(None, description="Hotel booking payload (required when booking a hotels-only AI search result)")
    car: Optional[CarBookingRequest] = Field(None, description="Car rental booking payload (required when booking a cars-only AI search result)")
    bundle: Optional[BundleBookingRequest] = Field(None, description="Bundle booking payload (required when booking a multi-type AI search result)")


class AIBookingResponse(BaseModel):
    """
    Booking confirmation response for an AI Search result.
    Wraps the native response of whichever service handled the booking
    (FlightBookingResponse, StayBookingResponse, CarBookingResponse, or BundleBookingResponse).
    """
    status: str = Field(..., description="Booking status e.g. confirmed")
    search_type: str = Field(..., description="Which type was booked: flights, hotels, cars, or bundle")
    source: Optional[str] = Field(None, description="Echo of the originating AI search source")

    class Config:
        extra = "allow"  # Native booking response fields (order_id, booking_reference, etc.) are merged in

