"""
AI Search Route Controllers for Duffel REST API.
Intelligent routing based on natural language prompt parsing with LLM.
"""

from typing import Any, Optional
from fastapi import APIRouter, HTTPException, Query, Request, status

from ..schemas import (
    AIBookingRequest,
    AIBookingResponse,
    AISearchRequest,
    AISearchResponse,
    SaveAISearchHistoryRequest,
    SaveAISearchHistoryResponse,
    AISearchHistoryListResponse,
    AISearchHistoryItem,
)
from . import common
from .bundles import book_bundle_endpoint
from .cars import book_car_endpoint
from .flights import book_flight
from .stays import book_stay_endpoint

router = APIRouter(tags=["AI Search API"])

VALID_SEARCH_TYPES = {"flights", "hotels", "cars", "bundle"}


def _resolve_search_type(req: AIBookingRequest) -> str:
    """Determines which service to book against from explicit search_type, source, or populated payload."""
    if req.search_type:
        st = req.search_type.strip().lower()
        st = "hotels" if st == "hotel" else st
        if st not in VALID_SEARCH_TYPES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid search_type '{st}'. Must be one of {sorted(VALID_SEARCH_TYPES)}.",
            )
        return st

    if req.source:
        s = req.source.lower()
        for t in VALID_SEARCH_TYPES:
            if t in s:
                return t

    if req.bundle:
        return "bundle"
    if req.flight:
        return "flights"
    if req.hotel:
        return "hotels"
    if req.car:
        return "cars"

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        detail="Unable to determine search_type. Provide 'search_type', 'source', or one of flight/hotel/car/bundle payloads.",
    )


@router.post(
    "/search/ai",
    response_model=AISearchResponse,
    summary="Intelligent AI-Powered Multi-Service Travel Search",
)
def search_ai_endpoint(req: AISearchRequest):
    """
    Intelligent AI Search that parses natural language prompts and routes to appropriate service(s).
    
    Flow:
    1. Parse prompt using LLM to extract intent (flights, hotels, cars, combinations)
    2. If single type: invoke that service, return its native response format
    3. If multiple types: invoke bundle service, return bundle response format
    4. Results: top 20 offers sorted by total price ascending
    5. Cached in Redis with dynamic TTL
    """
    client = common.get_duffel_client()
    try:
        # Ensure AI Search service is attached
        if not hasattr(client, "ai_search"):
            from ...services.ai_search import AISearchService
            client.ai_search = AISearchService(client.http_client, cache=client.cache, adapter=client.adapter, client=client)

        # Build overrides from optional parameters
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

        # Execute AI search with intelligent routing
        result = client.ai_search.search_ai(
            prompt=req.prompt,
            favorite_airline=req.favorite_airline or "",
            force_refresh=req.force_refresh,
            overrides=overrides,
        )
        
        if isinstance(result, dict) and result.get("status") == "error":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("message") or result.get("error") or "Validation error",
            )

        return AISearchResponse(**result)
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI search execution failed: {str(err)}"
        )


@router.get(
    "/search/ai",
    response_model=AISearchResponse,
    summary="Intelligent AI-Powered Multi-Service Travel Search (GET)",
)
def get_search_ai_endpoint(
    prompt: str = Query(..., description="Natural language search prompt e.g. 'Flight and hotel from NYC to Paris for 5 days'"),
    favorite_airline: str = Query("", description="Optional favorite airline"),
    force_refresh: bool = Query(False, description="Bypass cache"),
):
    """GET endpoint for AI-powered travel search."""
    return search_ai_endpoint(
        AISearchRequest(
            prompt=prompt,
            favorite_airline=favorite_airline,
            force_refresh=force_refresh,
        )
    )


