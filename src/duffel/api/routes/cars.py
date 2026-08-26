"""
Cars (Car Rentals) Route Controllers for Duffel REST API.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query, status

from . import common
from ..schemas import CarBookingRequest, CarBookingResponse, CarSearchRequest, CarSearchResponse

router = APIRouter(tags=["Cars (Car Rentals) API"])


@router.post("/cars/search", response_model=CarSearchResponse, summary="Search Rental Cars")
def search_cars_endpoint(req: CarSearchRequest):
    """Search for rental car offers by pickup/dropoff locations, datetimes, and driver age."""
    client = common.get_duffel_client()
    try:
        offers = client.cars.search(
            pickup_location=req.pickup_location,
            dropoff_location=req.dropoff_location,
            pickup_datetime=req.pickup_datetime,
            dropoff_datetime=req.dropoff_datetime,
            driver_age=req.driver_age,
        )
        offer_dicts = [o.to_dict() if hasattr(o, "to_dict") else getattr(o, "__dict__", {}) for o in offers]
        return CarSearchResponse(
            status="success",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            total_offers=len(offer_dicts),
            offers=offer_dicts,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Car rental search failed: {str(err)}"
        )


@router.get("/cars/search", response_model=CarSearchResponse, summary="Search Rental Cars (GET)")
def get_search_cars_endpoint(
    pickup_location: str = Query(..., description="Pickup location code e.g. LHR"),
    dropoff_location: str = Query(..., description="Dropoff location code e.g. LHR"),
    pickup_datetime: str = Query(..., description="Pickup datetime ISO format"),
    dropoff_datetime: str = Query(..., description="Dropoff datetime ISO format"),
    driver_age: int = Query(30, ge=18, le=99, description="Driver age"),
):
    """HTTP GET endpoint for car rental search via URL query parameters."""
    return search_cars_endpoint(
        CarSearchRequest(
            pickup_location=pickup_location,
            dropoff_location=dropoff_location,
            pickup_datetime=pickup_datetime,
            dropoff_datetime=dropoff_datetime,
            driver_age=driver_age,
        )
    )


@router.get("/cars/offers/{offer_id}", summary="Get Car Rental Offer Details")
def get_car_offer_endpoint(offer_id: str = Path(..., description="Car offer ID")):
    """Retrieves details for a specific car rental offer."""
    client = common.get_duffel_client()
    try:
        offer = client.cars.get_offer(offer_id)
        off_dict = offer.to_dict() if hasattr(offer, "to_dict") else getattr(offer, "__dict__", {})
        return {"status": "success", "offer": off_dict}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to fetch car offer '{offer_id}': {str(err)}"
        )


@router.post("/cars/book", response_model=CarBookingResponse, summary="Book Rental Car")
@router.post("/cars/orders", response_model=CarBookingResponse, summary="Book Rental Car (Orders Alias)")
def book_car_endpoint(req: CarBookingRequest):
    """Creates a car rental order with Duffel Cars API."""
    client = common.get_duffel_client()
    try:
        payments_list = []
        raw_payments = req.payments or ([req.payment] if req.payment else [])
        for pym in raw_payments:
            p_dict = pym.model_dump() if hasattr(pym, "model_dump") else pym.dict()
            payments_list.append(p_dict)

        order = client.cars.create_order(
            offer_id=req.offer_id,
            driver_details=req.driver_details,
            payments=payments_list,
        )

        ord_dict = order.to_dict() if hasattr(order, "to_dict") else getattr(order, "__dict__", {})
        ord_id = getattr(order, "id", "") or ord_dict.get("id", "")
        booking_ref = getattr(order, "booking_reference", "") or ord_dict.get("booking_reference", "") or ord_id
        tot = str(getattr(order, "total_amount", "0.00") or ord_dict.get("total_amount", "0.00"))
        curr = str(getattr(order, "total_currency", "USD") or ord_dict.get("total_currency", "USD"))
        veh_name = getattr(order, "vehicle_name", None) or ord_dict.get("vehicle_name")
        supp_name = getattr(order, "supplier_name", None) or ord_dict.get("supplier_name")

        tot_val = float(tot or 0.0)
        disc_val = float(req.discount_amount or 0.0)
        gross_val = tot_val + disc_val

        # Persist car order to database via OrderDAO
        try:
            from ...db.order_dao import OrderDAO
            order_dao = OrderDAO(config=client.config)
            order_dao.save_car_order(
                duffel_order_id=ord_id,
                booking_reference=booking_ref,
                total_amount=tot,
                total_currency=curr,
                offer_id=req.offer_id,
                supplier_name=supp_name,
                vehicle_name=veh_name,
                driver_age=int(req.driver_details.get("age", 30)) if isinstance(req.driver_details, dict) else 30,
                status="confirmed",
                payment_status="paid",
                driver_details=req.driver_details,
                promo_code=req.promo_code,
                gross_amount=f"{gross_val:.2f}",
                discount_amount=f"{disc_val:.2f}",
            )
        except Exception as db_err:
            print(f"[ORDER DAO NOTICE] Failed saving car order to database: {db_err}")

        return CarBookingResponse(
            status="confirmed",
            message="Car rental booked successfully.",
            order_id=ord_id,
            booking_reference=booking_ref,
            total_amount=tot,
            total_currency=curr,
            created_at=datetime.now().isoformat(),
            vehicle_name=veh_name,
            supplier_name=supp_name,
            gross_amount=f"{gross_val:.2f}",
            discount_amount=f"{disc_val:.2f}",
            promo_code=req.promo_code,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Car rental booking failed: {str(err)}"
        )


@router.get("/cars/orders/{order_id}", summary="Get Car Order Details")
def get_car_order_endpoint(order_id: str = Path(..., description="Car order ID")):
    """Retrieves car rental order details by order ID."""
    client = common.get_duffel_client()
    try:
        order = client.cars.get_order(order_id)
        ord_dict = order.to_dict() if hasattr(order, "to_dict") else getattr(order, "__dict__", {})
        return {"status": "success", "order": ord_dict}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Failed to fetch car order '{order_id}': {str(err)}"
        )


@router.post("/cars/orders/{order_id}/cancel", summary="Cancel Car Rental Order")
def cancel_car_order_endpoint(order_id: str = Path(..., description="Car order ID")):
    """Cancels a car rental order."""
    client = common.get_duffel_client()
    try:
        cancellation = client.cars.cancel_order(order_id)
        canc_dict = cancellation.to_dict() if hasattr(cancellation, "to_dict") else getattr(cancellation, "__dict__", {})
        return {"status": "cancelled", "cancellation": canc_dict}
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to cancel car order '{order_id}': {str(err)}"
        )
