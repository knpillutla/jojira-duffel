"""
User Profile & Preferences Routes for Jojira User Service.
"""

from fastapi import APIRouter, HTTPException, status
from ..schemas import UserProfileResponse, UserPreferencesUpdateRequest
from ...db.user_dao import UserDAO
from ...config import UserServiceConfig

router = APIRouter(prefix="/users", tags=["User Profile & Preferences"])


@router.get(
    "/{user_id}",
    response_model=UserProfileResponse,
    summary="Get User Profile & Travel Preferences",
)
def get_user_profile(user_id: str):
    """Retrieves user profile information and travel preferences."""
    user_dao = UserDAO(config=UserServiceConfig())
    user_data = user_dao.ensure_user_exists(user_id)


    return UserProfileResponse(
        status="success",
        user_id=user_data["id"],
        email=user_data["email"],
        name=user_data.get("name"),
        first_name=user_data.get("first_name"),
        last_name=user_data.get("last_name"),
        given_name=user_data.get("given_name"),
        family_name=user_data.get("family_name"),
        phone_number=user_data.get("phone_number"),
        date_of_birth=user_data.get("date_of_birth"),
        picture_url=user_data.get("picture_url"),
        google_user_id=user_data.get("google_user_id"),
        last_login_at=user_data.get("last_login_at"),
        created_at=user_data.get("created_at"),
        preferences=user_data["preferences"]
    )


@router.put(
    "/{user_id}/preferences",
    response_model=UserProfileResponse,
    summary="Update User Travel Preferences",
)
def update_user_preferences(user_id: str, req: UserPreferencesUpdateRequest):
    """Updates travel preferences for a user (home airport, preferred style, budget, seat choice, interests)."""
    user_dao = UserDAO(config=UserServiceConfig())
    existing = user_dao.get_user_by_id(user_id)
    if not existing:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' was not found."
        )

    from ...db.user_preferences_dao import UserPreferencesDAO
    pref_dao = UserPreferencesDAO(config=UserServiceConfig())
    success = pref_dao.update_preferences(
        user_id=user_id,
        home_airport=req.home_airport,
        preferred_style=req.preferred_style,
        preferred_budget=req.preferred_budget,
        seat_preference=req.seat_preference,
        interests=req.interests,
    )


    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user preferences."
        )

    updated_user = user_dao.get_user_by_id(user_id)
    return UserProfileResponse(
        status="success",
        user_id=updated_user["id"],
        email=updated_user["email"],
        name=updated_user.get("name"),
        first_name=updated_user.get("first_name"),
        last_name=updated_user.get("last_name"),
        given_name=updated_user.get("given_name"),
        family_name=updated_user.get("family_name"),
        phone_number=updated_user.get("phone_number"),
        date_of_birth=updated_user.get("date_of_birth"),
        picture_url=updated_user.get("picture_url"),
        google_user_id=updated_user.get("google_user_id"),
        last_login_at=updated_user.get("last_login_at"),
        created_at=updated_user.get("created_at"),
        preferences=updated_user["preferences"]
    )

