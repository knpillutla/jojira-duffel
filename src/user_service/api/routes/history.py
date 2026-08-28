"""
User Search History & Saved Bookings Routes for Jojira User Service.
"""

from fastapi import APIRouter, HTTPException, Query, status
from ..schemas import (
    SearchHistoryRecordRequest,
    SearchHistoryResponse,
    SearchHistoryItem,
    SaveBookingRequest,
    SaveBookingResponse,
)
from ...db.search_history_dao import SearchHistoryDAO
from ...db.history_dao import HistoryDAO
from ...db.user_dao import UserDAO
from ...config import UserServiceConfig

router = APIRouter(prefix="/users", tags=["Search History & Saved Bookings"])


@router.post(
    "/{user_id}/history",
    summary="Record User Search Query History",
)
def record_user_search(user_id: str, req: SearchHistoryRecordRequest):
    """Logs a user search query or natural language prompt into search history."""
    cfg = UserServiceConfig()
    user_dao = UserDAO(config=cfg)
    user_dao.ensure_user_exists(user_id)

    search_dao = SearchHistoryDAO(config=cfg)
    rec_id = search_dao.record_search(
        user_id=user_id,
        prompt=req.prompt,
        destination=req.destination,
        origin=req.origin,
        trip_duration_days=req.trip_duration_days,
    )

    return {
        "status": "success",
        "message": f"Recorded search history entry '{rec_id}'.",
        "search_id": rec_id,
    }


@router.get(
    "/{user_id}/history",
    response_model=SearchHistoryResponse,
    summary="Get User Search History",
)
def get_user_search_history(user_id: str, limit: int = Query(20, ge=1, le=100)):
    """Retrieves recent search queries logged for a user."""
    cfg = UserServiceConfig()
    user_dao = UserDAO(config=cfg)
    user_dao.ensure_user_exists(user_id)

    limit_val = limit if isinstance(limit, int) else (getattr(limit, "default", 20) or 20)
    search_dao = SearchHistoryDAO(config=cfg)
    rows = search_dao.get_user_search_history(user_id=user_id, limit=limit_val)

    items = [SearchHistoryItem(**r) for r in rows]

    return SearchHistoryResponse(
        status="success",
        user_id=user_id,
        count=len(items),
        history=items
    )


@router.get(
    "/{user_id}/history/{search_id}",
    summary="Get Specific AI Search Details & Package Bundles",
)
def get_user_search_entry_details(user_id: str, search_id: str):
    """Retrieves full details for a past AI Planner search, including generated package bundles and draft itinerary."""
    cfg = UserServiceConfig()
    user_dao = UserDAO(config=cfg)
    user_dao.ensure_user_exists(user_id)

    search_dao = SearchHistoryDAO(config=cfg)
    details = search_dao.get_search_entry_details(user_id=user_id, search_id=search_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Search history entry '{search_id}' for user '{user_id}' was not found."
        )

    return {
        "status": "success",
        "data": details
    }


@router.post(
    "/{user_id}/bookings",
    response_model=SaveBookingResponse,
    summary="Save Booked or Liked Itinerary for User",
)
def save_user_booking(user_id: str, req: SaveBookingRequest):
    """Saves a booked or liked itinerary to the user's saved bookings collection."""
    cfg = UserServiceConfig()
    user_dao = UserDAO(config=cfg)
    user_dao.ensure_user_exists(user_id)

    history_dao = HistoryDAO(config=cfg)
    bkg_id = history_dao.save_itinerary_booking(
        user_id=user_id,
        itinerary_id=req.itinerary_id,
        destination=req.destination,
        title=req.title,
        total_price=req.total_price,
        payload=req.payload,
    )

    return SaveBookingResponse(
        status="success",
        booking_id=bkg_id,
        message=f"Successfully saved itinerary booking '{req.itinerary_id}' for user '{user_id}'."
    )


@router.get(
    "/{user_id}/bookings",
    summary="Get User Saved & Booked Itineraries",
)
def get_user_bookings(user_id: str):
    """Retrieves all saved or booked itineraries for a user."""
    cfg = UserServiceConfig()
    user_dao = UserDAO(config=cfg)
    user_dao.ensure_user_exists(user_id)

    history_dao = HistoryDAO(config=cfg)
    bookings = history_dao.get_user_bookings(user_id=user_id)
    return {
        "status": "success",
        "user_id": user_id,
        "count": len(bookings),
        "bookings": bookings
    }

