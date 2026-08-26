"""
AI Travel Planner Pydantic schemas for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class GeoLocation(BaseModel):
    """Geographic location coordinates for interactive map rendering."""
    latitude: float = Field(..., description="Latitude coordinate e.g. 48.8584")
    longitude: float = Field(..., description="Longitude coordinate e.g. 2.2945")
    address: Optional[str] = Field(None, description="Physical address or neighborhood name")
    name: Optional[str] = Field(None, description="Location / Landmark name")


class ItineraryActivity(BaseModel):
    """Activity or attraction detail within a daily itinerary."""
    title: str = Field(..., description="Name of activity or attraction")
    time_slot: str = Field(..., description="Time of day e.g. 'Morning', 'Afternoon', 'Evening'")
    category: str = Field("Sightseeing", description="Category e.g. Culture, Dining, Outdoor, Sightseeing")
    description: str = Field(..., description="Detailed activity description and tips")
    geo_location: GeoLocation = Field(..., description="Geographic coordinates for map plotting")
    recommended_duration: Optional[str] = Field(None, description="Recommended visit duration e.g. '2 hours'")


class ItineraryDay(BaseModel):
    """Daily schedule breakdown."""
    day_number: int = Field(..., ge=1, le=30, description="Day index starting at 1")
    date: str = Field(..., description="Date in YYYY-MM-DD format")
    theme: str = Field(..., description="Day focus e.g. 'Historical Exploration & Seine Cruise'")
    activities: list[ItineraryActivity] = Field(..., description="List of scheduled activities for the day")


class ItineraryPlannerRequest(BaseModel):
    """AI Travel Planner search & itinerary generation request."""
    prompt: str = Field(..., min_length=3, description="Natural language travel query e.g. 'Plan a 5 day romantic trip to Paris in October'")
    origin: Optional[str] = Field(None, description="Origin airport IATA code e.g. 'ATL'")
    destination: Optional[str] = Field(None, description="Destination airport IATA code or city name e.g. 'CDG'")
    start_date: Optional[str] = Field(None, description="Departure / start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(None, description="Return / end date in YYYY-MM-DD format")
    passengers_count: int = Field(1, ge=1, le=9, description="Number of adult passengers")
    interests: Optional[list[str]] = Field(None, description="Travel interests e.g. ['Art', 'Food', 'History']")
    force_refresh: bool = Field(False, description="Set True to bypass Redis cache")


class ItineraryPlannerResponse(BaseModel):
    """Combined AI Itinerary, Geo-location Map Pins, and Top 3 Bundle Prices payload."""
    status: str = Field("success", description="Response status")
    message: str = Field("AI Itinerary and top 3 package bundles generated successfully.", description="Status message")
    destination: str = Field(..., description="Target destination city / country")
    trip_duration_days: int = Field(..., ge=1, le=30, description="Trip duration in days")
    start_date: str = Field(..., description="Trip start date YYYY-MM-DD")
    end_date: str = Field(..., description="Trip end date YYYY-MM-DD")
    map_center: GeoLocation = Field(..., description="Central coordinates for initial map viewport")
    itinerary: list[ItineraryDay] = Field(..., description="Day-by-day scheduled itinerary")
    top_3_bundles: list[dict[str, Any]] = Field(..., description="Top 3 live package bundles (Cheapest, Best Value, Luxury)")
    performance_metrics: Optional[dict[str, Any]] = Field(None, description="Execution latencies and cache metrics")
