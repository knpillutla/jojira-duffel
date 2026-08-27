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
    prompt: str = Field(..., min_length=3, description="Natural language travel query e.g. '4 day romantic trip to Paris in october'")
    include_flights: bool = Field(True, description="Whether to include flights in trip plan")
    include_hotels: bool = Field(True, description="Whether to include hotel stay in trip plan")
    include_cars: bool = Field(True, description="Whether to include car rental in trip plan")
    include_attractions: bool = Field(True, description="Whether to include attractions in trip plan")
    include_activities: bool = Field(True, description="Whether to include daily activities in trip plan")
    origin: Optional[str] = Field(None, description="Origin airport IATA code e.g. 'ATL'")
    destination: Optional[str] = Field(None, description="Destination airport IATA code or city name e.g. 'Paris'")
    days: Optional[int] = Field(None, ge=1, le=30, description="Trip duration in days e.g. 4")
    trip_duration_days: Optional[int] = Field(None, ge=1, le=30, description="Alias for trip duration in days")
    style: Optional[str] = Field("balanced", description="Travel style: romantic, adventure, luxury, budget, family, balanced")
    budget: Optional[str] = Field("moderate", description="Budget tier: cheapest, moderate, luxury")
    start_date: Optional[str] = Field(None, description="Departure / start date in YYYY-MM-DD format")
    end_date: Optional[str] = Field(None, description="Return / end date in YYYY-MM-DD format")
    passengers_count: int = Field(1, ge=1, le=9, description="Number of adult passengers")
    rooms: Optional[int] = Field(None, ge=1, le=10, description="Number of hotel rooms (auto-calculated if omitted)")
    driver_age: int = Field(30, ge=18, le=99, description="Driver age for car rental")
    interests: Optional[list[str]] = Field(None, description="Travel interests e.g. ['Art', 'Food', 'History']")
    force_refresh: bool = Field(False, description="Set True to bypass Redis cache")


class ItineraryPlannerResponse(BaseModel):
    """Standard envelope AI Itinerary Planner Response payload."""
    status: str = Field("success", description="Response status")
    timestamp: str = Field(..., description="Response generation timestamp YYYY-MM-DD HH:MM:SS")
    meta_data: dict[str, Any] = Field(..., description="Metadata envelope with search parameters, duration, occupancy, and map center")
    data: dict[str, Any] = Field(..., description="Data envelope with ai_summary, trip_summary, category_highlights, map_pins, daily_itinerary, top_3_bundles")

    class Config:
        extra = "allow"


class ItineraryLikeRequest(BaseModel):
    """Request schema for liking, upvoting, or downvoting an itinerary."""
    itinerary_id: str = Field(..., description="Itinerary ID e.g. 'itin_89f2a0'")
    liked: bool = Field(..., description="True for upvote/like, False for downvote/dislike")
    feedback_notes: Optional[str] = Field(None, description="Optional user feedback notes or reason for rating")


class ItineraryLikeResponse(BaseModel):
    """Response schema for itinerary feedback / like action."""
    status: str = Field("success", description="Response status")
    message: str = Field(..., description="Status message explaining action taken")
    itinerary_id: str = Field(..., description="Target itinerary ID")
    liked: bool = Field(..., description="Whether itinerary was liked or downvoted")
    deleted_from_db: bool = Field(False, description="True if itinerary was purged from database and cache due to downvote")