@router.post(
    "/search/ai/book",
    response_model=AIBookingResponse,
    summary="Book an AI Search Result (Auto-Routes to Flights/Hotels/Cars/Bundle Booking)",
)
def book_ai_endpoint(req: AIBookingRequest, request: Request):
    """
    Books the result of a prior AI search.

    The caller passes back the same `source`/`search_type` returned by `/search/ai`
    along with the matching type-specific booking payload (flight/hotel/car/bundle).
    This endpoint resolves which underlying service was used and calls its book API:
    - flights -> POST /flights/book
    - hotels  -> POST /stays/book
    - cars    -> POST /cars/book
    - bundle  -> POST /bundles/book
    and returns that service's booking response, tagged with search_type/source.
    """
    search_type = _resolve_search_type(req)

    try:
        if search_type == "flights":
            if not req.flight:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="search_type is 'flights' but no 'flight' booking payload was provided.",
                )
            booking_res = book_flight(req.flight, request)
        elif search_type == "hotels":
            if not req.hotel:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="search_type is 'hotels' but no 'hotel' booking payload was provided.",
                )
            booking_res = book_stay_endpoint(req.hotel)
        elif search_type == "cars":
            if not req.car:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="search_type is 'cars' but no 'car' booking payload was provided.",
                )
            booking_res = book_car_endpoint(req.car)
        else:  # bundle
            if not req.bundle:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="search_type is 'bundle' but no 'bundle' booking payload was provided.",
                )
            booking_res = book_bundle_endpoint(req.bundle)
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI booking failed while calling '{search_type}' book API: {str(err)}",
        )

    payload = booking_res.model_dump() if hasattr(booking_res, "model_dump") else dict(booking_res)
    payload["search_type"] = search_type
    payload["source"] = req.source
    return AIBookingResponse(**payload)


@router.post(
    "/search/ai/history",
    response_model=SaveAISearchHistoryResponse,
    summary="Save AI Search Prompt & Results into History",
)
@router.post(
    "/prompts/history",
    response_model=SaveAISearchHistoryResponse,
    summary="Save Search Prompt History (Alias)",
)
def save_ai_search_history_endpoint(req: SaveAISearchHistoryRequest):
    """
    Persists an AI search prompt, extracted parameters, and result summary into history table.
    """
    from ...db.order_dao import OrderDAO
    dao = OrderDAO(config=common.get_duffel_client().config)
    try:
        saved = dao.save_ai_search_history(
            prompt=req.prompt,
            user_id=req.user_id or "guest_user",
            search_type=req.search_type or "flights",
            origin=req.origin,
            destination=req.destination,
            departure_date=req.departure_date,
            return_date=req.return_date,
            parsed_intent=req.parsed_intent,
            results_summary=req.results_summary,
        )
        return SaveAISearchHistoryResponse(
            status="success",
            message="AI search prompt successfully saved to history.",
            history_id=saved["id"],
            user_id=saved["user_id"],
            prompt=saved["prompt"],
            created_at=saved["created_at"],
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed saving AI search prompt history: {str(err)}"
        )


@router.get(
    "/search/ai/history",
    response_model=AISearchHistoryListResponse,
    summary="Retrieve AI Search Prompt History",
)
@router.get(
    "/prompts/history",
    response_model=AISearchHistoryListResponse,
    summary="Retrieve Search Prompt History (Alias)",
)
def get_ai_search_history_endpoint(
    user_id: Optional[str] = Query(None, description="Filter history by user_id or session_id"),
    search_type: Optional[str] = Query(None, description="Filter history by search_type: flights, hotels, cars, or bundle"),
    limit: int = Query(20, ge=1, le=100, description="Max history records returned"),
):
    """
    Retrieves historical AI search prompts, extracted intent, and results summary for a user.
    """
    from ...db.order_dao import OrderDAO
    dao = OrderDAO(config=common.get_duffel_client().config)
    try:
        records = dao.get_ai_search_history(
            user_id=user_id,
            search_type=search_type,
            limit=limit,
        )
        history_items = [AISearchHistoryItem(**r) for r in records]
        return AISearchHistoryListResponse(
            status="success",
            user_id=user_id,
            total_records=len(history_items),
            history=history_items,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed retrieving AI search prompt history: {str(err)}"
        )

