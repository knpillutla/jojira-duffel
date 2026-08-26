"""
Stays (Hotels & Accommodations) Route Controllers for Duffel REST API.
"""

from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status

from . import common
from ...services.planner import DESTINATION_GEO_MAP
from ..schemas import StayBookingRequest, StayBookingResponse, StaySearchRequest, StaySearchResponse

router = APIRouter(tags=["Stays (Hotels) API"])

DEFAULT_SEARCH_RADIUS_KM = 5


def normalize_guests(
    guests: Optional[list[dict[str, Any]]] = None,
    guests_count: Optional[int] = None
) -> list[dict[str, Any]]:
    """
    Normalize guests parameter to Duffel format.
    
    Handles multiple input formats:
    - guests: [{"type": "adult"}, {"type": "child", "age": 8}]  (preferred)
    - guests_count: 2  (creates [{"type": "adult"}, {"type": "adult"}])
    
    Returns: List of guest objects with required 'type' field
    """
    if guests:
        # Ensure each guest has a 'type' field
        normalized = []
        for guest in guests:
            if isinstance(guest, dict) and "type" in guest:
                normalized.append(guest)
            else:
                # Default to adult if type missing
                normalized.append({**guest, "type": "adult"})
        return normalized
    
    if guests_count:
        return [{"type": "adult"} for _ in range(guests_count)]
    
    # Default: single adult guest
    return [{"type": "adult"}]


def normalize_location(
    location: Optional[dict[str, Any]] = None,
    location_string: Optional[str] = None,
    radius: Optional[float] = None,
) -> Optional[dict[str, Any]]:
    """
    Normalize location parameter to Duffel's actual stays search schema.

    Duffel's `location` object ONLY accepts `radius` (km) + `geographic_coordinates`
    ({'latitude': float, 'longitude': float}) - there is no `place_id` field.

    Handles multiple input formats:
    - location: {"geographic_coordinates": {"latitude": 28.7, "longitude": 77.1}, "radius": 5}  (preferred)
    - location_string: "paris"  (resolved via known city -> coordinates lookup)

    Returns: Location dict in Duffel format, or None if unresolvable (caller must then
    require accommodation_ids instead, since Duffel requires one of the two).
    """
    if location:
        if "geographic_coordinates" in location:
            return {
                "radius": location.get("radius", radius or DEFAULT_SEARCH_RADIUS_KM),
                "geographic_coordinates": location["geographic_coordinates"],
            }
        # If a single non-standard key is present, treat its value as a place name string
        if isinstance(location, dict) and len(location) == 1:
            key = list(location.keys())[0]
            if key != "geographic_coordinates":
                location_string = location[key]

    if location_string:
        geo = DESTINATION_GEO_MAP.get(location_string.strip().upper())
        if not geo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    f"Unable to resolve location '{location_string}' to coordinates. Duffel requires "
                    "'location.geographic_coordinates' (or 'accommodation_ids'). Pass "
                    "location={'geographic_coordinates': {'latitude': ..., 'longitude': ...}} directly, "
                    f"or use one of the supported city names: {sorted(DESTINATION_GEO_MAP.keys())}."
                ),
            )
        return {
            "radius": radius or DEFAULT_SEARCH_RADIUS_KM,
            "geographic_coordinates": {"latitude": geo["latitude"], "longitude": geo["longitude"]},
        }

    return None


@router.post("/stays/search", response_model=StaySearchResponse, summary="Search Stays (Hotels)")
def search_stays_endpoint(req: StaySearchRequest):
    """Search for hotel accommodation availability by check-in/check-out dates, location, or accommodation IDs."""
    client = common.get_duffel_client()
    try:
        # Normalize guests and location to Duffel format
        normalized_guests = normalize_guests(req.guests, req.guests_count)
        normalized_location = normalize_location(req.location, req.location_string)

        # Duffel requires either a location or accommodation_ids - never neither
        if not normalized_location and not req.accommodation_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Either 'location' (with geographic_coordinates), 'location_string' "
                    "(a supported city name), or 'accommodation_ids' must be provided."
                ),
            )

        results = client.stays.search(
            check_in_date=req.check_in_date,
            check_out_date=req.check_out_date,
            rooms=req.rooms,
            guests=normalized_guests,
            location=normalized_location,
            accommodation_ids=req.accommodation_ids,
        )
        res_dicts = [r.to_dict() if hasattr(r, "to_dict") else getattr(r, "__dict__", {}) for r in results]
        return StaySearchResponse(
            status="success",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_results=len(res_dicts),
            results=res_dicts,
        )
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Hotel search failed: {str(err)}"
        )


@router.get("/stays/search", response_model=StaySearchResponse, summary="Search Stays (Hotels - GET)")
def get_search_stays_endpoint(
    check_in_date: str = Query(..., description="Check-in date YYYY-MM-DD"),
    check_out_date: str = Query(..., description="Check-out date YYYY-MM-DD"),
    rooms: int = Query(1, ge=1, le=10, description="Number of rooms requested"),
    location_string: Optional[str] = Query(None, description="City name to search near, e.g. 'Paris'"),
):
    """HTTP GET endpoint for hotel search via URL query parameters."""
    return search_stays_endpoint(
        StaySearchRequest(
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            rooms=rooms,
            location_string=location_string,
        )
    )


