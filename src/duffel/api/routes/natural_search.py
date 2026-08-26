"""
Unified Natural Search Route Controllers for Duffel REST API.
"""

from fastapi import APIRouter, HTTPException, Query, status

from ...exceptions import DuffelException
from ..schemas import NaturalSearchRequest, NaturalSearchResponse
from . import common

router = APIRouter(tags=["Unified Natural Search API"])


@router.post(
    "/search/natural",
    response_model=NaturalSearchResponse,
    summary="Unified Multi-Category Natural Language Travel Search",
)
def search_natural_endpoint(req: NaturalSearchRequest):
    """
    Search across Flights, Hotels, Cars, Attractions, or any combination using natural language prompts.
    Returns a combined travel bundle if >1 type is selected, or specific data if 1 type is selected.
    Includes metadata indicating search classification (flights, hotels, cars, attractions, or bundle)
    and full category highlights for UI rendering.
    """
    client = common.get_duffel_client()
    try:
        if not hasattr(client, "natural_search"):
            from ...services.natural_search import NaturalSearchService
            client.natural_search = NaturalSearchService(client.http_client, cache=client.cache, adapter=client.adapter, client=client)

        overrides = {}
        if req.selected_types:
            overrides["selected_types"] = req.selected_types
        if req.origin:
            overrides["origin"] = req.origin
        if req.destination:
            overrides["destination"] = req.destination
        if req.departure_date:
            overrides["departure_date"] = req.departure_date
        if req.return_date:
            overrides["return_date"] = req.return_date
        if req.passengers_count:
            overrides["passengers_count"] = req.passengers_count
        if req.cabin_class:
            overrides["cabin_class"] = req.cabin_class
        if req.rooms:
            overrides["rooms"] = req.rooms
        if req.driver_age:
            overrides["driver_age"] = req.driver_age

        result = client.natural_search.search_natural(
            prompt=req.prompt,
            favorite_airline=req.favorite_airline or "",
            force_refresh=req.force_refresh,
            overrides=overrides,
        )
        return NaturalSearchResponse(**result)
    except HTTPException:
        raise
    except DuffelException as err:
        raise HTTPException(
            status_code=status.HTTP_424_FAILED_DEPENDENCY,
            detail=str(err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Natural search execution failed: {str(err)}"
        )


@router.get(
    "/search/natural",
    response_model=NaturalSearchResponse,
    summary="Unified Multi-Category Natural Language Travel Search (GET)",
)
def get_search_natural_endpoint(
    prompt: str = Query(..., description="Natural language search prompt"),
    favorite_airline: str = Query("", description="Optional favorite airline"),
    force_refresh: bool = Query(False, description="Bypass cache"),
):
    """GET endpoint for unified natural language travel search."""
    return search_natural_endpoint(
        NaturalSearchRequest(
            prompt=prompt,
            favorite_airline=favorite_airline,
            force_refresh=force_refresh,
        )
    )
