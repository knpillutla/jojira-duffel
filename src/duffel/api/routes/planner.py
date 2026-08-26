"""
AI Travel Planner REST API routes for Duffel FastAPI.
"""

from fastapi import APIRouter, HTTPException, status

from ..schemas.planner import ItineraryPlannerRequest, ItineraryPlannerResponse
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
            origin=req.origin,
            destination=req.destination,
            start_date=req.start_date,
            end_date=req.end_date,
            passengers_count=req.passengers_count,
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
