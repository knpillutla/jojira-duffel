"""
Stays (Hotels & Accommodations) Route Controllers for Duffel REST API.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query, status

from . import common
from ..schemas import StayBookingRequest, StayBookingResponse, StaySearchRequest, StaySearchResponse

router = APIRouter(tags=["Stays (Hotels) API"])


@router.post("/stays/search", response_model=StaySearchResponse, summary="Search Stays (Hotels)")
def search_stays_endpoint(req: StaySearchRequest):
    """Search for hotel accommodation availability by check-in/check-out dates, location, or accommodation IDs."""
    client = common.get_duffel_client()
    try:
        results = client.stays.search(
            check_in_date=req.check_in_date,
            check_out_date=req.check_out_date,
            rooms=req.rooms,
            guests=req.guests,
            location=req.location,
            accommodation_ids=req.accommodation_ids,
        )
        res_dicts = [r.to_dict() if hasattr(r, "to_dict") else getattr(r, "__dict__", {}) for r in results]
        return StaySearchResponse(
            status="success",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_results=len(res_dicts),
            results=res_dicts,
        )
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
):
    """HTTP GET endpoint for hotel search via URL query parameters."""
    return search_stays_endpoint(
        StaySearchRequest(
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            rooms=rooms,
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
