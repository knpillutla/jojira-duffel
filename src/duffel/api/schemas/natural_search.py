"""
Natural Language Search Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class NaturalSearchRequest(BaseModel):
    """Unified natural language travel search request for Flights, Hotels, Cars, and Attractions."""
    prompt: str = Field(..., description="Natural language search prompt string e.g. 'Flight and hotel in Paris for Oct 1'")
    favorite_airline: Optional[str] = Field(None, description="Optional preferred airline name or code")
    force_refresh: bool = Field(False, description="Set true to bypass cache and query live")
    selected_types: Optional[list[str]] = Field(None, description="Explicit override for search categories: flights, hotels, cars, attractions")
    origin: Optional[str] = Field(None, description="Explicit origin airport/city IATA code")
    destination: Optional[str] = Field(None, description="Explicit destination airport/city IATA code")
    departure_date: Optional[str] = Field(None, description="Explicit departure/check-in date YYYY-MM-DD")
    return_date: Optional[str] = Field(None, description="Explicit return/check-out date YYYY-MM-DD")
    passengers_count: Optional[int] = Field(None, ge=1, le=9, description="Number of passengers")
    cabin_class: Optional[str] = Field(None, description="Cabin class: economy, business, etc.")
    rooms: Optional[int] = Field(None, ge=1, le=10, description="Hotel rooms count")
    driver_age: Optional[int] = Field(None, ge=18, le=99, description="Car rental driver age")


class NaturalSearchMeta(BaseModel):
    """Metadata detailing search classification, selected domain types, bundle details, and TTL expiry."""
    search_type: str = Field(..., description="Search classification type: flights, hotels, cars, attractions, or bundle")
    selected_types: list[str] = Field(..., description="List of extracted/selected domain types")
    is_bundle: bool = Field(..., description="True if multiple types are combined into a package bundle")
    bundle_for: str = Field(..., description="Human-readable title indicating what this search/bundle is for")
    bundle_description: str = Field(..., description="Description of included components and savings/purpose")
    prompt: str = Field(..., description="Original search prompt string")
    ttl_seconds: int = Field(3600, description="Seconds remaining until response expires, calculated from earliest offer expiry date")
    expires_at: str = Field(..., description="ISO 8601 timestamp string indicating when response expires for browser storage")
    timestamp: str = Field(..., description="Execution timestamp string")




class NaturalSearchResponse(BaseModel):
    """Unified natural search API response."""
    status: str = Field("success", description="Status of search response")
    timestamp: str = Field(..., description="Response execution timestamp")
    search_type: str = Field(..., description="Top-level search type indicator: flights, hotels, cars, attractions, or bundle")
    meta: NaturalSearchMeta = Field(..., description="Metadata block indicating domain search type and parameters")
    search_params: dict[str, Any] = Field(..., description="Resolved search parameter criteria")
    category_highlights: dict[str, Any] = Field(..., description="Category highlights dict tailored to search type")
    total_results: int = Field(..., description="Total search result items returned")
    results: list[dict[str, Any]] = Field(..., description="Search results or package bundles")
    output_file: Optional[str] = Field(None, description="Path to saved JSON search report file")
