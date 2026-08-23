"""
FastAPI Route Controllers for Duffel REST API (Flights, Stays, Cars).
"""

import glob
import json
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status

from ..client import DuffelClient
from ..models.common import CabinClass, Passenger, Payment
from ..models.flights import FlightSliceQuery
from .schemas import (
    AnalyzeQueriesResponse,
    FlightBookingRequest,
    FlightBookingResponse,
    HealthCheckResponse,
    OptimizedFlightSearchRequest,
    OptimizedFlightSearchResponse,
)

router = APIRouter(prefix="/api/v1", tags=["Duffel REST API"])


def get_duffel_client() -> DuffelClient:
    """Dependency helper to return configured DuffelClient."""
    token = os.environ.get("DUFFEL_API_TOKEN", "")
    return DuffelClient(api_token=token, debug=False)


@router.get("/health", response_model=HealthCheckResponse, summary="System Health Check")
def health_check():
    """Returns system status, Duffel API configuration, and Redis cache connection state."""
    client = get_duffel_client()
    redis_enabled = client.cache.enabled if client.cache else False
    redis_status = "Connected" if (client.cache and client.cache.redis_client is not None) else (
        "In-Memory Fallback" if redis_enabled else "Disabled"
    )

    return HealthCheckResponse(
        status="ok",
        version="1.0.0",
        duffel_token_configured=bool(client.config.api_token),
        redis_cache_enabled=redis_enabled,
        redis_cache_status=redis_status,
    )


@router.post("/flights/analyze-queries", response_model=AnalyzeQueriesResponse, summary="Pre-Analyze Candidate Search Queries")
def analyze_candidate_queries(req: OptimizedFlightSearchRequest):
    """
    Pre-analyzes candidate date pairs to estimate Duffel API calls vs Redis Cache hits (Tier-1 vs Tier-2 breakdown).
    """
    client = get_duffel_client()
    try:
        passengers = [Passenger(type="adult") for _ in range(req.passengers_count)]
        cabin_enum = CabinClass(req.cabin_class.lower())

        analysis = client.flights.analyze_candidate_queries(
            origin=req.origin,
            destination=req.destination,
            target_date=req.target_date,
            target_return_date=req.target_return_date,
            min_duration_days=req.min_duration_days,
            max_duration_days=req.max_duration_days,
            flex_days=req.flex_days,
            passengers=passengers,
            cabin_class=cabin_enum,
        )
        return AnalyzeQueriesResponse(**analysis)
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error analyzing candidate queries: {str(err)}"
        )


@router.post("/flights/search-optimized", response_model=OptimizedFlightSearchResponse, summary="Optimized Flexible Multi-Day Flight Search")
def search_optimized_flights(req: OptimizedFlightSearchRequest):
    """
    Executes flexible multi-day flight search optimization.
    - Serves from Tier-1 Aggregated Cache (0ms) when available.
    - Computes category highlights (overall cheapest, cheapest non-stop, shortest non-stop, 1-stop, 2-stop, shortest overall, favorite airline).
    - Returns top 10 cheapest non-stop, top 10 shortest non-stop, and top 40 overall offers.
    - Automatically exports JSON report to `outputs/<hash>_search_results.json`.
    """
    client = get_duffel_client()
    try:
        passengers = [Passenger(type="adult") for _ in range(req.passengers_count)]
        cabin_enum = CabinClass(req.cabin_class.lower())

        offers = client.flights.search_optimized(
            origin=req.origin,
            destination=req.destination,
            target_date=req.target_date,
            target_return_date=req.target_return_date,
            min_duration_days=req.min_duration_days,
            max_duration_days=req.max_duration_days,
            flex_days=req.flex_days,
            passengers=passengers,
            cabin_class=cabin_enum,
            force_refresh=req.force_refresh,
        )

        from ..cli.menu import DuffelCLI
        cli = DuffelCLI()
        cli.client = client
        output_file = cli._export_search_results_json(offers, fav_airline=req.favorite_airline or "")

        output_json = getattr(offers, "output_json", {}) or {}
        highlights = getattr(offers, "category_highlights", None)
        if not highlights:
            highlights = client.flights.compute_category_highlights(offers, favorite_airline=req.favorite_airline or "")

        return OptimizedFlightSearchResponse(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            search_params={
                "origin": req.origin.upper(),
                "destination": req.destination.upper(),
                "target_date": req.target_date,
                "target_return_date": req.target_return_date,
                "min_duration_days": req.min_duration_days,
                "max_duration_days": req.max_duration_days,
                "flex_days": req.flex_days,
                "cabin_class": req.cabin_class,
                "passengers_count": req.passengers_count,
                "favorite_airline": req.favorite_airline,
            },
            category_highlights=output_json.get("category_highlights", highlights),
            total_offers_found=len(offers),
            cheapest_non_stop_offers=output_json.get("cheapest_non_stop_offers", []),
            shortest_non_stop_offers=output_json.get("shortest_non_stop_offers", []),
            top_offers=output_json.get("top_offers", []),
            performance_metrics=client.http_client.get_metrics_summary(),
            cache_metrics=client.cache.get_metrics_summary() if client.cache else {},
            output_file=output_file,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing optimized flight search: {str(err)}"
        )


