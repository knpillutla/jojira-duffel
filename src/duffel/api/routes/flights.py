"""
Flight Route Controllers for Duffel REST API.
"""

import glob
import json
import os
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Path, Query, Request, status

from ...exceptions import DuffelAPIError, DuffelException
from ...models.common import CabinClass, Passenger, Payment
from . import common
from ..schemas import (
    AnalyzeQueriesResponse,
    FlightBookingRequest,
    FlightBookingResponse,
    NaturalLanguageFlightSearchRequest,
    OptimizedFlightSearchRequest,
    OptimizedFlightSearchResponse,
    OrderPaymentRequest,
    StandardFlightSearchRequest,
)

router = APIRouter(tags=["Flights API"])


@router.post("/flights/analyze-queries", response_model=AnalyzeQueriesResponse, summary="Pre-Analyze Candidate Search Queries")
def analyze_candidate_queries(req: OptimizedFlightSearchRequest):
    """
    Pre-analyzes candidate date pairs to estimate Duffel API calls vs Redis Cache hits (Tier-1 vs Tier-2 breakdown).
    """
    client = common.get_duffel_client()
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
    """
    client = common.get_duffel_client()
    try:
        parsed_prompt = {}
        parsed_slice = {}
        if req.prompt:
            from ...cli.parser import PromptExtractor
            parsed_prompt = PromptExtractor.extract_flight_info(req.prompt)
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
        missing = []
        if not origin:
            missing.append("origin")
        if not destination:
            missing.append("destination")
        if not target_date:
            missing.append("target_date")
        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "prompt must include an origin, destination, and travel month or date", "missing_fields": missing}
            )

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

        # Determine trip_type
        if req.trip_type and str(req.trip_type).lower() in ["one_way", "oneway", "one-way"]:
            target_return_date = None
            trip_type_val = "one_way"
        elif not target_return_date:
            target_return_date = None
            trip_type_val = "one_way"
        else:
            trip_type_val = "round_trip"

        from ...cli.menu import DuffelCLI
        cli = DuffelCLI()
        cli.client = client
        search_params = {
            "trip_type": trip_type_val,
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

        try:
            from ...services.locations import resolve_geo_location
            orig_geo = resolve_geo_location(origin)
            dest_geo = resolve_geo_location(destination)
            flight_geo = {
                "origin": {"code": origin, **orig_geo},
                "destination": {"code": destination, **dest_geo},
            }
        except Exception:
            flight_geo = None

        meta_data = {
            "type": "flights",
            "trip_type": trip_type_val,
            "search_prompt": req.prompt or "",
            "search_params": search_params,
            "geo_location": flight_geo,
        }


        data_section = {
            "total_offers_found": len(offers),
            "category_highlights": output_json.get("category_highlights", highlights),
            "lowest_non_stop_offers": output_json.get("lowest_non_stop_offers", output_json.get("cheapest_non_stop_offers", [])),
            "shortest_non_stop_offers": output_json.get("shortest_non_stop_offers", []),
            "top_offers": output_json.get("top_offers", []),
            "performance_metrics": client.http_client.get_metrics_summary(),
            "cache_metrics": client.cache.get_metrics_summary() if client.cache else {},
            "output_file": output_file,
        }

        return OptimizedFlightSearchResponse(
            status="success",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            meta_data=meta_data,
            data=data_section,
        )


    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing optimized flight search: {str(err)}"
        )


@router.post("/flights/search", response_model=OptimizedFlightSearchResponse, summary="Standard Exact-Date Flight Search")
@router.post("/flights/search-standard", response_model=OptimizedFlightSearchResponse, summary="Standard Flight Search (Exact Dates)")
@router.post("/flights/search-exact", response_model=OptimizedFlightSearchResponse, summary="Standard Exact-Date Flight Search (Alias)")
def search_exact_flights(req: StandardFlightSearchRequest):
    """
    Executes standard exact-date flight search for specific departure and return dates.
    """
    client = common.get_duffel_client()
    try:
        parsed_prompt = {}
        parsed_slice = {}
        if req.prompt:
            from ...cli.parser import PromptExtractor
            parsed_prompt = PromptExtractor.extract_flight_info(req.prompt)
            parsed_slice = (parsed_prompt.get("slices") or [{}])[0]

        origin = req.origin or parsed_slice.get("origin")
        destination = req.destination or parsed_slice.get("destination")
        dep_date = req.departure_date or req.target_date or parsed_slice.get("departure_date")
        ret_date = req.return_date or req.target_return_date or parsed_prompt.get("target_return_date")

        # Determine trip_type
        if req.trip_type and str(req.trip_type).lower() in ["one_way", "oneway", "one-way"]:
            ret_date = None
            trip_type_val = "one_way"
        elif not ret_date:
            ret_date = None
            trip_type_val = "one_way"
        else:
            trip_type_val = "round_trip"

        missing = []
        if not origin:
            missing.append("origin")
        if not destination:
            missing.append("destination")
        if not dep_date:
            missing.append("departure_date")

        if missing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "Missing required fields", "missing_fields": missing}
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

        from ...cli.menu import DuffelCLI
        cli = DuffelCLI()
        cli.client = client
        search_params = {
            "trip_type": trip_type_val,
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

        try:
            from ...services.locations import resolve_geo_location
            orig_geo = resolve_geo_location(origin)
            dest_geo = resolve_geo_location(destination)
            flight_geo = {
                "origin": {"code": origin, **orig_geo},
                "destination": {"code": destination, **dest_geo},
            }
        except Exception:
            flight_geo = None

        meta_data = {
            "type": "flights",
            "trip_type": trip_type_val,
            "search_prompt": req.prompt or f"{origin} -> {destination} ({dep_date})",
            "search_params": search_params,
            "geo_location": flight_geo,
        }


        raw_offers = [o.to_dict() if hasattr(o, "to_dict") else getattr(o, "__dict__", {}) for o in offers[:50]]

        data_section = {
            "total_offers_found": len(offers),
            "offers": top_offers,
            "category_highlights": output_json.get("category_highlights", highlights),
            "lowest_non_stop_offers": cheapest_non_stop,
            "shortest_non_stop_offers": shortest_non_stop,
            "top_offers": top_offers,
            "raw_offers": raw_offers,
            "performance_metrics": (
                client.http_client.get_metrics_summary() if hasattr(client, "http_client") and hasattr(client.http_client, "get_metrics_summary")
                else (client.get_metrics_summary() if hasattr(client, "get_metrics_summary") else {})
            ),
            "cache_metrics": getattr(client.cache, "get_metrics_summary", lambda: {})() if getattr(client, "cache", None) else {},
            "output_file": output_file,
        }

        return OptimizedFlightSearchResponse(
            status="success",
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            meta_data=meta_data,
            data=data_section,
        )

    except HTTPException:
        raise
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error executing exact-date flight search: {str(err)}"
        )


@router.get("/flights/search", response_model=OptimizedFlightSearchResponse, summary="Standard Exact-Date Flight Search (GET)")
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
    """HTTP GET endpoint for standard exact-date flight search using URL query parameters."""
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


@router.post("/flights/search-natural-language", response_model=OptimizedFlightSearchResponse, summary="Natural-Language Flight Search")
def search_natural_language_flights(req: NaturalLanguageFlightSearchRequest):
    """Resolve a natural-language flight request with Gemini and run optimized search."""
    try:
        return search_optimized_flights(
            OptimizedFlightSearchRequest(
                prompt=req.prompt,
                favorite_airline=req.favorite_airline,
                force_refresh=req.force_refresh,
            )
        )
    except HTTPException as http_err:
        raise http_err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(err)
        )


@router.get("/flights/results/{hash_id}", summary="Retrieve Saved JSON Search Report")
def get_search_result_file(
    hash_id: str = Path(..., description="Unique filename hash ID or 'latest'")
):
    """Fetches pre-computed search results JSON report from the outputs/ folder."""
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


@router.get("/flights/offers/{offer_id}", summary="Get Verified Live Offer Details")
def get_flight_offer_details(offer_id: str = Path(..., description="Duffel offer ID e.g. off_0000...")):
    """Fetches verified live flight offer details from Duffel API."""
    if offer_id.startswith("off_duffel_") or offer_id.startswith("mock_"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Offer ID '{offer_id}' is a sample demo offer. Please execute a live flight search to view real Duffel offers."
        )

    client = common.get_duffel_client()
    try:
        real_offer = client.flights.get_offer(offer_id)
        if not real_offer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Offer '{offer_id}' not found on Duffel API."
            )

        offer_dict = real_offer.to_dict() if hasattr(real_offer, "to_dict") else getattr(real_offer, "__dict__", {})
        tot = float(getattr(real_offer, "total_amount", 0.0) or 0.0)
        tax = float(getattr(real_offer, "tax_amount", 0.0) or 0.0)
        raw_base = getattr(real_offer, "base_amount", None)
        try:
            base = float(raw_base) if raw_base is not None and str(raw_base).strip() not in ["", "0", "0.00", "None"] else 0.0
        except Exception:
            base = 0.0
        if base <= 0.0 and tot > 0.0:
            base = max(0.0, tot - tax) if tax > 0.0 else tot

        return {
            "status": "success",
            "offer_id": getattr(real_offer, "id", offer_id),
            "total_amount": f"{tot:.2f}",
            "total_currency": getattr(real_offer, "total_currency", "USD"),
            "base_amount": f"{base:.2f}",
            "tax_amount": f"{tax:.2f}",
            "expires_at": getattr(real_offer, "expires_at", None),
            "offer_details": offer_dict
        }
    except HTTPException as http_err:
        raise http_err
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Error fetching live Duffel offer '{offer_id}': {str(err)}"
        )


@router.post("/flights/book", response_model=FlightBookingResponse, summary="Book Flight Offer")
@router.post("/orders", response_model=FlightBookingResponse, summary="Book Flight Offer (Orders Alias)")
def book_flight(req: FlightBookingRequest, request: Request = None):
    """Books a flight offer on Duffel by offer_id or selected_offers list."""
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
                detail=f"Offer ID '{target_offer_id}' is a sample demo offer. Please execute a live flight search to book real flights."
            )

        real_offer = None
        requires_instant = False
        try:
            real_offer = client.flights.get_offer(offer_ids[0])
            if real_offer:
                payment_req = getattr(real_offer, "payment_requirements", {}) if hasattr(real_offer, "payment_requirements") else (real_offer.raw.get("payment_requirements", {}) if isinstance(getattr(real_offer, "raw", None), dict) else {})
                if isinstance(payment_req, dict):
                    requires_instant = bool(payment_req.get("requires_instant_payment", False))

                if hasattr(real_offer, "total_amount") and real_offer.total_amount:
                    try:
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
                                        "message": f"The airline updated the price from {curr_display} {user_price:.2f} to {curr_display} {live_price:.2f}. Please confirm the updated price before completing booking.",
                                        "old_price": f"{user_price:.2f}",
                                        "new_price": f"{live_price:.2f}",
                                        "currency": curr_display
                                    }
                                )
                    except (ValueError, TypeError):
                        pass
        except HTTPException:
            raise
        except Exception:
            pass

        if getattr(client.config, "force_instant_booking", False):
            order_type = "instant"
        elif req.type and req.type.lower() == "instant":
            order_type = "instant"
        elif requires_instant:
            order_type = "instant"
        else:
            order_type = "hold"

        passengers = []
        for i, p in enumerate(req.passengers):
            g_name = p.given_name or p.first_name or "John"
            f_name = p.family_name or p.last_name or "Doe"
            pid = p.id or getattr(p, "passenger_id", None) or None
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
            type=order_type,
            idempotency_key=idempotency_key
        )

        raw_status = getattr(order, "status", "confirmed")
        order_status = str(raw_status) if isinstance(raw_status, str) else "confirmed"

        if order_type == "hold" and payment_objs and getattr(order, "id", None):
            try:
                pay_res = client.flights.pay_order(
                    order_id=order.id,
                    payment=payment_objs[0]
                )
                if isinstance(pay_res, dict) and pay_res.get("status") and isinstance(pay_res["status"], str):
                    order_status = pay_res["status"]
            except Exception as pay_err:
                print(f"[STRATEGY A PAYMENT NOTICE]: Created hold order '{order.id}', order payment attempt: {pay_err}")

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

        try:
            from ...db.order_dao import OrderDAO
            order_dao = OrderDAO(config=client.config)
            payment_req_by = None
            if real_offer and hasattr(real_offer, "payment_requirements") and isinstance(real_offer.payment_requirements, dict):
                payment_req_by = real_offer.payment_requirements.get("payment_required_by")

            cust_email = "customer@example.com"
            if req.passengers:
                cust_email = req.passengers[0].email or cust_email

            tot_val = float(getattr(order, "total_amount", "0.00") or 0.0)
            disc_val = float(req.discount_amount or 0.0)
            gross_val = tot_val + disc_val

            target_user_id = req.user_id
            auth_hdr = request.headers.get("Authorization", "")
            if not target_user_id and auth_hdr.startswith("Bearer "):
                try:
                    from ...user_service.api.routes.auth import _verify_jwt_token
                    from ...user_service.config import UserServiceConfig
                    token_str = auth_hdr.split(" ", 1)[1].strip()
                    token_payload = _verify_jwt_token(token_str, UserServiceConfig().jwt_secret)
                    if token_payload and token_payload.get("sub"):
                        target_user_id = token_payload["sub"]
                except Exception:
                    pass

            order_dao.save_hold_order(
                duffel_order_id=getattr(order, "id", ""),
                booking_reference=booking_ref,
                total_amount=str(getattr(order, "total_amount", "0.00")),
                total_currency=getattr(order, "total_currency", "USD"),
                order_type=order_type,
                status=order_status,
                payment_method=payment_objs[0].type if payment_objs else "balance",
                payment_required_by=payment_req_by,
                email_recipient=cust_email,
                passengers=passengers_summary,
                slices=slices_summary,
                payment_status="paid" if order_status in ["confirmed", "paid"] else "pending",
                email_confirmation_status="pending",
                promo_code=req.promo_code,
                gross_amount=f"{gross_val:.2f}",
                discount_amount=f"{disc_val:.2f}",
                user_id=target_user_id,
            )

        except Exception as db_err:
            print(f"[ORDER DAO NOTICE] Failed saving order to database: {db_err}")

        if order_type == "hold" or order_status == "hold":
            try:
                from ...services.service_bus import ServiceBusPublisher
                publisher = ServiceBusPublisher(config=client.config)
                payment_dict = payment_objs[0].to_dict() if payment_objs else {"type": "balance", "amount": str(getattr(order, "total_amount", "0.00")), "currency": str(getattr(order, "total_currency", "USD"))}
                publisher.publish_order_hold_event(
                    order_id=getattr(order, "id", ""),
                    booking_reference=booking_ref,
                    total_amount=str(getattr(order, "total_amount", "0.00")),
                    total_currency=getattr(order, "total_currency", "USD"),
                    passengers=passengers_summary,
                    slices=slices_summary,
                    payment=payment_dict,
                    payment_required_by=payment_req_by
                )
            except Exception as sb_err:
                print(f"[SERVICE BUS NOTICE] Failed to publish order hold event: {sb_err}")

        msg = (
            "Flight hold order created. Physical seats and price locked."
            if order_type == "hold" and order_status == "hold"
            else "Flight order successfully created and confirmed."
        )

        tot_val = float(getattr(order, "total_amount", "0.00") or 0.0)
        disc_val = float(req.discount_amount or 0.0)
        gross_val = tot_val + disc_val

        meta_data = {
            "type": "flights",
            "order_id": getattr(order, "id", ""),
            "booking_reference": booking_ref,
            "promo_code": req.promo_code,
            "discount_amount": f"{disc_val:.2f}",
            "gross_amount": f"{gross_val:.2f}",
            "geo_location": None,
        }

        ord_dict = order.to_dict() if hasattr(order, "to_dict") else getattr(order, "__dict__", {})
        raw_order = getattr(order, "raw", None) or ord_dict.get("raw") or ord_dict

        data_section = {
            **ord_dict,
            "order_id": getattr(order, "id", ""),
            "booking_reference": booking_ref,
            "message": msg,
            "total_amount": str(getattr(order, "total_amount", "0.00")),
            "total_currency": getattr(order, "total_currency", "USD"),
            "created_at": getattr(order, "created_at", datetime.now().isoformat()),
            "passengers": passengers_summary,
            "slices": slices_summary,
            "gross_amount": f"{gross_val:.2f}",
            "discount_amount": f"{disc_val:.2f}",
            "promo_code": req.promo_code,
            "raw_order": raw_order,
        }


        return FlightBookingResponse(
            status=order_status,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            meta_data=meta_data,
            data=data_section,
        )

    except HTTPException:
        raise
    except DuffelAPIError as err:
        status_code = err.status_code if (err.status_code and err.status_code >= 400 and err.status_code <= 599) else status.HTTP_400_BAD_REQUEST
        if 500 <= status_code <= 599:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE
            msg = "Airline reservation system experienced a temporary service disruption. No payment was charged. Please try booking again in a few moments."
        else:
            msg = f"Flight booking failed: {str(err)}"
        raise HTTPException(
            status_code=status_code,
            detail=msg
        )
    except DuffelException as err:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Airline reservation system experienced a temporary service disruption. No payment was charged. Please try booking again in a few moments."
        )
    except Exception as err:
        err_str = str(err)
        if "timed out" in err_str.lower() or "timeout" in err_str.lower() or "connection" in err_str.lower() or "503" in err_str:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Airline reservation system experienced a temporary service disruption. No payment was charged. Please try booking again in a few moments."
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Flight booking failed: {err_str}"
        )


@router.post("/air/orders/{order_id}/payments", summary="Pay Hold Order (Strategy A Step 2)")
@router.post("/orders/{order_id}/payments", summary="Pay Hold Order Alias")
def pay_hold_order(order_id: str, req: OrderPaymentRequest):
    """Executes payment for an existing Duffel hold order."""
    client = common.get_duffel_client()
    try:
        payment_input = req.payment or (req.payments[0] if req.payments else None)
        payment_obj = None
        if payment_input:
            raw_data = {}
            token_val = payment_input.card_token or payment_input.token or payment_input.payment_method_id
            if token_val:
                raw_data["card_token"] = token_val
            if payment_input.card_id:
                raw_data["card_id"] = payment_input.card_id
            payment_obj = Payment(
                type=payment_input.type or "balance",
                currency=payment_input.currency or "USD",
                amount=payment_input.amount or "0.00",
                raw=raw_data
            )
        res = client.flights.pay_order(order_id=order_id, payment=payment_obj)
        return {
            "status": "success",
            "message": f"Payment successfully created for hold order '{order_id}'.",
            "order_id": order_id,
            "payment_details": res
        }
    except HTTPException:
        raise
    except DuffelAPIError as err:
        status_code = err.status_code if err.status_code in [400, 401, 403, 404, 409, 422, 429, 500, 502, 503, 504] else status.HTTP_400_BAD_REQUEST
        raise HTTPException(
            status_code=status_code,
            detail=f"Hold order payment failed: {str(err)}"
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hold order payment failed: {str(err)}"
        )
