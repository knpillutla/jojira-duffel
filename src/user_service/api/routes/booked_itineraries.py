"""
Dedicated REST API Controller for Booked Itineraries (`users.user_booked_itineraries`).
Handles confirming user bookings and linking live supplier order tickets (flights, hotels, cars, bundles).
"""

import json
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query, Request, status

from pydantic import BaseModel, Field
from ...db.booked_itinerary_dao import BookedItineraryDAO
from ...db.user_dao import UserDAO
from ...config import UserServiceConfig

router = APIRouter(tags=["Booked Itineraries"])


class CreateBookedItineraryRequest(BaseModel):
    title: str = Field(..., description="Booking title e.g. 'Flight + Hotel Paris Trip'")
    destination: str = Field(..., description="Destination city/IATA e.g. 'CDG'")
    total_amount: float = Field(..., description="Total price paid")
    total_currency: str = Field("USD", description="Currency code")
    status: str = Field("confirmed", description="Booking status e.g. 'confirmed', 'ticketed'")
    trip_plan_id: Optional[str] = Field(None, description="Optional AI Trip Plan source ID")
    flight_order_id: Optional[str] = Field(None, description="Optional flight order ID")
    stay_order_id: Optional[str] = Field(None, description="Optional hotel stay order ID")
    car_order_id: Optional[str] = Field(None, description="Optional car rental order ID")
    bundle_order_id: Optional[str] = Field(None, description="Optional bundle order ID")
    booking_details: Optional[dict[str, Any]] = Field(None, description="Full booking details JSON")
    is_test: bool = Field(False, description="Flag indicating if this is a test order for live troubleshooting")


class BookedItineraryItem(BaseModel):
    id: str
    title: str
    destination: str
    status: str
    total_amount: float
    total_currency: str
    flight_order_id: Optional[str] = None
    stay_order_id: Optional[str] = None
    car_order_id: Optional[str] = None
    bundle_order_id: Optional[str] = None
    is_test: Optional[bool] = False
    created_at: Optional[str] = None
    created_by: Optional[str] = None
    updated_at: Optional[str] = None
    updated_by: Optional[str] = None




class BookedItinerariesResponse(BaseModel):
    status: str
    user_id: str
    count: int
    bookings: list[BookedItineraryItem]


@router.post(
    "/bookings",
    summary="Create Confirmed Booked Itinerary (User or Guest)",
)
@router.post(
    "/users/{user_id}/bookings",
    summary="Record Confirmed Booked Itinerary (User Alias)",
)
def create_booked_itinerary_endpoint(req: CreateBookedItineraryRequest, request: Request, user_id: Optional[str] = None):
    """
    Creates/records a confirmed travel booking.
    - If logged in (via Bearer token header or user_id in path): links booking to user_id.
    - If unauthenticated guest: records booking under 'guest'.
    """
    cfg = UserServiceConfig()
    target_user_id = user_id or "guest"
    auth_hdr = request.headers.get("Authorization", "")
    if target_user_id == "guest" and auth_hdr.startswith("Bearer "):
        try:
            from src.user_service.api.routes.auth import _verify_jwt_token
            token_str = auth_hdr.split(" ", 1)[1].strip()
            token_payload = _verify_jwt_token(token_str, cfg.jwt_secret)
            if token_payload and token_payload.get("sub"):
                target_user_id = token_payload["sub"]
        except Exception:
            pass


    bkg_dao = BookedItineraryDAO(config=cfg)
    bkg_id = bkg_dao.create_booked_itinerary(
        user_id=target_user_id,
        title=req.title,
        destination=req.destination,
        total_amount=req.total_amount,
        total_currency=req.total_currency,
        status=req.status,
        trip_plan_id=req.trip_plan_id,
        flight_order_id=req.flight_order_id,
        stay_order_id=req.stay_order_id,
        car_order_id=req.car_order_id,
        bundle_order_id=req.bundle_order_id,
        booking_details=req.booking_details,
        is_test=req.is_test,
    )


    return {
        "status": "success",
        "message": f"Recorded confirmed booked itinerary '{bkg_id}'.",
        "booking_id": bkg_id,
        "user_id": target_user_id,
    }


