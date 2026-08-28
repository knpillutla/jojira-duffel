"""
Dedicated REST API Controller for AI Trip Plans (`users.user_trip_plans`).
Handles saving AI draft plans, day-by-day schedules, and suggested package deals.
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from ...db.trip_plan_dao import TripPlanDAO
from ...db.user_dao import UserDAO
from ...config import UserServiceConfig

router = APIRouter(prefix="/users", tags=["AI Trip Plans"])


class SaveTripPlanRequest(BaseModel):
    title: str = Field(..., description="User-facing title e.g. '4 Days in Paris'")
    prompt: str = Field(..., description="Original search prompt")
    destination: Optional[str] = Field(None, description="Destination city/IATA e.g. 'CDG'")
    origin: Optional[str] = Field(None, description="Origin city/IATA e.g. 'JFK'")
    trip_duration_days: Optional[int] = Field(None, description="Total days")
    day_by_day_schedule: Optional[dict[str, Any]] = Field(None, description="Day-by-day attraction schedule")
    package_options: Optional[list[dict[str, Any]]] = Field(None, description="Suggested package deals")


class TripPlanItem(BaseModel):
    id: str
    title: str
    prompt: str
    destination: Optional[str] = None
    origin: Optional[str] = None
    trip_duration_days: Optional[int] = None
    created_at: Optional[str] = None


class TripPlansResponse(BaseModel):
    status: str
    user_id: str
    count: int
    plans: list[TripPlanItem]


@router.post(
    "/{user_id}/plans",
    summary="Save AI Trip Plan Draft",
)
def save_user_trip_plan(user_id: str, req: SaveTripPlanRequest):
    """Saves a generated AI Trip Plan draft (day-by-day attraction schedule + suggested package deals)."""
    cfg = UserServiceConfig()
    user_dao = UserDAO(config=cfg)
    if user_id != "guest" and not user_dao.get_user_by_id(user_id):
        user_id = "guest"

    plan_dao = TripPlanDAO(config=cfg)
    plan_id = plan_dao.save_trip_plan(
        user_id=user_id,
        title=req.title,
        prompt=req.prompt,
        destination=req.destination,
        origin=req.origin,
        trip_duration_days=req.trip_duration_days,
        day_by_day_schedule=req.day_by_day_schedule,
        package_options=req.package_options,
    )

    return {
        "status": "success",
        "message": f"Saved AI Trip Plan '{plan_id}'.",
        "plan_id": plan_id
    }


@router.get(
    "/{user_id}/plans",
    response_model=TripPlansResponse,
    summary="Get User's Saved AI Trip Plans",
)
def get_user_trip_plans(user_id: str, limit: int = Query(20, ge=1, le=100)):
    """Retrieves lightweight list of saved AI Trip Plans for a user."""
    cfg = UserServiceConfig()
    plan_dao = TripPlanDAO(config=cfg)
    rows = plan_dao.get_user_trip_plans(user_id=user_id, limit=limit)
    items = [TripPlanItem(**r) for r in rows]

    return TripPlansResponse(
        status="success",
        user_id=user_id,
        count=len(items),
        plans=items
    )


@router.get(
    "/{user_id}/plans/{plan_id}",
    summary="Get Specific AI Trip Plan Details & Package Options",
)
def get_user_trip_plan_details(user_id: str, plan_id: str):
    """Retrieves full details for a saved AI Trip Plan, including day-by-day schedule and suggested package deals."""
    cfg = UserServiceConfig()
    plan_dao = TripPlanDAO(config=cfg)
    details = plan_dao.get_trip_plan_by_id(user_id=user_id, plan_id=plan_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI Trip Plan '{plan_id}' for user '{user_id}' was not found."
        )

    return {
        "status": "success",
        "data": details
    }