@router.get("/flights/results/{hash_id}", summary="Retrieve Saved JSON Search Report")
def get_search_result_file(
    hash_id: str = Path(..., description="Unique filename hash ID or 'latest'")
):
    """
    Fetches pre-computed search results JSON report from the `outputs/` folder by hash ID or 'latest'.
    """
    output_dir = "outputs"
    if hash_id == "latest" or hash_id == "search_results":
        filepath = os.path.join(output_dir, "search_results.json")
    else:
        pattern = os.path.join(output_dir, f"*{hash_id}*.json")
        matches = glob.glob(pattern)
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No search results JSON report found matching hash '{hash_id}'."
            )
        filepath = matches[0]

    if not os.path.exists(filepath):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Search result report file '{filepath}' does not exist."
        )

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading search results file: {str(err)}"
        )


@router.post("/flights/book", response_model=FlightBookingResponse, summary="Book Flight Offer")
def book_flight(req: FlightBookingRequest):
    """
    Books a flight offer on Duffel by offer_id.
    Executes order creation with Duffel API, returning booking reference (PNR) and order confirmation.
    """
    client = get_duffel_client()
    try:
        passengers = []
        for p in req.passengers:
            passengers.append(Passenger(
                type=p.type,
                given_name=p.first_name or "John",
                family_name=p.last_name or "Doe",
                email=p.email or "passenger@example.com",
                phone_number=p.phone_number or "+14155552671",
                born_on=p.born_on or "1990-01-01",
                title=p.title or "mr",
                gender=p.gender or "m",
            ))

        payment_obj = None
        if req.payment:
            payment_obj = Payment(
                type=req.payment.type,
                currency=req.payment.currency,
                amount=req.payment.amount
            )

        order = client.flights.create_order(
            offer_id=req.offer_id,
            passengers=passengers,
            payments=[payment_obj] if payment_obj else None
        )

        passengers_summary = []
        for p in getattr(order, "passengers", []):
            passengers_summary.append({
                "id": getattr(p, "id", ""),
                "name": f"{getattr(p, 'given_name', '')} {getattr(p, 'family_name', '')}".strip(),
                "type": getattr(p, "type", ""),
            })

        slices_summary = []
        for s in getattr(order, "slices", []):
            slices_summary.append({
                "origin": getattr(s, "origin", {}).get("iata_code") if isinstance(getattr(s, "origin", {}), dict) else getattr(s, "origin", ""),
                "destination": getattr(s, "destination", {}).get("iata_code") if isinstance(getattr(s, "destination", {}), dict) else getattr(s, "destination", ""),
                "duration": getattr(s, "duration", ""),
            })

        booking_ref = getattr(order, "booking_reference", "") or getattr(order, "id", "")

        return FlightBookingResponse(
            status="confirmed",
            message="Flight order successfully created and confirmed.",
            order_id=getattr(order, "id", ""),
            booking_reference=booking_ref,
            total_amount=str(getattr(order, "total_amount", "0.00")),
            total_currency=getattr(order, "total_currency", "USD"),
            created_at=getattr(order, "created_at", datetime.now().isoformat()),
            passengers=passengers_summary,
            slices=slices_summary,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Flight booking failed: {str(err)}"
        )
