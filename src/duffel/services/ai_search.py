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
        intent = PromptExtractor.extract_natural_intent(prompt)
        selected_types = overrides.get("selected_types") or intent.get("selected_types") or ["flights"]
        
        # Normalize types to lowercase
        selected_types = [t.lower() for t in selected_types]
        
        # Extract parameters with overrides
        origin = (overrides.get("origin") or intent.get("origin") or "").upper()
        destination = (overrides.get("destination") or intent.get("destination") or "").upper()
        departure_date = overrides.get("departure_date") or intent.get("departure_date") or "2026-10-01"
        return_date = overrides.get("return_date") or intent.get("return_date") or "2026-10-08"
        passengers_count = overrides.get("passengers_count") or intent.get("passengers_count") or 1
        cabin_class = (overrides.get("cabin_class") or intent.get("cabin_class") or "economy").lower()
        rooms = overrides.get("rooms") or intent.get("rooms") or 1
        driver_age = overrides.get("driver_age") or intent.get("driver_age") or 30
        
        # Build cache key based on search intent
        hash_input = f"ai_{sorted(selected_types)}_{origin}_{destination}_{departure_date}_{return_date}_{passengers_count}_{cabin_class}_{rooms}_{driver_age}"
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
            # Single type: call that service and return its response format
            service_type = selected_types[0]
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
                favorite_airline=favorite_airline,
                force_refresh=force_refresh,
                prompt=prompt,
                intent=intent,
            )
        else:
            # Multiple types: call bundle service with these types
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
        
        # Cache result
        if self.cache and self.cache.enabled:
            ttl_seconds = result.get("ttl_seconds", 3600)
            self.cache.set(cache_key, result, ttl_seconds=ttl_seconds)
        
        return result

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
        """
        Execute single service and return its native response format.
        """
        if service_type == "flights":
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
        elif service_type == "hotels":
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
            # Default to flights
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
        """Execute flight search and return OptimizedFlightSearchResponse format."""
        try:
            if not hasattr(self.client_app, "flights"):
                return {"status": "error", "detail": "Flights service not available"}
            
            flights_service = self.client_app.flights
            result = flights_service.search_exact(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers=[Passenger(type="adult") for _ in range(passengers_count)],
                cabin_class=CabinClass(cabin_class.lower()),
                favorite_airline=favorite_airline or None,
                force_refresh=force_refresh,
            )
            
            # Add TTL info
            result["ttl_seconds"] = 3600
            result["source"] = "ai_search_flights"
            result["search_type"] = "flights"
            result["prompt"] = prompt
            
            return result
        except Exception as e:
            print(f"[AI SEARCH] Flight search error: {e}")
            return {"status": "error", "detail": str(e), "ttl_seconds": 3600, "search_type": "flights"}

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
        """Execute hotel search and return StaySearchResponse format."""
        try:
            if not hasattr(self.client_app, "stays"):
                return {"status": "error", "detail": "Stays service not available"}
            
            stays_service = self.client_app.stays
            results = stays_service.search(
                check_in_date=check_in_date,
                check_out_date=check_out_date,
                rooms=rooms,
                guests=[{"type": "adult"} for _ in range(passengers_count)],
                location={"place_id": destination.lower()},
            )
            
            res_dicts = [r.to_dict() if hasattr(r, "to_dict") else getattr(r, "__dict__", {}) for r in results]
            
            response = {
                "status": "success",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_results": len(res_dicts),
                "results": res_dicts,
                "ttl_seconds": 3600,
                "source": "ai_search_hotels",
                "search_type": "hotels",
                "prompt": prompt,
            }
            
            return response
        except Exception as e:
            print(f"[AI SEARCH] Hotel search error: {e}")
            return {"status": "error", "detail": str(e), "ttl_seconds": 3600, "search_type": "hotels"}

    def _execute_car_search(
        self,
        destination: str,
        pickup_datetime: str,
        dropoff_datetime: str,
        driver_age: int,
        force_refresh: bool,
        prompt: str,
    ) -> dict[str, Any]:
        """Execute car search and return CarSearchResponse format."""
        try:
            if not hasattr(self.client_app, "cars"):
                return {"status": "error", "detail": "Cars service not available"}
            
            cars_service = self.client_app.cars
            results = cars_service.search(
                pickup_location=destination,
                dropoff_location=destination,
                pickup_datetime=pickup_datetime,
                dropoff_datetime=dropoff_datetime,
                driver_age=driver_age,
            )
            
            res_dicts = [r.to_dict() if hasattr(r, "to_dict") else getattr(r, "__dict__", {}) for r in results]
            
            response = {
                "status": "success",
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "total_results": len(res_dicts),
                "results": res_dicts,
                "ttl_seconds": 3600,
                "source": "ai_search_cars",
                "search_type": "cars",
                "prompt": prompt,
            }
            
            return response
        except Exception as e:
            print(f"[AI SEARCH] Car search error: {e}")
            return {"status": "error", "detail": str(e), "ttl_seconds": 3600, "search_type": "cars"}

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
        """Execute bundle search with selected types and return BundleSearchResponse format."""
        try:
            if not hasattr(self.client_app, "bundles"):
                return {"status": "error", "detail": "Bundles service not available"}
            
            bundles_service = self.client_app.bundles
            result = bundles_service.search_bundle(
                origin=origin,
                destination=destination,
                departure_date=departure_date,
                return_date=return_date,
                passengers_count=passengers_count,
                cabin_class=cabin_class,
                rooms=rooms,
                driver_age=driver_age,
                force_refresh=force_refresh,
                selected_types=selected_types,  # Pass which types to search
            )
            
            # Add source info
            result["source"] = "ai_search_bundle"
            result["search_type"] = "bundle"
            result["prompt"] = prompt
            result["ttl_seconds"] = 3600
            result["selected_types"] = selected_types
            
            return result
        except Exception as e:
            print(f"[AI SEARCH] Bundle search error: {e}")
            return {"status": "error", "detail": str(e), "ttl_seconds": 3600, "search_type": "bundle"}
