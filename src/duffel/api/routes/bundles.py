"""
Bundled Travel Package Route Controllers for Duffel REST API.
"""

import glob
import json
import os
from datetime import datetime

from fastapi import APIRouter, HTTPException, Path, Query, status

from ...exceptions import DuffelException
from ...models.common import Passenger, Payment
from ..schemas import (
    BundleBookingRequest,
    BundleBookingResponse,
    BundleSearchRequest,
    BundleSearchResponse,
)
from . import common

router = APIRouter(tags=["Bundles (Travel Packages) API"])

VALID_BUNDLE_TYPES = {"flights", "hotels", "cars"}


def normalize_bundle_types(bundle_types) -> list[str]:
    """Normalizes bundle_types input ('all', a comma-separated string, or a list) into a list of valid types."""
    if bundle_types is None or bundle_types == "all" or bundle_types == ["all"]:
        return ["flights", "hotels", "cars"]
    types = bundle_types.split(",") if isinstance(bundle_types, str) else list(bundle_types)
    normalized = [t.strip().lower() for t in types if t and t.strip()]
    invalid = [t for t in normalized if t not in VALID_BUNDLE_TYPES]
    if invalid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid bundle_types value(s): {invalid}. Must be one of {sorted(VALID_BUNDLE_TYPES)} or 'all'.",
        )
    return normalized or ["flights", "hotels", "cars"]


@router.post("/bundles/search", response_model=BundleSearchResponse, summary="Search Bundled Travel Packages")
def search_bundles_endpoint(req: BundleSearchRequest):
    """
    Search for combined Flight + Hotel Stay + Car Rental travel package bundles.
    Computes combined package pricing, 5% package savings, category highlights, caches in Redis, and exports JSON report.
    """
    client = common.get_duffel_client()
    try:
        if not hasattr(client, "bundles"):
            from ...services.bundles import BundlesService
            client.bundles = BundlesService(client.http_client, cache=client.cache, adapter=client.adapter, client=client)

        selected_types = normalize_bundle_types(req.bundle_types)

        result = client.bundles.search_bundle(
            origin=req.origin,
            destination=req.destination,
            departure_date=req.departure_date,
            return_date=req.return_date,
            passengers_count=req.passengers_count,
            cabin_class=req.cabin_class,
            rooms=req.rooms,
            driver_age=req.driver_age,
            force_refresh=req.force_refresh,
            selected_types=selected_types,
        )
        return BundleSearchResponse(**result)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Bundle search failed: Package search could not be completed."
        )




@router.get("/bundles/search", response_model=BundleSearchResponse, summary="Search Bundled Travel Packages (GET)")
def get_search_bundles_endpoint(
    origin: str = Query(..., description="Origin Airport IATA code e.g. ATL"),
    destination: str = Query(..., description="Destination Airport IATA code e.g. CDG"),
    departure_date: str = Query(..., description="Departure date YYYY-MM-DD"),
    return_date: str = Query(..., description="Return date YYYY-MM-DD"),
    passengers_count: int = Query(1, ge=1, le=9, description="Number of adult passengers"),
    cabin_class: str = Query("economy", description="Cabin class"),
    rooms: int = Query(1, ge=1, le=10, description="Hotel rooms"),
    driver_age: int = Query(30, ge=18, le=99, description="Driver age"),
    bundle_types: str = Query("all", description="Comma-separated types to include: flights,hotels,cars or 'all'"),
    force_refresh: bool = Query(False, description="Bypass cache"),
):
    """HTTP GET endpoint for bundled travel package search using URL query parameters."""
    parsed_bundle_types = [t.strip() for t in bundle_types.split(",")] if bundle_types != "all" else "all"
    return search_bundles_endpoint(
        BundleSearchRequest(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers_count=passengers_count,
            cabin_class=cabin_class,
            rooms=rooms,
            driver_age=driver_age,
            bundle_types=parsed_bundle_types,
            force_refresh=force_refresh,
        )
    )


@router.post("/bundles/book", response_model=BundleBookingResponse, summary="Book Bundled Travel Package")
@router.post("/bundles/orders", response_model=BundleBookingResponse, summary="Book Bundled Travel Package (Orders Alias)")
def book_bundle_endpoint(req: BundleBookingRequest):
    """Creates a combined Flight + Hotel + Car Rental package order."""
    client = common.get_duffel_client()
    try:
        if not hasattr(client, "bundles"):
            from ...services.bundles import BundlesService
            client.bundles = BundlesService(client.http_client, cache=client.cache, adapter=client.adapter, client=client)

        passengers_objs = []
        for p in req.passengers:
            g_name = p.given_name or p.first_name or "John"
            f_name = p.family_name or p.last_name or "Doe"
            passengers_objs.append(Passenger(
                id=p.id,
                type=p.type or "adult",
                given_name=g_name,
                family_name=f_name,
                email=p.email or "passenger@example.com",
                phone_number=p.phone_number or "+14155552671",
                born_on=p.born_on or "1990-01-01",
            ))

        payment_objs = []
        raw_payments = req.payments or ([req.payment] if req.payment else [])
        for pym in raw_payments:
            payment_objs.append(Payment(
                type=pym.type or "balance",
                currency=pym.currency or "USD",
                amount=pym.amount or "0.00",
            ))

        res = client.bundles.create_bundle_order(
            flight_offer_id=req.flight_offer_id,
            stay_quote_id=req.stay_quote_id,
            car_offer_id=req.car_offer_id,
            passengers=passengers_objs,
            guests=req.guests,
            driver_details=req.driver_details,
            payments=payment_objs,
            promo_code=req.promo_code,
            discount_amount=req.discount_amount,
        )

        return BundleBookingResponse(**res)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Bundled package booking failed: {str(err)}"
        )


@router.get("/bundles/orders/{bundle_order_id}", summary="Get Bundled Package Order Details")
def get_bundle_order_endpoint(bundle_order_id: str = Path(..., description="Bundle order ID")):
    """Retrieves combined travel package bundle order details by order ID."""
    client = common.get_duffel_client()
    try:
        from ...db.order_dao import OrderDAO
        order_dao = OrderDAO(config=client.config)
        res = order_dao.get_bundle_order_by_id(bundle_order_id)
        if not res:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Bundle order '{bundle_order_id}' not found."
            )
        return {"status": "success", "bundle_order": res}
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving bundle order '{bundle_order_id}': {str(err)}"
        )


@router.get("/bundles/results/{hash_id}", summary="Retrieve Saved JSON Bundle Search Report")
def get_bundle_result_file(
    hash_id: str = Path(..., description="Unique filename hash ID or 'latest'")
):
    """Fetches pre-computed bundle search results JSON report from outputs/ folder."""
    output_dir = "outputs"
    if hash_id == "latest":
        matches = glob.glob(os.path.join(output_dir, "*_bundle_results.json"))
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No bundle search results JSON report found."
            )
        filepath = max(matches, key=os.path.getmtime)
    else:
        pattern = os.path.join(output_dir, f"*{hash_id}*.json")
        matches = glob.glob(pattern)
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No bundle search results report found matching hash '{hash_id}'."
            )
        filepath = matches[0]

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading bundle results file: {str(err)}"
        )