@router.get(
    "/bookings/{booking_id}",
    summary="Get Confirmed Booking Details by Booking ID (User or Guest)",
)
def get_booking_details_by_id_endpoint(booking_id: str):
    """
    Retrieves full details for a confirmed travel booking and live tickets directly using booking_id.
    Works for both logged-in users and guest checkouts without requiring /guest/ paths.
    """
    cfg = UserServiceConfig()
    bkg_dao = BookedItineraryDAO(config=cfg)
    
    conn = bkg_dao._get_connection()
    cur = conn.cursor()
    sql = "SELECT user_id FROM users.user_booked_itineraries WHERE id = %s LIMIT 1;" if bkg_dao.db_engine == "postgresql" else "SELECT user_id FROM user_booked_itineraries WHERE id = ? LIMIT 1;"
    cur.execute(sql, (booking_id,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booking with ID '{booking_id}' was not found."
        )
    target_user_id = row[0]
    return get_user_booked_itinerary_details(user_id=target_user_id, booking_id=booking_id)


@router.get(
    "/bookings",
    response_model=BookedItinerariesResponse,
    summary="Get Logged-in User's Confirmed Booked Itineraries",
)
@router.get(
    "/users/{user_id}/bookings",
    response_model=BookedItinerariesResponse,
    summary="Get User's Confirmed Booked Itineraries",
)
def get_user_booked_itineraries(request: Request, user_id: Optional[str] = None, limit: int = Query(20, ge=1, le=100)):
    """Retrieves list of confirmed booked itineraries for a logged-in user or specified user_id."""
    cfg = UserServiceConfig()
    target_user_id = user_id or "guest"
    auth_hdr = request.headers.get("Authorization", "")
    if auth_hdr.startswith("Bearer "):
        try:
            from src.user_service.api.routes.auth import _verify_jwt_token
            token_str = auth_hdr.split(" ", 1)[1].strip()
            token_payload = _verify_jwt_token(token_str, cfg.jwt_secret)
            if token_payload and token_payload.get("sub"):
                target_user_id = token_payload["sub"]
        except Exception as err:
            print(f"[BOOKED ITINERARY NOTICE] Auth token decode notice: {err}")


    bkg_dao = BookedItineraryDAO(config=cfg)
    rows = bkg_dao.get_user_booked_itineraries(user_id=target_user_id, limit=limit)
    items = [BookedItineraryItem(**r) for r in rows]

    return BookedItinerariesResponse(
        status="success",
        user_id=target_user_id,
        count=len(items),
        bookings=items
    )



@router.get(
    "/{user_id}/bookings/{booking_id}",
    summary="Get Specific Confirmed Booked Itinerary Details",
)
def get_user_booked_itinerary_details(user_id: str, booking_id: str):
    """Retrieves full details for a confirmed travel booking with linked live order tickets."""
    cfg = UserServiceConfig()
    user_dao = UserDAO(config=cfg)
    if user_id != "guest" and not user_dao.get_user_by_id(user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID '{user_id}' was not found."
        )


    bkg_dao = BookedItineraryDAO(config=cfg)
    details = bkg_dao.get_booked_itinerary_by_id(user_id=user_id, booking_id=booking_id)
    if not details:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Booked itinerary '{booking_id}' for user '{user_id}' was not found."
        )

    # Hydrate clean user-facing order details (passengers, adult/child count, baggage rules, PNR reference)
    details["order_details"] = {}
    fl_id = details.get("flight_order_id")
    if fl_id:
        try:
            from src.duffel.db.flight_order_dao import FlightOrderDAO
            fl_dao = FlightOrderDAO()
            conn = fl_dao._get_connection()
            cur = conn.cursor()
            sql = "SELECT booking_reference, status, total_amount, payment_status, passengers, slices FROM flight_orders WHERE duffel_order_id = %s" if fl_dao.db_engine == "postgresql" else "SELECT booking_reference, status, total_amount, payment_status, passengers, slices FROM flight_orders WHERE duffel_order_id = ?"
            cur.execute(sql, (fl_id,))
            row = cur.fetchone()
            if row:
                passengers_list = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or [])
                slices_list = json.loads(row[5]) if isinstance(row[5], str) else (row[5] or [])

                passenger_names = []
                adult_count = 0
                child_count = 0
                for p in passengers_list:
                    if isinstance(p, dict):
                        g_name = p.get("given_name", "") or p.get("first_name", "")
                        f_name = p.get("family_name", "") or p.get("last_name", "")
                        full = f"{g_name} {f_name}".strip()
                        if full:
                            passenger_names.append(full)
                        p_type = str(p.get("type", "adult")).lower()
                        if "child" in p_type or "infant" in p_type:
                            child_count += 1
                        else:
                            adult_count += 1

                details["order_details"]["flight"] = {
                    "booking_reference": row[0],
                    "status": row[1],
                    "total_amount": str(row[2]),
                    "payment_status": row[3],
                    "total_passengers": len(passengers_list),
                    "adult_count": adult_count or (len(passengers_list) if passengers_list else 1),
                    "child_count": child_count,
                    "passenger_names": passenger_names,
                    "flight_slices": slices_list,
                }
        except Exception as err:
            print(f"[BOOKED ITINERARY NOTICE] Flight hydration notice: {err}")

    st_id = details.get("stay_order_id")
    if st_id:
        try:
            from src.duffel.db.stay_order_dao import StayOrderDAO
            st_dao = StayOrderDAO()
            conn = st_dao._get_connection()
            cur = conn.cursor()
            sql = "SELECT booking_reference, status, total_amount, accommodation_name, check_in_date, check_out_date, rooms, guests FROM stay_orders WHERE duffel_order_id = %s" if st_dao.db_engine == "postgresql" else "SELECT booking_reference, status, total_amount, accommodation_name, check_in_date, check_out_date, rooms, guests FROM stay_orders WHERE duffel_order_id = ?"
            cur.execute(sql, (st_id,))
            row = cur.fetchone()
            if row:
                guests_list = json.loads(row[7]) if isinstance(row[7], str) else (row[7] or [])
                guest_names = [f"{g.get('given_name', '')} {g.get('family_name', '')}".strip() for g in guests_list if isinstance(g, dict) and (g.get('given_name') or g.get('family_name'))]
                details["order_details"]["stay"] = {
                    "booking_reference": row[0],
                    "status": row[1],
                    "total_amount": str(row[2]),
                    "hotel_name": row[3],
                    "check_in_date": row[4],
                    "check_out_date": row[5],
                    "rooms_booked": row[6] or 1,
                    "guest_names": guest_names,
                }
        except Exception as err:
            print(f"[BOOKED ITINERARY NOTICE] Stay hydration notice: {err}")

    cr_id = details.get("car_order_id")
    if cr_id:
        try:
            from src.duffel.db.car_order_dao import CarOrderDAO
            cr_dao = CarOrderDAO()
            conn = cr_dao._get_connection()
            cur = conn.cursor()
            sql = "SELECT booking_reference, status, total_amount, supplier_name, vehicle_name, pickup_location, dropoff_location, pickup_datetime, dropoff_datetime, driver_age, driver_details FROM car_orders WHERE duffel_order_id = %s" if cr_dao.db_engine == "postgresql" else "SELECT booking_reference, status, total_amount, supplier_name, vehicle_name, pickup_location, dropoff_location, pickup_datetime, dropoff_datetime, driver_age, driver_details FROM car_orders WHERE duffel_order_id = ?"
            cur.execute(sql, (cr_id,))
            row = cur.fetchone()
            if row:
                d_details = json.loads(row[10]) if isinstance(row[10], str) else (row[10] or {})
                details["order_details"]["car"] = {
                    "booking_reference": row[0],
                    "status": row[1],
                    "total_amount": str(row[2]),
                    "supplier_name": row[3],
                    "vehicle_name": row[4],
                    "pickup_location": row[5],
                    "dropoff_location": row[6],
                    "pickup_datetime": row[7],
                    "dropoff_datetime": row[8],
                    "driver_age": row[9],
                    "driver_name": f"{d_details.get('given_name', '')} {d_details.get('family_name', '')}".strip() if isinstance(d_details, dict) else "",
                }
        except Exception as err:
            print(f"[BOOKED ITINERARY NOTICE] Car hydration notice: {err}")

    bdl_id = details.get("bundle_order_id")
    if bdl_id:
        try:
            from src.duffel.db.bundle_order_dao import BundleOrderDAO
            bdl_dao = BundleOrderDAO()
            conn = bdl_dao._get_connection()
            cur = conn.cursor()
            sql = "SELECT duffel_bundle_id, status, combined_total_amount, flight_details, stay_details, car_details FROM bundle_orders WHERE duffel_bundle_id = %s" if bdl_dao.db_engine == "postgresql" else "SELECT duffel_bundle_id, status, combined_total_amount, flight_details, stay_details, car_details FROM bundle_orders WHERE duffel_bundle_id = ?"
            cur.execute(sql, (bdl_id,))
            row = cur.fetchone()
            if row:
                fl_info = json.loads(row[3]) if isinstance(row[3], str) else (row[3] or {})
                st_info = json.loads(row[4]) if isinstance(row[4], str) else (row[4] or {})
                cr_info = json.loads(row[5]) if isinstance(row[5], str) else (row[5] or {})
                details["order_details"]["bundle"] = {
                    "bundle_id": row[0],
                    "status": row[1],
                    "combined_total_amount": str(row[2]),
                    "flight_summary": fl_info,
                    "stay_summary": st_info,
                    "car_summary": cr_info,
                }
        except Exception as err:
            print(f"[BOOKED ITINERARY NOTICE] Bundle hydration notice: {err}")

    return {
        "status": "success",
        "data": details
    }



