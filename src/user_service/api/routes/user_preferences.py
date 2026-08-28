"""
Dedicated REST Controller for User Preferences & LLM AI Profiler.
Manages user travel preferences (home airport, hotel type, hotel rating, user rating, ui layout, airline, airline class, trip interests)
and triggers background LLM evaluation from search and booking history.
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, BackgroundTasks, status
from pydantic import BaseModel, Field

from ...db.user_dao import UserDAO
from ...config import UserServiceConfig
from ...services.preference_profiler import UserPreferenceProfiler

router = APIRouter(prefix="/users", tags=["User Preferences"])


class UserPreferencesModel(BaseModel):
    user_id: str
    home_airport: Optional[str] = Field("ATL", description="Home airport IATA code e.g. 'ATL'")
    preferred_style: Optional[str] = Field("balanced", description="Preferred travel style e.g. 'balanced', 'luxury'")
    preferred_budget: Optional[str] = Field("moderate", description="Preferred budget tier e.g. 'moderate', 'luxury'")
    seat_preference: Optional[str] = Field("window", description="Preferred seating e.g. 'window', 'aisle'")
    hotel_type: Optional[str] = Field("resort", description="Preferred hotel style e.g. 'resort', 'boutique', 'luxury'")
    hotel_rating: Optional[str] = Field("4-star", description="Preferred star rating e.g. '4-star', '5-star'")
    hotel_user_rating: Optional[str] = Field("8.5+", description="Preferred min user rating e.g. '8.5+'")
    ui_layout: Optional[str] = Field("grid", description="UI data pane layout e.g. 'grid', 'compact', 'split'")
    airline: Optional[str] = Field("Delta", description="Preferred airline e.g. 'Delta', 'Air France'")
    airline_class: Optional[str] = Field("economy", description="Airline class e.g. 'economy', 'premium_economy', 'business', 'first'")
    interests: list[str] = Field(default_factory=lambda: ["romantic", "nature"], description="Trip interests e.g. ['romantic', 'nature', 'spiritual', 'adventure']")
    is_test: Optional[bool] = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class UpdatePreferencesRequest(BaseModel):
    home_airport: Optional[str] = Field(None, description="Home airport IATA code e.g. 'ATL'")
    preferred_style: Optional[str] = Field(None, description="Preferred travel style e.g. 'balanced', 'luxury'")
    preferred_budget: Optional[str] = Field(None, description="Preferred budget tier e.g. 'moderate', 'luxury'")
    seat_preference: Optional[str] = Field(None, description="Preferred seating e.g. 'window', 'aisle'")
    hotel_type: Optional[str] = Field(None, description="Preferred hotel style e.g. 'resort', 'boutique'")
    hotel_rating: Optional[str] = Field(None, description="Preferred star rating e.g. '4-star', '5-star'")
    hotel_user_rating: Optional[str] = Field(None, description="Preferred min user rating e.g. '8.5+'")
    ui_layout: Optional[str] = Field(None, description="UI data pane layout e.g. 'grid', 'compact'")
    airline: Optional[str] = Field(None, description="Preferred airline e.g. 'Delta', 'Air France'")
    airline_class: Optional[str] = Field(None, description="Airline class e.g. 'economy', 'business'")
    interests: Optional[list[str]] = Field(None, description="Trip interests e.g. ['romantic', 'nature', 'spiritual', 'adventure']")
    is_test: Optional[bool] = False


from ...db.user_preference_dao import UserPreferenceDAO

@router.get(
    "/{user_id}/preferences",
    response_model=UserPreferencesModel,
    summary="Get Active User Preferences & AI Profile",
)
def get_user_preferences(user_id: str):
    """Retrieves user travel preferences from dedicated `users.user_preferences` database table."""
    cfg = UserServiceConfig()
    pref_dao = UserPreferenceDAO(config=cfg)
    prefs = pref_dao.get_preferences(user_id)

    return UserPreferencesModel(
        user_id=user_id,
        home_airport=prefs.get("home_airport", "ATL"),
        preferred_style=prefs.get("preferred_style", "balanced"),
        preferred_budget=prefs.get("preferred_budget", "moderate"),
        seat_preference=prefs.get("seat_preference", "window"),
        hotel_type=prefs.get("hotel_type", "resort"),
        hotel_rating=prefs.get("hotel_rating", "4-star"),
        hotel_user_rating=prefs.get("hotel_user_rating", "8.5+"),
        ui_layout=prefs.get("ui_layout", "grid"),
        airline=prefs.get("airline", "Delta"),
        airline_class=prefs.get("airline_class", "economy"),
        interests=prefs.get("interests", ["romantic", "nature"]),
        is_test=prefs.get("is_test", False),
        created_at=prefs.get("created_at"),
        updated_at=prefs.get("updated_at"),
    )


@router.put(
    "/{user_id}/preferences",
    summary="Update User Preferences Manually",
)
def update_user_preferences(user_id: str, req: UpdatePreferencesRequest):
    """Updates user travel preferences in dedicated `users.user_preferences` table."""
    cfg = UserServiceConfig()
    pref_dao = UserPreferenceDAO(config=cfg)
    success = pref_dao.upsert_preferences(
        user_id=user_id,
        home_airport=req.home_airport,
        preferred_style=req.preferred_style,
        preferred_budget=req.preferred_budget,
        seat_preference=req.seat_preference,
        hotel_type=req.hotel_type,
        hotel_rating=req.hotel_rating,
        hotel_user_rating=req.hotel_user_rating,
        ui_layout=req.ui_layout,
        airline=req.airline,
        airline_class=req.airline_class,
        interests=req.interests,
        is_test=req.is_test or False
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user preferences in user_preferences table."
        )

    updated_prefs = pref_dao.get_preferences(user_id)
    return {
        "status": "success",
        "message": f"Updated preferences for user '{user_id}' in user_preferences table.",
        "data": updated_prefs
    }


    return {
        "status": "success",
        "message": f"Updated preferences for user '{user_id}'.",
        "user_id": user_id
    }


@router.post(
    "/{user_id}/preferences/auto-evaluate",
    summary="Trigger LLM Background Profiler Service to Auto-Identify Preferences",
)
def trigger_auto_evaluate_preferences(user_id: str, background_tasks: BackgroundTasks):
    """
    Triggers background LLM profiler service to analyze search history & booking history
    and auto-update user travel preferences.
    """
    profiler = UserPreferenceProfiler()
    background_tasks.add_task(profiler.evaluate_user_profile, user_id=user_id)

    return {
        "status": "success",
        "message": f"Queued background LLM evaluation task for user '{user_id}'. Preferences will update upon completion.",
        "user_id": user_id
    }