@router.get("/stays/search-results/{search_result_id}", summary="Get Stay Search Result Details")
def get_stay_search_result_endpoint(search_result_id: str = Path(..., description="Stay search result ID")):
    """Retrieves detailed stay search result information including accommodation details and rates."""
    client = common.get_duffel_client()
    try:
        res = client.stays.get_search_result(search_result_id)
        res_dict = res.to_dict() if hasattr(res, "to_dict") else getattr(res, "__dict__", {})
        return {"status": "success", "search_result": res_dict}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to fetch stay search result '{search_result_id}': {str(err)}"
        )


@router.get("/stays/search-results/{search_result_id}/rates", summary="Get Stay Search Result Rates")
def get_stay_rates_endpoint(search_result_id: str = Path(..., description="Stay search result ID")):
    """List available rates for a stay search result."""
    client = common.get_duffel_client()
    try:
        rates = client.stays.get_rates(search_result_id)
        rates_list = [r.to_dict() if hasattr(r, "to_dict") else getattr(r, "__dict__", {}) for r in rates]
        return {"status": "success", "search_result_id": search_result_id, "rates": rates_list}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to fetch stay rates for '{search_result_id}': {str(err)}"
        )


@router.post("/stays/book", response_model=StayBookingResponse, summary="Book Hotel Stay")
@router.post("/stays/orders", response_model=StayBookingResponse, summary="Book Hotel Stay (Orders Alias)")
def book_stay_endpoint(req: StayBookingRequest):
    """Creates a hotel booking / stay order with Duffel Stays API."""
    client = common.get_duffel_client()
    try:
        payments_list = []
        raw_payments = req.payments or ([req.payment] if req.payment else [])
        for pym in raw_payments:
            p_dict = pym.model_dump() if hasattr(pym, "model_dump") else pym.dict()
            payments_list.append(p_dict)

        order = client.stays.create_order(
            quote_id=req.quote_id,
            guests=req.guests,
            payments=payments_list,
            accommodation_id=req.accommodation_id,
        )

        ord_dict = order.to_dict() if hasattr(order, "to_dict") else getattr(order, "__dict__", {})
        ord_id = getattr(order, "id", "") or ord_dict.get("id", "")
        booking_ref = getattr(order, "booking_reference", "") or ord_dict.get("booking_reference", "") or ord_id
        tot = str(getattr(order, "total_amount", "0.00") or ord_dict.get("total_amount", "0.00"))
        curr = str(getattr(order, "total_currency", "USD") or ord_dict.get("total_currency", "USD"))
        acc_name = getattr(order, "accommodation_name", None) or ord_dict.get("accommodation_name")
        check_in = getattr(order, "check_in_date", None) or ord_dict.get("check_in_date")
        check_out = getattr(order, "check_out_date", None) or ord_dict.get("check_out_date")

        tot_val = float(tot or 0.0)
        disc_val = float(req.discount_amount or 0.0)
        gross_val = tot_val + disc_val

        # Persist stay order to database via OrderDAO
        try:
            from ...db.order_dao import OrderDAO
            order_dao = OrderDAO(config=client.config)
            order_dao.save_stay_order(
                duffel_order_id=ord_id,
                booking_reference=booking_ref,
                total_amount=tot,
                total_currency=curr,
                quote_id=req.quote_id,
                accommodation_id=req.accommodation_id,
                accommodation_name=acc_name,
                check_in_date=check_in,
                check_out_date=check_out,
                status="confirmed",
                payment_status="paid",
                guests=req.guests,
                promo_code=req.promo_code,
                gross_amount=f"{gross_val:.2f}",
                discount_amount=f"{disc_val:.2f}",
            )
        except Exception as db_err:
            print(f"[ORDER DAO NOTICE] Failed saving stay order to database: {db_err}")

        return StayBookingResponse(
            status="confirmed",
            message="Hotel stay booked successfully.",
            order_id=ord_id,
            booking_reference=booking_ref,
            total_amount=tot,
            total_currency=curr,
            created_at=datetime.now().isoformat(),
            accommodation_name=acc_name,
            check_in_date=check_in,
            check_out_date=check_out,
            gross_amount=f"{gross_val:.2f}",
            discount_amount=f"{disc_val:.2f}",
            promo_code=req.promo_code,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hotel stay booking failed: {str(err)}"
        )


@router.get("/stays/orders/{order_id}", summary="Get Stay Order Details")
def get_stay_order_endpoint(order_id: str = Path(..., description="Stay order ID")):
    """Retrieves stay order details by order ID."""
    client = common.get_duffel_client()
    try:
        order = client.stays.get_order(order_id)
        ord_dict = order.to_dict() if hasattr(order, "to_dict") else getattr(order, "__dict__", {})
        return {"status": "success", "order": ord_dict}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to fetch stay order '{order_id}': {str(err)}"
        )


@router.post("/stays/orders/{order_id}/cancel", summary="Cancel Stay Order")
def cancel_stay_order_endpoint(order_id: str = Path(..., description="Stay order ID")):
    """Cancels a stay order."""
    client = common.get_duffel_client()
    try:
        cancellation = client.stays.cancel_order(order_id)
        canc_dict = cancellation.to_dict() if hasattr(cancellation, "to_dict") else getattr(cancellation, "__dict__", {})
        return {"status": "cancelled", "cancellation": canc_dict}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel stay order '{order_id}': {str(err)}"
        )
