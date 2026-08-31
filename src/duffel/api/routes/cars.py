"""
Cars (Car Rentals) Route Controllers for Duffel REST API.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query, Request, status


from . import common
from ..schemas import CarBookingRequest, CarBookingResponse, CarSearchRequest, CarSearchResponse

router = APIRouter(tags=["Cars (Car Rentals) API"])


@router.post("/cars/search", response_model=CarSearchResponse, summary="Search Rental Cars")
@router.post("/cars/search-optimized", response_model=CarSearchResponse, summary="Optimized Car Rental Search")
def search_cars_endpoint(req: CarSearchRequest):
    """Search for rental car offers by pickup/dropoff locations, datetimes, and driver age."""
    client = common.get_duffel_client()
    try:
        from ...services.locations import resolve_geo_location
        pickup_geo = resolve_geo_location(req.pickup_location)
        dropoff_geo = resolve_geo_location(req.dropoff_location)
        geo_payload = {
            "pickup": {"location": req.pickup_location, **pickup_geo},
            "dropoff": {"location": req.dropoff_location, **dropoff_geo},
        }
    except Exception:
        geo_payload = None

    try:
        offers = client.cars.search(
            pickup_location=req.pickup_location,
            dropoff_location=req.dropoff_location,
            pickup_datetime=req.pickup_datetime,
            dropoff_datetime=req.dropoff_datetime,
            driver_age=req.driver_age,
        )
        offer_dicts = []
        for o in offers:
            od = o.to_dict() if hasattr(o, "to_dict") else getattr(o, "__dict__", {})
            if geo_payload:
                od["geo_location"] = geo_payload
            offer_dicts.append(od)

        meta_data = {
            "type": "cars",
            "pickup_location": req.pickup_location,
            "dropoff_location": req.dropoff_location,
            "pickup_datetime": req.pickup_datetime,
            "dropoff_datetime": req.dropoff_datetime,
            "driver_age": req.driver_age,
            "geo_location": geo_payload,
        }

        data_section = {
            "total_offers": len(offer_dicts),
            "offers": offer_dicts,
        }

        return CarSearchResponse(
            status="success",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            meta_data=meta_data,
            data=data_section,
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
def book_car_endpoint(req: CarBookingRequest, request: Request = None):
    """Creates a car rental order with Duffel Cars API following identical workflow to flight booking."""
    client = common.get_duffel_client()
    idempotency_key = req.idempotency_key or (request.headers.get("Duffel-Idempotency-Key") if request else None) or (request.headers.get("X-Idempotency-Key") if request else None)

    try:
        offer_ids = req.selected_offers or ([req.offer_id] if req.offer_id else [])
        if not offer_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either offer_id or selected_offers list must be provided in request body."
            )

        target_offer_id = offer_ids[0]
        if target_offer_id.startswith("off_duffel_") or target_offer_id.startswith("mock_"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Offer ID '{target_offer_id}' is a sample demo offer. Please execute a live car search to book real rentals."
            )

        # 1. Price Verification & Lock (Guard against live supplier price changes)
        real_offer = None
        try:
            real_offer = client.cars.get_offer(target_offer_id)
            if real_offer and hasattr(real_offer, "total_amount") and real_offer.total_amount:
                live_price = float(real_offer.total_amount)
                user_price = None
                if req.expected_price is not None:
                    user_price = float(req.expected_price)
                elif req.payment and req.payment.amount and req.payment.amount not in ["0.00", "0"]:
                    user_price = float(req.payment.amount)

                if user_price is not None and not req.allow_price_change:
                    if abs(user_price - live_price) > 0.01:
                        curr_str = getattr(real_offer, "total_currency", "USD") or "USD"
                        curr_display = curr_str if isinstance(curr_str, str) else "USD"
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail={
                                "error": "price_changed",
                                "message": f"The supplier updated the car rental price from {curr_display} {user_price:.2f} to {curr_display} {live_price:.2f}. Please confirm the updated price before completing booking.",
                                "old_price": f"{user_price:.2f}",
                                "new_price": f"{live_price:.2f}",
                                "currency": curr_display,
                            }
                        )
        except HTTPException:
            raise
        except Exception:
            pass

        # 2. Driver & Passenger Info Resolution
        driver_info = req.driver_details or req.driver
        if not driver_info and req.passengers:
            p0 = req.passengers[0]
            p0_dict = p0.model_dump() if hasattr(p0, "model_dump") else (p0.dict() if hasattr(p0, "dict") else dict(p0))
            driver_info = {
                "given_name": p0_dict.get("given_name") or p0_dict.get("first_name", "Jane"),
                "family_name": p0_dict.get("family_name") or p0_dict.get("last_name", "Doe"),
                "email": p0_dict.get("email", "jane@example.com"),
                "phone_number": p0_dict.get("phone_number", "+15551234567"),
                "age": int(p0_dict.get("age", 30)) if p0_dict.get("age") else 30,
            }

        if not driver_info:
            driver_info = {"given_name": "Jane", "family_name": "Doe", "email": "jane@example.com", "age": 30}


        # 3. Payment Resolution (Supports Balance & Card with card_id / card_token)
        payments_list = []
        raw_payments = req.payments or ([req.payment] if req.payment else [])
        for pym in raw_payments:
            p_dict = pym.model_dump() if hasattr(pym, "model_dump") else (pym.dict() if hasattr(pym, "dict") else dict(pym))
            token_val = p_dict.get("card_id") or p_dict.get("card_token") or p_dict.get("token") or p_dict.get("payment_method_id") or p_dict.get("customer_card_id")
            if token_val:
                p_dict["card_id"] = str(token_val).strip()
                p_dict["card_token"] = str(token_val).strip()
            payments_list.append(p_dict)

        order = client.cars.create_order(
            offer_id=target_offer_id,
            driver_details=driver_info,
            payments=payments_list if payments_list else [{"type": "balance"}],
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
                offer_id=target_offer_id,
                supplier_name=supp_name,
                vehicle_name=veh_name,
                driver_age=int(driver_info.get("age", 30)) if isinstance(driver_info, dict) else 30,
                status="confirmed",
                payment_status="paid",
                driver_details=driver_info,
                promo_code=req.promo_code,
                gross_amount=f"{gross_val:.2f}",
                discount_amount=f"{disc_val:.2f}",
            )
        except Exception as db_err:
            print(f"[ORDER DAO NOTICE] Failed saving car order to database: {db_err}")

        meta_data = {
            "type": "cars",
            "order_id": ord_id,
            "booking_reference": booking_ref,
            "promo_code": req.promo_code,
            "discount_amount": f"{disc_val:.2f}",
            "gross_amount": f"{gross_val:.2f}",
            "geo_location": None,
        }

        raw_order = getattr(order, "raw", None) or ord_dict.get("raw") or ord_dict

        data_section = {
            **ord_dict,
            "order_id": ord_id,
            "booking_reference": booking_ref,
            "message": "Car rental booked successfully.",
            "total_amount": tot,
            "total_currency": curr,
            "created_at": datetime.now().isoformat(),
            "vehicle_name": veh_name,
            "supplier_name": supp_name,
            "driver_details": driver_info,
            "gross_amount": f"{gross_val:.2f}",
            "discount_amount": f"{disc_val:.2f}",
            "promo_code": req.promo_code,
            "raw_order": raw_order,
        }


        return CarBookingResponse(
            status="confirmed",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            meta_data=meta_data,
            data=data_section,
        )

    except HTTPException:
        raise
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
