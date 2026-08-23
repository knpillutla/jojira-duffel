"""
FastAPI Route Controllers for Duffel REST API (Flights, Stays, Cars).
"""

import glob
import json
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from ..client import DuffelClient
from ..models.common import CabinClass, Passenger, Payment
from ..models.flights import FlightSliceQuery
from .schemas import (
    AnalyzeQueriesResponse,
    ApiEndpointHelp,
    ApiHelpResponse,
    FlightBookingRequest,
    FlightBookingResponse,
    HealthCheckResponse,
    NaturalLanguageFlightSearchRequest,
    OptimizedFlightSearchRequest,
    OptimizedFlightSearchResponse,
    PaymentMethodOption,
    PaymentMethodsResponse,
    StandardFlightSearchRequest,
)

router = APIRouter(prefix="/api/v1", tags=["Duffel REST API"])


def get_duffel_client() -> DuffelClient:
    """Dependency helper to return configured DuffelClient."""
    token = os.environ.get("DUFFEL_API_TOKEN", "")
    return DuffelClient(api_token=token, debug=False)


@router.get("/health", response_model=HealthCheckResponse, summary="System Health Check")
def health_check():
    """Returns system status, timestamp, Duffel API configuration, and Redis cache connection state."""
    client = get_duffel_client()
    redis_enabled = client.cache.enabled if client.cache else False
    redis_status = "Connected" if (client.cache and client.cache.redis_client is not None) else (
        "In-Memory Fallback" if redis_enabled else "Disabled"
    )

    return HealthCheckResponse(
        status="healthy",
        service="Jojira Duffel Integration API",
        version="1.0.0",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        duffel_token_configured=bool(client.config.api_token),
        redis_cache_enabled=redis_enabled,
        redis_cache_status=redis_status,
    )


