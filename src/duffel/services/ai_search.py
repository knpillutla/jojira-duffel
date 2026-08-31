"""
AI Search Service - Intelligent API Router
Parses natural language prompts using LLM to determine which services to invoke,
then returns the response from the appropriate service or bundle.
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from ..cli.parser import PromptExtractor
from ..models.common import CabinClass, Passenger
from .base import BaseService


class AISearchService(BaseService):
    """
    Intelligent AI Search Service that:
    1. Parses natural language prompt using LLM
    2. Extracts search intent and selected service types
    3. Routes to appropriate service(s):
       - Single type → Call that service directly, return its response format
       - Multiple types → Call bundles service, return bundle response format
    4. Results ordered by total price ascending (top 20)
    """

    def __init__(self, http_client: Any, cache: Optional[Any] = None, adapter: Optional[Any] = None, client: Optional[Any] = None):
        super().__init__(http_client, cache=cache, adapter=adapter)
        self.client_app = client

    def search_ai(
        self,
        prompt: str,
        favorite_airline: str = "",
        force_refresh: bool = False,
        overrides: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """
        Execute intelligent AI search based on natural language prompt.
        
        Process:
        1. Extract search intent from prompt (which services, parameters)
        2. If single type: return that service's response format
        3. If multiple types: return bundle response format
        4. All sorted by total price ascending, top 20 results
        """
        overrides = overrides or {}
        
        # Step 1: Extract intent using LLM
        prompt = (prompt or "").lower().strip()
        user_loc = overrides.get("user_location")
        intent = PromptExtractor.extract_natural_intent(prompt, user_location=user_loc)
        selected_types = overrides.get("selected_types") or intent.get("selected_types") or ["flights"]
        
        # Normalize types to lowercase
        selected_types = [t.lower() for t in selected_types]
        
        # Extract parameters with overrides
        origin = (overrides.get("origin") or intent.get("origin") or "").upper()
        dest_candidate = (overrides.get("destination") or intent.get("destination") or "PARIS").strip().upper()
        try:
            from .locations import resolve_geo_location
            resolve_geo_location(dest_candidate)
            destination = dest_candidate
        except Exception:
            destination = "CDG"

        if "flights" in selected_types or len(selected_types) > 1:
            if not origin or origin == destination:
                origin = "JFK" if destination != "JFK" else "LHR"


        departure_date = overrides.get("departure_date") or intent.get("departure_date") or "2026-10-01"
        return_date = overrides.get("return_date") or intent.get("return_date") or "2026-10-08"

        # Immediate input validation before cache or Duffel API calls
        today_str = datetime.now().strftime("%Y-%m-%d")
        if departure_date and departure_date < today_str:
            err_msg = f"Departure date '{departure_date}' is in the past. Search dates must be today ({today_str}) or in the future."
            return {
                "status": "error",
                "error": "invalid_past_date",
                "message": err_msg,
                "meta_data": {
                    "type": "ai_search",
                    "search_type": selected_types[0] if selected_types else "flights",
                    "prompt": prompt,
                    "parsed_intent": intent,
                    "error": err_msg,
                },
                "data": {
                    "ai_summary": f"Cannot complete search: {err_msg}",
                    "category_highlights": {},
                    "search_type": selected_types[0] if selected_types else "flights",
                    "total_items": 0,
                    "offers": [],
                    "top_bundles": [],
                    "raw_data": {},
                },
            }

        if return_date and return_date < today_str:
            err_msg = f"Return date '{return_date}' is in the past. Search dates must be today ({today_str}) or in the future."
            return {
                "status": "error",
                "error": "invalid_past_date",
                "message": err_msg,
                "meta_data": {
                    "type": "ai_search",
                    "search_type": selected_types[0] if selected_types else "flights",
                    "prompt": prompt,
                    "parsed_intent": intent,
                    "error": err_msg,
                },
                "data": {
                    "ai_summary": f"Cannot complete search: {err_msg}",
                    "category_highlights": {},
                    "search_type": selected_types[0] if selected_types else "flights",
                    "total_items": 0,
                    "offers": [],
                    "top_bundles": [],
                    "raw_data": {},
                },
            }

        if departure_date and return_date and departure_date > return_date:
            err_msg = f"Departure date '{departure_date}' cannot be after return date '{return_date}'."
            return {
                "status": "error",
                "error": "invalid_date_range",
                "message": err_msg,
                "meta_data": {
                    "type": "ai_search",
                    "search_type": selected_types[0] if selected_types else "flights",
                    "prompt": prompt,
                    "parsed_intent": intent,
                    "error": err_msg,
                },
                "data": {
                    "ai_summary": f"Cannot complete search: {err_msg}",
                    "category_highlights": {},
                    "search_type": selected_types[0] if selected_types else "flights",
                    "total_items": 0,
                    "offers": [],
                    "top_bundles": [],
                    "raw_data": {},
                },
            }

        # Check for max 30 days date range window limit
        from_d_str = intent.get("from_date") or departure_date
        to_d_str = intent.get("to_date") or return_date
        if from_d_str and to_d_str:
            try:
                fd = datetime.strptime(from_d_str, "%Y-%m-%d")
                td = datetime.strptime(to_d_str, "%Y-%m-%d")
                diff_days = (td - fd).days
                if diff_days > 30:
                    err_msg = f"Search date range between '{from_d_str}' and '{to_d_str}' ({diff_days} days) exceeds the maximum allowed search window of 30 days. Please narrow your search window to 30 days or less."
                    return {
                        "status": "error",
                        "error": "date_range_exceeded",
                        "message": err_msg,
                        "meta_data": {
                            "type": "ai_search",
                            "search_type": selected_types[0] if selected_types else "flights",
                            "prompt": prompt,
                            "parsed_intent": intent,
                            "error": err_msg,
                        },
                        "data": {
                            "ai_summary": f"Cannot complete search: {err_msg}",
                            "category_highlights": {},
                            "search_type": selected_types[0] if selected_types else "flights",
                            "total_items": 0,
                            "offers": [],
                            "top_bundles": [],
                            "raw_data": {},
                        },
                    }
            except Exception:
                pass

        if ("flights" in selected_types or len(selected_types) > 1) and origin and destination and origin == destination:
            err_msg = f"Origin airport '{origin}' and destination airport '{destination}' cannot be identical."
            return {
                "status": "error",
                "error": "invalid_route",
                "message": err_msg,
                "meta_data": {
                    "type": "ai_search",
                    "search_type": selected_types[0] if selected_types else "flights",
                    "prompt": prompt,
                    "parsed_intent": intent,
                    "error": err_msg,
                },
                "data": {
                    "ai_summary": f"Cannot complete search: {err_msg}",
                    "category_highlights": {},
                    "search_type": selected_types[0] if selected_types else "flights",
                    "total_items": 0,
                    "offers": [],
                    "top_bundles": [],
                    "raw_data": {},
                },
            }

        passengers_count = overrides.get("passengers_count") or intent.get("passengers_count") or 1
        cabin_class = (overrides.get("cabin_class") or intent.get("cabin_class") or "economy").lower()
        rooms = overrides.get("rooms") or intent.get("rooms") or 1
        driver_age = overrides.get("driver_age") or intent.get("driver_age") or 30
        
        # Build cache key based on search intent including prompt and airline preferences
        import re
        norm_prompt = re.sub(r"\s+", " ", prompt.lower().strip().strip(".,!?"))
        fav_airline = (favorite_airline or overrides.get("favorite_airline") or intent.get("preferred_airline") or intent.get("favorite_airline") or "").strip().lower()
        if fav_airline and not intent.get("preferred_airline"):
            intent["preferred_airline"] = fav_airline.title()
        excluded_airlines = sorted([x.lower().strip() for x in (intent.get("excluded_airlines") or overrides.get("excluded_airlines") or [])])

        hash_input = f"ai_{norm_prompt}_{sorted(selected_types)}_{origin}_{destination}_{departure_date}_{return_date}_{passengers_count}_{cabin_class}_{rooms}_{driver_age}_{fav_airline}_{excluded_airlines}"
        hash_key = hashlib.md5(hash_input.encode("utf-8")).hexdigest()[:6]
        cache_key = f"duffel:ai:search:{hash_key}"
        
        # Check cache
        if self.cache and self.cache.enabled and not force_refresh:
            cached_res = self.cache.get(cache_key)
            if cached_res and isinstance(cached_res, dict):
                print(f"\n[+] TIER-1 AI SEARCH CACHE HIT for key: {cache_key}\n")
                return cached_res
        
        # Step 2: Route based on number of types
        num_types = len(selected_types)
        
        if num_types == 1:
            service_type = selected_types[0]
            search_type = service_type
            result = self._execute_single_service(
                service_type=service_type,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers_count=passengers_count,
                cabin_class=cabin_class,
                rooms=rooms,
                driver_age=driver_age,
                favorite_airline=fav_airline,
                force_refresh=force_refresh,
                prompt=prompt,
                intent=intent,
            )
        else:
            search_type = "bundle"
            result = self._execute_bundle_search(
                selected_types=selected_types,
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers_count=passengers_count,
                cabin_class=cabin_class,
                rooms=rooms,
                driver_age=driver_age,
                force_refresh=force_refresh,
                prompt=prompt,
            )

        # Build geo location metadata
        try:
            from .locations import resolve_geo_location
            orig_geo = resolve_geo_location(origin) if origin else {}
            dest_geo = resolve_geo_location(destination) if destination else {}
            geo_info = {
                "origin": {"code": origin, **orig_geo} if origin else None,
                "destination": {"code": destination, **dest_geo} if destination else None,
            }
        except Exception:
            geo_info = None

        meta_data = {
            "type": "ai_search",
            "search_type": search_type,
            "prompt": prompt,
            "parsed_intent": intent,
            "geo_location": geo_info,
        }

        if hasattr(result, "model_dump"):
            res_dict = result.model_dump()
        elif hasattr(result, "dict"):
            res_dict = result.dict()
        elif isinstance(result, dict):
            res_dict = result
        else:
            res_dict = dict(result)

        raw_data = res_dict.get("data", res_dict)
        items = raw_data.get("offers") or raw_data.get("results") or raw_data.get("top_bundles") or raw_data.get("packages") or raw_data.get("bundles") or []




        highlights = self._synthesize_highlights(items, search_type)
        ai_summary = self._generate_ai_summary(prompt, search_type, items, highlights, destination)

        def _is_ns(item: Any) -> bool:
            o = item.get("flight_offer") if isinstance(item, dict) and "flight_offer" in item else item
            if not isinstance(o, dict):
                return False
            if o.get("max_stops") == 0 or o.get("stops") == 0 or o.get("legs") in ["Non-stop", "Direct", "Nonstop"]:
                return True
            slices = o.get("slices") or o.get("slice_details") or []
            if isinstance(slices, list) and len(slices) > 0:
                for s in slices:
                    if isinstance(s, dict):
                        segs = s.get("segments") or []
                        if len(segs) > 1:
                            return False
                return True
            return False

        non_stop_items = [x for x in items if _is_ns(x)]
        non_stop_items.sort(key=lambda x: float(x.get("total_amount") or x.get("total_package_price") or 0.0))
        lowest_non_stop_offers = non_stop_items[:10]

        data_section = {
            "ai_summary": ai_summary,
            "category_highlights": highlights,
            "search_type": search_type,
            "total_items": len(items),
            "lowest_non_stop_offers": lowest_non_stop_offers,
            "total_non_stop_offers": len(non_stop_items),
            "offers": items if search_type != "bundle" else [],
            "top_bundles": items if search_type == "bundle" else [],
            "raw_data": raw_data,
        }

        response_envelope = {
            "status": "success",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "meta_data": meta_data,
            "data": data_section,
        }

        # Cache result (120s for no data found, 3600s for valid results)
        if self.cache and self.cache.enabled:
            ttl_sec = 120 if (not items or len(items) == 0) else 3600
            self.cache.set(cache_key, response_envelope, ttl_seconds=ttl_sec)

        return response_envelope

    def _synthesize_highlights(self, items: list[dict[str, Any]], search_type: str) -> dict[str, Any]:
        """Synthesizes persona highlights (best_match, cheapest, luxury_choice, fastest) across offers."""
        if not items:
            return {}

        def get_price(item: dict[str, Any]) -> float:
            p = item.get("total_amount") or item.get("total_package_price") or item.get("cheapest_rate_total_amount") or 0.0
            try:
                return float(p)
            except Exception:
                return 0.0

        sorted_by_price = sorted(items, key=get_price)
        cheapest = sorted_by_price[0] if sorted_by_price else items[0]
        luxury = sorted_by_price[-1] if sorted_by_price else items[0]
        best_match = items[0]

        # Determine fastest/express pick
        fastest = best_match
        if search_type == "flights":
            nonstops = [i for i in items if i.get("max_stops", 1) == 0]
            fastest = nonstops[0] if nonstops else cheapest
        elif search_type == "cars":
            suvs = [i for i in items if "SUV" in str(i.get("vehicle", {}).get("category", ""))]
            fastest = suvs[0] if suvs else cheapest
        elif search_type == "bundle":
            direct_pkgs = [b for b in items if b.get("flight_offer", {}).get("max_stops", 1) == 0]
            fastest = direct_pkgs[0] if direct_pkgs else cheapest

        return {
            "best_match": best_match,
            "cheapest": cheapest,
            "luxury_choice": luxury,
            "fastest": fastest,
        }

    def _generate_ai_summary(
        self,
        prompt: str,
        search_type: str,
        items: list[dict[str, Any]],
        highlights: dict[str, Any],
        destination: str,
    ) -> str:
        """Generates executive 2-sentence summary explaining top choice and value insights."""
        if not items:
            return f"No travel options found for your prompt: '{prompt}'. Please try broadening your search criteria."

        best = highlights.get("best_match", {})
        cheap = highlights.get("cheapest", {})
        price = best.get("total_amount") or best.get("total_package_price") or best.get("cheapest_rate_total_amount") or "N/A"
        curr = best.get("currency") or best.get("total_currency") or "USD"

        if search_type == "cars":
            v_name = best.get("vehicle", {}).get("name") or "vehicle"
            sup = best.get("supplier", {}).get("name") or "supplier"
            return f"AI Search analyzed {len(items)} rental car options in {destination or 'your destination'}. Recommended: {sup} - {v_name} at {curr} {price}."
        elif search_type == "hotels":
            acc_name = best.get("accommodation", {}).get("name") or "hotel"
            return f"AI Search analyzed {len(items)} hotel accommodations. Recommended: {acc_name} at {curr} {price}."
        elif search_type == "bundle":
            return f"AI Search created {len(items)} package bundles. Recommended package combines flights, stay, and car rental starting at {curr} {price}."
        else:
            return f"AI Search analyzed {len(items)} flight offers. Recommended best option is available starting at {curr} {price}."

    def _execute_single_service(
        self,
        service_type: str,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        passengers_count: int,
        cabin_class: str,
        rooms: int,
        driver_age: int,
        favorite_airline: str,
        force_refresh: bool,
        prompt: str,
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute single service and return its response format."""
        if service_type in ["hotels", "stays"]:
            return self._execute_hotel_search(
                destination=destination,
                check_in_date=departure_date,
                check_out_date=return_date,
                rooms=rooms,
                passengers_count=passengers_count,
                force_refresh=force_refresh,
                prompt=prompt,
            )
        elif service_type == "cars":
            return self._execute_car_search(
                destination=destination,
                pickup_datetime=f"{departure_date}T10:00:00Z",
                dropoff_datetime=f"{return_date}T10:00:00Z",
                driver_age=driver_age,
                force_refresh=force_refresh,
                prompt=prompt,
            )
        else:
            return self._execute_flight_search(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers_count=passengers_count,
                cabin_class=cabin_class,
                favorite_airline=favorite_airline,
                force_refresh=force_refresh,
                prompt=prompt,
                intent=intent,
            )

    def _execute_flight_search(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        passengers_count: int,
        cabin_class: str,
        favorite_airline: str,
        force_refresh: bool,
        prompt: str,
        intent: dict[str, Any],
    ) -> dict[str, Any]:
        """Execute flight search using natural search resolution to enforce intent filters."""
        if hasattr(self.client_app, "natural_search"):
            pref_air_param = favorite_airline or intent.get("preferred_airline") or ""
            return self.client_app.natural_search.search_natural(
                prompt,
                favorite_airline=pref_air_param,
                force_refresh=force_refresh,
            )

        if not hasattr(self.client_app, "flights"):
            return {"status": "error", "detail": "Flights service not available"}

        from ..api.schemas.flights import StandardFlightSearchRequest
        from ..api.routes.flights import search_exact_flights

        req = StandardFlightSearchRequest(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers_count=passengers_count,
            cabin_class=cabin_class,
            favorite_airline=favorite_airline or intent.get("preferred_airline"),
            force_refresh=force_refresh,
            prompt=prompt,
        )
        res = search_exact_flights(req)
        return res.model_dump() if hasattr(res, "model_dump") else dict(res)


    def _execute_hotel_search(
        self,
        destination: str,
        check_in_date: str,
        check_out_date: str,
        rooms: int,
        passengers_count: int,
        force_refresh: bool,
        prompt: str,
    ) -> dict[str, Any]:
        """Execute hotel search and return native stay response format."""
        if not hasattr(self.client_app, "stays"):
            return {"status": "error", "detail": "Stays service not available"}

        from ..api.schemas.stays import StaySearchRequest
        from ..api.routes.stays import search_stays_endpoint

        req = StaySearchRequest(
            check_in_date=check_in_date,
            check_out_date=check_out_date,
            rooms=rooms,
            location_string=destination,
            force_refresh=force_refresh,
        )
        res = search_stays_endpoint(req)
        return res.model_dump() if hasattr(res, "model_dump") else dict(res)

    def _execute_car_search(
        self,
        destination: str,
        pickup_datetime: str,
        dropoff_datetime: str,
        driver_age: int,
        force_refresh: bool,
        prompt: str,
    ) -> dict[str, Any]:
        """Execute car search and return native car search response format."""
        if not hasattr(self.client_app, "cars"):
            return {"status": "error", "detail": "Cars service not available"}

        from ..api.schemas.cars import CarSearchRequest
        from ..api.routes.cars import search_cars_endpoint

        req = CarSearchRequest(
            pickup_location=destination,
            dropoff_location=destination,
            pickup_datetime=pickup_datetime,
            dropoff_datetime=dropoff_datetime,
            driver_age=driver_age,
            force_refresh=force_refresh,
        )

        res = search_cars_endpoint(req)
        return res.model_dump() if hasattr(res, "model_dump") else dict(res)

    def _execute_bundle_search(
        self,
        selected_types: list[str],
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        passengers_count: int,
        cabin_class: str,
        rooms: int,
        driver_age: int,
        force_refresh: bool,
        prompt: str,
    ) -> dict[str, Any]:
        """Execute bundle search and return native bundle response format."""
        if not hasattr(self.client_app, "bundles"):
            return {"status": "error", "detail": "Bundles service not available"}

        from ..api.schemas.bundles import BundleSearchRequest
        from ..api.routes.bundles import search_bundles_endpoint

        req = BundleSearchRequest(
            origin=origin,
            destination=destination,
            departure_date=departure_date,
            return_date=return_date,
            passengers_count=passengers_count,
            cabin_class=cabin_class,
            rooms=rooms,
            driver_age=driver_age,
            bundle_types=selected_types,
            force_refresh=force_refresh,
        )
        res = search_bundles_endpoint(req)
        return res.model_dump() if hasattr(res, "model_dump") else dict(res)

