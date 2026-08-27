"""
AI Travel Planner REST API routes for Duffel FastAPI.
"""

from fastapi import APIRouter, HTTPException, status

from ..schemas.planner import (
    ItineraryPlannerRequest,
    ItineraryPlannerResponse,
    ItineraryLikeRequest,
    ItineraryLikeResponse,
)
from . import common


router = APIRouter(prefix="/api/v1", tags=["AI Travel Planner"])


@router.post(
    "/planner/itinerary",
    response_model=ItineraryPlannerResponse,
    summary="Generate AI Day-by-Day Travel Itinerary with Geo-Coordinates & Top 3 Bundle Prices",
)
@router.post(
    "/planner/generate",
    response_model=ItineraryPlannerResponse,
    summary="Generate AI Day-by-Day Travel Itinerary (Alias)",
)
def generate_itinerary_endpoint(req: ItineraryPlannerRequest):
    """
    Generates a comprehensive day-by-day travel itinerary complete with attraction geo-coordinates
    for interactive map rendering and pairs it with the Top 3 live travel package bundle prices (Flight + Hotel + Car).
    Enforces a strict 30-day maximum trip duration guardrail.
    """
    client = common.get_duffel_client()
    try:
        if not hasattr(client, "planner"):
            from ...services.planner import TravelPlannerService
            client.planner = TravelPlannerService(client.http_client, cache=client.cache, adapter=client.adapter, client=client)

        res = client.planner.generate_itinerary(
            prompt=req.prompt,
            include_flights=req.include_flights,
            include_hotels=req.include_hotels,
            include_cars=req.include_cars,
            include_attractions=req.include_attractions,
            include_activities=req.include_activities,
            origin=req.origin,
            destination=req.destination,
            days=req.days or req.trip_duration_days,
            style=req.style,
            budget=req.budget,
            start_date=req.start_date,
            end_date=req.end_date,
            passengers_count=req.passengers_count,
            rooms=req.rooms,
            driver_age=req.driver_age,
            interests=req.interests,
            force_refresh=req.force_refresh,
        )


        return ItineraryPlannerResponse(**res)
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed generating AI travel itinerary: {str(err)}"
        )


@router.post(
    "/planner/like",
    response_model=ItineraryLikeResponse,
    summary="Upvote or Downvote an AI Itinerary",
)
@router.post(
    "/planner/feedback",
    response_model=ItineraryLikeResponse,
    summary="Upvote or Downvote an AI Itinerary (Alias)",
)
def like_itinerary_endpoint(req: ItineraryLikeRequest):
    """
    Submits user feedback (like/upvote or downvote) for a generated travel itinerary.
    - If liked (liked=true): Saves upvote and notes in PostgreSQL via ItineraryDAO.
    - If downvoted (liked=false): Deletes the itinerary from PostgreSQL and purges Redis & process cache so future searches re-invoke LLM to create a fresh itinerary.
    """
    client = common.get_duffel_client()
    try:
        if not hasattr(client, "planner"):
            from ...services.planner import TravelPlannerService
            client.planner = TravelPlannerService(client.http_client, cache=client.cache, adapter=client.adapter, client=client)

        res = client.planner.like_itinerary(
            itinerary_id=req.itinerary_id,
            liked=req.liked,
            feedback_notes=req.feedback_notes,
        )
        return ItineraryLikeResponse(**res)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed processing itinerary feedback: {str(err)}"
        )