@router.get("/help", response_model=ApiHelpResponse, summary="API Help & Documentation Index")
def get_api_help(request: Request):
    """
    Returns a complete directory of all available REST APIs, including API name, HTTP method, URL, description, request schema, and response schema.
    """
    base_url = str(request.base_url).rstrip("/")
    openapi = request.app.openapi()
    components_schemas = openapi.get("components", {}).get("schemas", {})

    def resolve_schema(schema_ref):
        if not isinstance(schema_ref, dict):
            return schema_ref
        if "$ref" in schema_ref:
            ref_name = schema_ref["$ref"].split("/")[-1]
            return components_schemas.get(ref_name, schema_ref)
        return schema_ref

    endpoints = []
    for path, methods in openapi.get("paths", {}).items():
        for method_name, spec in methods.items():
            method_str = method_name.upper()
            summary = spec.get("summary") or spec.get("operationId") or f"{method_str} {path}"
            description = spec.get("description") or spec.get("summary") or ""

            # Extract request schema
            request_schema = None
            if "requestBody" in spec:
                content = spec["requestBody"].get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                request_schema = resolve_schema(schema)
            elif "parameters" in spec:
                request_schema = {
                    "type": "query_parameters",
                    "parameters": spec["parameters"]
                }

            # Extract response schema (200 OK)
            response_schema = None
            responses = spec.get("responses", {})
            ok_res = responses.get("200") or responses.get(200)
            if ok_res:
                content = ok_res.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                response_schema = resolve_schema(schema)

            endpoints.append(ApiEndpointHelp(
                name=summary,
                method=method_str,
                path=path,
                url=f"{base_url}{path}",
                description=description,
                request_schema=request_schema,
                response_schema=response_schema,
            ))

    return ApiHelpResponse(
        service=openapi.get("info", {}).get("title", "Jojira Duffel REST API"),
        version=openapi.get("info", {}).get("version", "1.0.0"),
        base_url=base_url,
        interactive_docs_url=f"{base_url}/docs",
        total_endpoints=len(endpoints),
        endpoints=endpoints,
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
@router.post("/flights/search-standard", response_model=OptimizedFlightSearchResponse, summary="Standard Flight Search (Exact Dates)")
@router.post("/flights/search-exact", response_model=OptimizedFlightSearchResponse, summary="Exact Flight Search")
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
        parsed_prompt = {}
        parsed_slice = {}
        if req.prompt:
            from ..cli.parser import PromptExtractor
            parsed_prompt = PromptExtractor.extract_flight_info(req.prompt)
            # Handle missing fields gracefully with defaults instead of HTTP 400
            if not parsed_prompt.get("slices"):
                parsed_prompt["slices"] = [{"origin": req.origin or "ATL", "destination": req.destination or "CDG", "departure_date": req.target_date or "2026-10-01"}]
            if not parsed_prompt.get("min_duration_days"):
                parsed_prompt["min_duration_days"] = req.min_duration_days or 4
            if not parsed_prompt.get("max_duration_days"):
                parsed_prompt["max_duration_days"] = req.max_duration_days or 7
            parsed_slice = (parsed_prompt.get("slices") or [{}])[0]

        origin = req.origin or parsed_slice.get("origin")
        destination = req.destination or parsed_slice.get("destination")
        target_date = req.target_date or parsed_slice.get("departure_date")
        if not origin or not destination or not target_date:
            raise ValueError("prompt must include an origin, destination, and travel month or date")

        target_return_date = req.target_return_date or parsed_prompt.get("target_return_date")
        if not target_return_date and len(parsed_prompt.get("slices") or []) > 1:
            target_return_date = parsed_prompt["slices"][1].get("departure_date")

        duration_days = parsed_prompt.get("duration_days")
        if not target_return_date and duration_days:
            from datetime import timedelta
            target_return_date = (
                datetime.strptime(target_date, "%Y-%m-%d") + timedelta(days=duration_days)
            ).strftime("%Y-%m-%d")
        min_duration_days = req.min_duration_days
        max_duration_days = req.max_duration_days
        if req.prompt and duration_days and "min_duration_days" not in req.model_fields_set:
            min_duration_days = duration_days
        if req.prompt and duration_days and "max_duration_days" not in req.model_fields_set:
            max_duration_days = duration_days

        passengers = [Passenger(type="adult") for _ in range(req.passengers_count)]
        cabin_enum = CabinClass(req.cabin_class.lower())

        offers = client.flights.search_optimized(
            origin=origin,
            destination=destination,
            target_date=target_date,
            target_return_date=target_return_date,
            min_duration_days=min_duration_days,
            max_duration_days=max_duration_days,
            flex_days=req.flex_days,
            passengers=passengers,
            cabin_class=cabin_enum,
            force_refresh=req.force_refresh,
        )

        from ..cli.menu import DuffelCLI
        cli = DuffelCLI()
        cli.client = client
        search_params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "target_date": target_date,
            "target_return_date": target_return_date,
            "min_duration_days": min_duration_days,
            "max_duration_days": max_duration_days,
            "flex_days": req.flex_days,
            "cabin_class": req.cabin_class,
            "passengers_count": req.passengers_count,
            "favorite_airline": req.favorite_airline,
            "force_refresh": req.force_refresh,
        }
        output_file = cli._export_search_results_json(
            offers,
            fav_airline=req.favorite_airline or "",
            search_prompt=req.prompt or "",
            search_params=search_params,
        )

        output_json = getattr(offers, "output_json", {}) or {}
        highlights = getattr(offers, "category_highlights", None)
        if not highlights:
            highlights = client.flights.compute_category_highlights(offers, favorite_airline=req.favorite_airline or "")

        return OptimizedFlightSearchResponse(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            search_prompt=req.prompt or "",
            search_params=search_params,
            category_highlights=output_json.get("category_highlights", highlights),
            total_offers_found=len(offers),
            cheapest_non_stop_offers=output_json.get("cheapest_non_stop_offers", []),
            shortest_non_stop_offers=output_json.get("shortest_non_stop_offers", []),
            top_offers=output_json.get("top_offers", []),
            performance_metrics=client.http_client.get_metrics_summary(),
            cache_metrics=client.cache.get_metrics_summary() if client.cache else {},
            output_file=output_file,
        )
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing optimized flight search: {str(err)}"
        )


