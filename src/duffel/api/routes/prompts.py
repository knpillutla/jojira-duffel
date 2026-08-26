"""
Popular & Trending Prompts Route Controllers for Duffel REST API.
"""

from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status

from ..schemas import PopularPromptsResponse
from . import common

router = APIRouter(tags=["Popular Search Prompts API"])


@router.get(
    "/prompts/popular",
    response_model=PopularPromptsResponse,
    summary="Get Popular / Trending Search Prompts & Parameters",
)
@router.get(
    "/search/popular-prompts",
    response_model=PopularPromptsResponse,
    summary="Get Popular / Trending Search Prompts (Alias)",
)
def get_popular_prompts_endpoint(
    category: Optional[str] = Query(None, description="Filter category: flights, cars, hotels, bundles, ai_trip_planner, ai_search"),
    limit: int = Query(6, ge=1, le=20, description="Max prompts returned per category"),
):
    """
    Returns top trending travel search prompts and structured search parameters across
    Flights, Cars, Hotels, Travel Bundles, AI Trip Planner, and AI Search.
    UI can render prompt buttons/cards and populate search form fields automatically when clicked.
    """
    client = common.get_duffel_client()
    try:
        if not hasattr(client, "prompts"):
            from ...services.prompts import PromptsService
            client.prompts = PromptsService(client.http_client, cache=client.cache, adapter=client.adapter, client=client)

        result = client.prompts.get_popular_prompts(category=category, limit=limit)
        return PopularPromptsResponse(**result)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch popular prompts: {str(err)}"
        )
