"""
Pydantic Schemas for Jojira User Service REST APIs.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class GoogleAuthRequest(BaseModel):
    """Google OAuth Sign-In request payload from UI."""
    email: str = Field(..., description="Google account email address e.g. 'user@example.com'")
    google_user_id: Optional[str] = Field(None, description="Google OAuth sub / user ID")
    name: Optional[str] = Field(None, description="User full name e.g. 'Jane Doe'")
    given_name: Optional[str] = Field(None, description="Google given name / first name e.g. 'Jane'")
    family_name: Optional[str] = Field(None, description="Google family name / last name e.g. 'Doe'")
    first_name: Optional[str] = Field(None, description="User first name e.g. 'Jane'")
    last_name: Optional[str] = Field(None, description="User last name e.g. 'Doe'")
    phone_number: Optional[str] = Field(None, description="User phone number for booking confirmations")
    date_of_birth: Optional[str] = Field(None, description="User date of birth YYYY-MM-DD")
    picture: Optional[str] = Field(None, description="User avatar image URL")
    google_token: Optional[str] = Field(None, description="Google OAuth ID token or access token")


class UserPreferencesSchema(BaseModel):
    """User travel preferences."""
    home_airport: str = Field("ATL", description="Home airport IATA code e.g. 'ATL'")
    preferred_style: str = Field("balanced", description="Preferred travel style e.g. 'balanced', 'luxury', 'romantic'")
    preferred_budget: str = Field("moderate", description="Preferred budget tier e.g. 'cheapest', 'moderate', 'luxury'")
    seat_preference: Optional[str] = Field(None, description="Preferred flight seat e.g. 'window', 'aisle'")
    interests: list[str] = Field(default_factory=list, description="Travel interests e.g. ['Art', 'Food', 'Culture']")


class UserProfileResponse(BaseModel):
    """User profile response envelope."""
    status: str = Field("success", description="Response status")
    user_id: str = Field(..., description="User ID e.g. 'usr_948f2a'")
    email: str = Field(..., description="User email address")
    name: Optional[str] = Field(None, description="User full name")
    first_name: Optional[str] = Field(None, description="First name / Given name")
    last_name: Optional[str] = Field(None, description="Last name / Family name")
    given_name: Optional[str] = Field(None, description="Alias for first name")
    family_name: Optional[str] = Field(None, description="Alias for last name")
    phone_number: Optional[str] = Field(None, description="Phone number for travel notifications")
    date_of_birth: Optional[str] = Field(None, description="Date of birth YYYY-MM-DD")
    picture_url: Optional[str] = Field(None, description="User avatar image URL")
    google_user_id: Optional[str] = Field(None, description="Google user ID")
    last_login_at: Optional[str] = Field(None, description="Last login timestamp ISO string")
    created_at: Optional[str] = Field(None, description="Account creation timestamp ISO string")
    preferences: UserPreferencesSchema = Field(..., description="User travel preferences")



class GoogleAuthResponse(BaseModel):
    """Google Auth response payload."""
    status: str = Field("success", description="Response status")
    message: str = Field(..., description="Authentication status message")
    session_token: str = Field(..., description="JWT / Session token for authenticated calls")
    user: UserProfileResponse = Field(..., description="Synced user profile data")


class SignOutRequest(BaseModel):
    """User Sign-Out request payload."""
    user_id: Optional[str] = Field(None, description="User ID to sign out e.g. 'usr_0cba00ca3da1'")
    session_token: Optional[str] = Field(None, description="Session JWT token to revoke")


class SignOutResponse(BaseModel):
    """User Sign-Out response payload."""
    status: str = Field("success", description="Response status")
    message: str = Field("User successfully signed out.", description="Sign-out status message")



class UserPreferencesUpdateRequest(BaseModel):
    """Request schema for updating user travel preferences."""
    home_airport: Optional[str] = Field(None, description="Home airport IATA code e.g. 'ATL'")
    preferred_style: Optional[str] = Field(None, description="Preferred style e.g. 'balanced', 'luxury'")
    preferred_budget: Optional[str] = Field(None, description="Preferred budget tier e.g. 'cheapest', 'moderate', 'luxury'")
    seat_preference: Optional[str] = Field(None, description="Preferred seat choice e.g. 'window', 'aisle'")
    interests: Optional[list[str]] = Field(None, description="Travel interests e.g. ['Art', 'Dining']")


class SearchHistoryRecordRequest(BaseModel):
    """Request schema for recording a user search query."""
    prompt: str = Field(..., min_length=3, description="Search query prompt")
    destination: Optional[str] = Field(None, description="Destination city or airport code")
    origin: Optional[str] = Field(None, description="Origin airport code")
    trip_duration_days: Optional[int] = Field(None, ge=1, le=30, description="Trip duration in days")


class SearchHistoryItem(BaseModel):
    """Individual search history item."""
    id: str = Field(..., description="Search history ID e.g. 'sch_89f2a0'")
    prompt: str = Field(..., description="Search prompt")
    destination: Optional[str] = Field(None, description="Destination")
    origin: Optional[str] = Field(None, description="Origin")
    trip_duration_days: Optional[int] = Field(None, description="Trip duration in days")
    created_at: str = Field(..., description="Timestamp ISO string")


class SearchHistoryResponse(BaseModel):
    """Response containing user search history."""
    status: str = Field("success", description="Response status")
    user_id: str = Field(..., description="User ID")
    count: int = Field(..., description="Total history records returned")
    history: list[SearchHistoryItem] = Field(..., description="List of recent searches")


class SaveBookingRequest(BaseModel):
    """Request schema for saving a booked or liked itinerary."""
    itinerary_id: str = Field(..., description="Itinerary ID e.g. 'itin_opt_3cc953bf'")
    destination: str = Field(..., description="Destination e.g. 'Paris'")
    title: str = Field(..., description="Itinerary option title")
    total_price: float = Field(..., description="Total trip price in USD")
    payload: dict[str, Any] = Field(..., description="Full itinerary JSON payload")


class SaveBookingResponse(BaseModel):
    """Response schema for saving a booking/itinerary."""
    status: str = Field("success", description="Response status")
    booking_id: str = Field(..., description="Saved booking ID e.g. 'bkg_948f2a'")
    message: str = Field(..., description="Status message")