@router.post(
    "/flights/search",
    response_model=OptimizedFlightSearchResponse,
    summary="Standard Exact-Date Flight Search",
)
@router.post(
    "/flights/search-exact",
    response_model=OptimizedFlightSearchResponse,
    summary="Standard Exact-Date Flight Search (Alias)",
)
def search_exact_flights(req: StandardFlightSearchRequest):
    """
    Executes standard exact-date flight search for specific departure and return dates.
    - Serves from Redis cache (0ms) when available.
    - Computes category highlights (overall cheapest, cheapest non-stop, shortest non-stop, 1-stop, 2-stop, shortest overall, favorite airline).
    - Automatically exports JSON report to `outputs/<hash>_search_results.json`.
    """
    client = get_duffel_client()
    try:
        parsed_prompt = {}
        parsed_slice = {}
        if req.prompt:
            from ..cli.parser import PromptExtractor
            parsed_prompt = PromptExtractor.extract_flight_info(req.prompt)
            parsed_slice = (parsed_prompt.get("slices") or [{}])[0]

        origin = req.origin or parsed_slice.get("origin")
        destination = req.destination or parsed_slice.get("destination")
        dep_date = req.departure_date or req.target_date or parsed_slice.get("departure_date")
        ret_date = req.return_date or req.target_return_date or parsed_prompt.get("target_return_date")

        if not origin or not destination or not dep_date:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Search request must include origin, destination, and departure_date (or target_date)."
            )

        passengers = [Passenger(type="adult") for _ in range(req.passengers_count)]
        cabin_enum = CabinClass(req.cabin_class.lower())

        offers = client.flights.search_exact(
            origin=origin,
            destination=destination,
            departure_date=dep_date,
            return_date=ret_date,
            passengers=passengers,
            cabin_class=cabin_enum,
            force_refresh=req.force_refresh,
        )

        from ..cli.menu import DuffelCLI
        cli = DuffelCLI()
        cli.client = client
        search_params = {
            "origin": origin.upper(),
            "destination": destination.upper(),
            "departure_date": dep_date,
            "return_date": ret_date or "oneway",
            "cabin_class": req.cabin_class,
            "passengers_count": req.passengers_count,
            "favorite_airline": req.favorite_airline,
            "force_refresh": req.force_refresh,
        }
        output_file = cli._export_search_results_json(
            offers,
            fav_airline=req.favorite_airline or "",
            search_prompt=req.prompt or f"{origin} -> {destination} ({dep_date})",
            search_params=search_params,
        )

        output_json = getattr(offers, "output_json", {}) or {}
        highlights = getattr(offers, "category_highlights", None)
        if not highlights:
            highlights = client.flights.compute_category_highlights(offers, favorite_airline=req.favorite_airline or "")

        top_offers = output_json.get("top_offers")
        if top_offers is None:
            top_offers = [client.flights._build_offer_summary(o) for o in offers[:40] if o]

        cheapest_non_stop = output_json.get("cheapest_non_stop_offers")
        if cheapest_non_stop is None:
            non_stop_offers = [o for o in offers if (getattr(o, "max_connections", 0) == 0 or len(getattr(o, "slices", [{}])[0].get("segments", [])) <= 1)]
            sorted_non_stop = sorted(non_stop_offers, key=lambda o: float(getattr(o, "total_amount", 0.0) or 0.0))[:10]
            cheapest_non_stop = [client.flights._build_offer_summary(o) for o in sorted_non_stop if o]

        shortest_non_stop = output_json.get("shortest_non_stop_offers")
        if shortest_non_stop is None:
            non_stop_offers = [o for o in offers if (getattr(o, "max_connections", 0) == 0 or len(getattr(o, "slices", [{}])[0].get("segments", [])) <= 1)]
            sorted_shortest = sorted(non_stop_offers, key=lambda o: getattr(o, "duration_minutes", 99999))[:10]
            shortest_non_stop = [client.flights._build_offer_summary(o) for o in sorted_shortest if o]

        return OptimizedFlightSearchResponse(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            search_prompt=req.prompt or f"{origin} -> {destination} ({dep_date})",
            search_params=search_params,
            category_highlights=output_json.get("category_highlights", highlights),
            total_offers_found=len(offers),
            cheapest_non_stop_offers=cheapest_non_stop,
            shortest_non_stop_offers=shortest_non_stop,
            top_offers=top_offers,
            performance_metrics=client.http_client.get_metrics_summary(),
            cache_metrics=client.cache.get_metrics_summary() if client.cache else {},
            output_file=output_file,
        )
    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing exact-date flight search: {str(err)}"
        )


@router.get(
    "/flights/search",
    response_model=OptimizedFlightSearchResponse,
    summary="Standard Exact-Date Flight Search (GET)",
)
def get_search_exact_flights(
    origin: str = Query(..., description="Origin Airport IATA code e.g. LHR or ATL"),
    destination: str = Query(..., description="Destination Airport IATA code e.g. JFK or CDG"),
    departure_date: str = Query(..., description="Exact departure date in YYYY-MM-DD format"),
    return_date: Optional[str] = Query(None, description="Exact return date in YYYY-MM-DD format (for round-trip)"),
    passengers_count: int = Query(1, ge=1, le=9, description="Number of adult passengers"),
    cabin_class: str = Query("economy", description="Cabin class: economy, premium_economy, business, first"),
    max_connections: Optional[int] = Query(None, description="Maximum connections / stops allowed"),
    favorite_airline: Optional[str] = Query(None, description="Preferred favorite airline"),
    force_refresh: bool = Query(False, description="Set true to bypass cache and query Duffel live"),
):
    """
    HTTP GET endpoint for standard exact-date flight search using URL query parameters.
    Allows UI applications to execute flight searches via GET requests.
    """
    return search_exact_flights(
        StandardFlightSearchRequest(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers_count=passengers_count,
            cabin_class=cabin_class,
            max_connections=max_connections,
            favorite_airline=favorite_airline,
            force_refresh=force_refresh,
        )
    )


@router.post(
    "/flights/search-natural-language",
    response_model=OptimizedFlightSearchResponse,
    summary="Natural-Language Flight Search",
)
def search_natural_language_flights(req: NaturalLanguageFlightSearchRequest):
    """Resolve a natural-language flight request with Gemini and run optimized search."""
    return search_optimized_flights(
        OptimizedFlightSearchRequest(
            prompt=req.prompt,
            favorite_airline=req.favorite_airline,
            force_refresh=req.force_refresh,
        )
    )


@router.get("/flights/results/{hash_id}", summary="Retrieve Saved JSON Search Report")
def get_search_result_file(
    hash_id: str = Path(..., description="Unique filename hash ID or 'latest'")
):
    """
    Fetches pre-computed search results JSON report from the `outputs/` folder by hash ID or 'latest'.
    """
    output_dir = "outputs"
    if hash_id == "latest":
        matches = glob.glob(os.path.join(output_dir, "*_search_results.json"))
        if not matches:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No search results JSON report found."
            )
        filepath = max(matches, key=os.path.getmtime)
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
    Books a flight offer on Duffel by offer_id or selected_offers list.
    Executes order creation with Duffel API (type: 'instant' or 'hold'), returning booking reference (PNR) and order confirmation.
    Passes passenger and payment details directly to Duffel API.
    """
    client = get_duffel_client()
    try:
        offer_ids = req.selected_offers or ([req.offer_id] if req.offer_id else [])
        if not offer_ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either offer_id or selected_offers list must be provided in request body."
            )

        passengers = []
        for i, p in enumerate(req.passengers):
            g_name = p.given_name or p.first_name or "John"
            f_name = p.family_name or p.last_name or "Doe"
            pid = p.id or getattr(p, "passenger_id", None) or f"pas_00000000000000000{i+1}"
            passengers.append(Passenger(
                id=pid,
                type=p.type or "adult",
                given_name=g_name,
                family_name=f_name,
                email=p.email or "passenger@example.com",
                phone_number=p.phone_number or "+14155552671",
                born_on=p.born_on or "1990-01-01",
                title=p.title or "mr",
                gender=p.gender or "m",
            ))

        payment_objs = []
        payments_list = req.payments or ([req.payment] if req.payment else [])
        for pym in payments_list:
            raw_data = {}
            token_val = pym.card_token or pym.token or pym.payment_method_id
            if token_val:
                raw_data["card_token"] = token_val
                raw_data["token"] = token_val
            if pym.card_id:
                raw_data["card_id"] = pym.card_id
            if pym.customer_card_id:
                raw_data["customer_card_id"] = pym.customer_card_id

            payment_objs.append(Payment(
                type=pym.type or "balance",
                currency=pym.currency or "USD",
                amount=pym.amount or "0.00",
                raw=raw_data
            ))

        order = client.flights.create_order(
            selected_offers=offer_ids,
            passengers=passengers,
            payments=payment_objs if payment_objs else None,
            type=req.type or "instant"
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


@router.get("/payments/methods", response_model=PaymentMethodsResponse, summary="Get Supported Payment Methods")
@router.get("/flights/payment-methods", response_model=PaymentMethodsResponse, summary="Get Supported Flight Payment Methods")
def get_supported_payment_methods():
    """
    Returns all payment methods supported by the Duffel API.
    UI applications can invoke this endpoint to dynamically render payment options to users.
    """
    methods = [
        PaymentMethodOption(
            id="balance",
            name="Duffel Balance",
            description="Pay using your Duffel account balance or test environment balance",
            category="account",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="card",
            name="Credit or Debit Card",
            description="Pay instantly using credit or debit card tokenization",
            category="card",
            requires_card_details=True,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="customer_card",
            name="Saved Customer Card",
            description="Pay using a saved customer card on file",
            category="card",
            requires_card_details=False,
            requires_customer_card_id=True,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="arc_bsp_one_step",
            name="ARC / BSP Settlement",
            description="One-step cash settlement for ARC or BSP accredited travel agencies",
            category="agency",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="bank_transfer",
            name="Bank Transfer",
            description="Pay via standard electronic bank transfer",
            category="bank",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="instant_bank_transfer",
            name="Instant Bank Transfer",
            description="Pay via Open Banking instant bank transfer",
            category="bank",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="hold",
            name="Hold Reservation (Pay Later)",
            description="Reserve flight seats now without immediate payment and pay before expiration",
            category="reservation",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=True,
        ),
    ]

    return PaymentMethodsResponse(
        status="ok",
        default_method="balance",
        supported_payment_methods=methods,
    )
