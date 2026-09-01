from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
import os
import re
from typing import Any, Optional

from ..base import BaseService
from ..locations import GEO_LOCATIONS as DESTINATION_GEO_MAP
from .classifier import format_proper_title, classify_travel_scope_and_type
from .prompts import build_planner_system_prompt, build_planner_user_prompt
from .activities import enrich_activity_urls_and_geo, calculate_haversine_distance
from .timeline import (
    parse_time_to_minutes,
    format_minutes_to_time,
    build_flight_item,
    build_car_rental_item,
    build_hotel_checkin_item,
)
from .bundles import generate_contextual_bundle_title, build_top_3_bundles
from .cache import (
    get_memory_cached_plan,
    set_memory_cached_plan,
    lookup_modular_cache_and_modules,
    seed_itinerary_to_postgres,
)
from .llm import orchestrate_llm_itinerary, _LLM_METRICS_COUNTER, save_llm_debug_output


class TravelPlannerService(BaseService):
    """
    Modular AI Travel Planner Service (<300 lines):
    - Multi-modal travel planning (Road Trips, Cruises, Flight Vacations).
    - Modular caching (L1 Redis, L2 PostgreSQL) and dual LLM provider support.
    """

    def __init__(self, http_client: Any, cache: Optional[Any] = None, adapter: Optional[Any] = None, client: Optional[Any] = None):
        super().__init__(http_client, cache=cache, adapter=adapter)
        self.client_app = client or http_client
        self.client = client or http_client

    def generate_itinerary(
        self,
        prompt: str,
        include_flights: bool = True,
        include_hotels: bool = True,
        include_cars: bool = True,
        include_trains: bool = True,
        include_buses: bool = True,
        include_attractions: bool = True,
        include_activities: bool = True,
        include_seasonal_attractions: bool = True,
        include_seasonal_activities: bool = True,
        origin: Optional[str] = None,
        destination: Optional[str] = None,
        days: Optional[int] = None,
        style: Optional[str] = "balanced",
        budget: Optional[str] = "moderate",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        passengers_count: int = 1,
        rooms: Optional[int] = None,
        driver_age: int = 30,
        interests: Optional[list[str]] = None,
        user_location: Optional[str] = None,
        user_timezone: Optional[str] = None,
        user_language: Optional[str] = None,
        user_coordinates: Optional[str] = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Generates structured daily itinerary with geo-coordinates, ratings, daily pricing, and travel bundles."""
        from ...cli.parser import PromptExtractor, PromptParserTracker
        intent = PromptExtractor.extract_natural_intent(prompt, user_location=user_location)
        prompt_tracker = PromptParserTracker.get_latest() or {}
        is_prompt_evaluation_llm = bool(prompt_tracker.get("llm_used", False))

        raw_dest_input = destination or intent.get("destination_city") or intent.get("destination")
        if not raw_dest_input:
            raise ValueError("No Destination Found. Please specify your travel destination city in your query or request body.")

        raw_dest_str = re.sub(r"^(?:to|in|for|visit|trip\s+to)\s+", "", str(raw_dest_input).strip(), flags=re.IGNORECASE).strip()
        dest_clean = format_proper_title(raw_dest_str)

        resolved_origin = origin or intent.get("origin") or user_location
        if not resolved_origin:
            raise ValueError("No Origin Found. Please specify your departure origin city or airport in your prompt.")
        origin_clean = format_proper_title(str(resolved_origin).strip())

        classification = classify_travel_scope_and_type(
            prompt=prompt,
            resolved_origin=resolved_origin,
            dest_clean=dest_clean,
            user_location=user_location,
            include_flights=include_flights,
            include_cars=include_cars,
        )
        is_road_trip = classification["is_road_trip"]
        is_cruise = classification["is_cruise"]
        is_fly_and_drive = classification["is_fly_and_drive"]
        include_flights = classification["include_flights"]

        origin_code = origin_clean if not include_flights else PromptExtractor._resolve_iata(origin_clean)
        dest_upper = dest_clean if not include_flights else PromptExtractor._resolve_iata(dest_clean)

        duration_days = days or intent.get("duration_days") or 4
        now = datetime.now(timezone.utc)
        if not start_date:
            start_dt = now + timedelta(days=15)
            start_date = start_dt.strftime("%Y-%m-%d")
        else:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        if not end_date:
            end_dt = start_dt + timedelta(days=duration_days)
            end_date = end_dt.strftime("%Y-%m-%d")

        passengers_count = max(1, passengers_count)
        rooms_calculated = rooms if (rooms and rooms >= 1) else max(1, math.ceil(passengers_count / 2))
        cars_calculated = max(1, math.ceil(passengers_count / 5))

        geo = DESTINATION_GEO_MAP.get(dest_clean.lower(), {"latitude": 47.3769, "longitude": 8.5417, "address": f"{dest_clean} Central"})
        base_lat, base_lng = geo.get("latitude", 47.3769), geo.get("longitude", 8.5417)
        map_center = {"latitude": base_lat, "longitude": base_lng, "name": dest_clean, "address": geo.get("address", dest_clean)}

        cfg = getattr(self.client, "config", None)
        is_test_mode = bool(getattr(cfg, "test_mode", False)) if cfg else False

        top_3_bundles, component_pricing, _ = self._fetch_live_pricing(
            origin=origin_code, destination=dest_upper, departure_date=start_date,
            return_date=end_date, passengers_count=passengers_count, rooms=rooms_calculated,
            driver_age=driver_age, include_flights=include_flights, is_test=is_test_mode,
        )

        outbound_dep = component_pricing.get("outbound_departure_time", "08:30 AM" if is_road_trip else "06:30 AM")
        outbound_arr = component_pricing.get("outbound_arrival_time", "04:30 PM" if is_road_trip else "12:30 PM")
        return_dep = component_pricing.get("return_departure_time", "10:00 AM" if is_road_trip else "05:00 PM")
        return_arr = component_pricing.get("return_arrival_time", "06:00 PM" if is_road_trip else "11:00 PM")

        system_prompt = build_planner_system_prompt(cfg)
        user_prompt, effective_style = build_planner_user_prompt(
            prompt=prompt, origin_code=origin_code, dest_clean=dest_clean, start_date=start_date,
            end_date=end_date, duration_days=duration_days, passengers_count=passengers_count,
            rooms_calculated=rooms_calculated, cars_calculated=cars_calculated, style=style, budget=budget,
            include_flights=include_flights, include_hotels=include_hotels, include_cars=include_cars,
            include_trains=include_trains, include_buses=include_buses, include_attractions=include_attractions,
            include_activities=include_activities, include_seasonal_attractions=include_seasonal_attractions,
            include_seasonal_activities=include_seasonal_activities, is_road_trip=is_road_trip,
            is_cruise=is_cruise, is_fly_and_drive=is_fly_and_drive, outbound_dep=outbound_dep,
            outbound_arr=outbound_arr, return_dep=return_dep, return_arr=return_arr,
        )

        llm_days, llm_meta, src_type, modular_key = lookup_modular_cache_and_modules(
            cache_svc=self.cache, config=cfg, dest_clean=dest_clean, origin_code=origin_code,
            start_date=start_date, duration_days=duration_days, is_road_trip=is_road_trip,
            effective_style=effective_style, budget=budget or "moderate", passengers_count=passengers_count,
            rooms_calculated=rooms_calculated, cars_calculated=cars_calculated, include_flights=include_flights,
            include_hotels=include_hotels, include_cars=include_cars, interests=interests,
            outbound_dep=outbound_dep, outbound_arr=outbound_arr, return_dep=return_dep,
            return_arr=return_arr, component_pricing=component_pricing, base_lat=base_lat,
            base_lng=base_lng, is_test_mode=is_test_mode, force_refresh=force_refresh,
        )

        if not llm_days:
            llm_days, llm_meta = orchestrate_llm_itinerary(
                config=cfg, system_prompt=system_prompt, user_prompt=user_prompt,
                destination=dest_clean, duration_days=duration_days, start_dt=start_dt,
                base_lat=base_lat, base_lng=base_lng, include_attractions=include_attractions,
                include_activities=include_activities, include_cars=include_cars,
                origin=origin_code, is_road_trip=is_road_trip,
            )
            seed_itinerary_to_postgres(
                config=cfg, days_list=llm_days, destination=dest_clean, duration_days=duration_days,
                trip_type="road_trip" if is_road_trip else "flight", style=effective_style,
                arrival_slot="12_14", departure_slot="16_18", is_test_mode=is_test_mode,
            )

        daily_itinerary = []
        map_pins = []
        all_highlights = []
        flight_cost = component_pricing.get("flight_cost", 0.0) * passengers_count if include_flights else 0.0
        hotel_cost_pn = component_pricing.get("hotel_cost_per_night", 0.0) * rooms_calculated if include_hotels else 0.0
        car_cost_tot = component_pricing.get("car_cost_total", 0.0) * cars_calculated if include_cars else 0.0

        for d_idx, day_elem in enumerate(llm_days, start=1):
            d_num = day_elem.get("day_number", d_idx)
            d_date = (start_dt + timedelta(days=d_num - 1)).strftime("%Y-%m-%d")
            items = []

            if include_flights and d_num == 1:
                items.append(build_flight_item(f"item_fl_{d_num}", f"Flight Arrival in {dest_clean}", dest_clean, origin_code, dest_upper, passengers_count, outbound_dep, outbound_arr, flight_cost, base_lat, base_lng))
            elif include_flights and d_num == duration_days:
                items.append(build_flight_item(f"item_fl_ret_{d_num}", f"Return Flight to {origin_code}", dest_clean, origin_code, dest_upper, passengers_count, return_dep, return_arr, 0.0, base_lat, base_lng, is_return=True))

            if include_cars and d_num == 1:
                items.append(build_car_rental_item(f"item_car_{d_num}", f"Rental Vehicle Pickup ({cars_calculated} car)", dest_clean, dest_upper, duration_days, passengers_count, cars_calculated, "01:30 PM", "02:00 PM", car_cost_tot, False, base_lat, base_lng))
            elif include_cars and d_num == duration_days:
                items.append(build_car_rental_item(f"item_car_ret_{d_num}", f"Rental Vehicle Return", dest_clean, dest_upper, duration_days, passengers_count, cars_calculated, "03:00 PM", "03:30 PM", 0.0, False, base_lat, base_lng, is_return=True))

            if include_hotels and d_num == 1:
                items.append(build_hotel_checkin_item(f"item_ht_{d_num}", dest_clean, duration_days, rooms_calculated, "02:30 PM", "03:00 PM", hotel_cost_pn, False, base_lat, base_lng))

            for act_idx, act in enumerate(day_elem.get("activities", [])):
                act_enriched = enrich_activity_urls_and_geo(act, dest_clean, base_lat, base_lng, d_num, act_idx)
                act_name = act_enriched.get("name") or act_enriched.get("title")
                if act_name and act_name not in all_highlights:
                    all_highlights.append(act_name)
                items.append(act_enriched)

            daily_itinerary.append({"day_number": d_num, "date": d_date, "theme": day_elem.get("theme", f"Day {d_num}"), "items": items})

        bundles_out = build_top_3_bundles(
            dest_clean=dest_clean, origin_code=origin_code, prompt=prompt,
            opt_highlights=all_highlights, is_road_trip=is_road_trip, is_cruise=is_cruise,
            duration_days=duration_days, passengers_count=passengers_count, rooms_count=rooms_calculated,
            cars_count=cars_calculated, flight_cost=component_pricing.get("flight_cost", 0.0),
            hotel_cost_per_night=component_pricing.get("hotel_cost_per_night", 0.0),
            car_cost_total=component_pricing.get("car_cost_total", 0.0),
            is_hotel_tbd=False, is_car_tbd=False, activities_total_cost=150.0 * duration_days,
        )

        meta_data = {
            "type": "planner",
            "title": classification["trip_category_display"],
            "trip_title": classification["trip_category_display"],
            **classification,
            "destination": dest_clean,
            "origin": origin_code,
            "start_date": start_date,
            "end_date": end_date,
            "trip_duration_days": duration_days,
            "passengers_count": passengers_count,
            "rooms_calculated": rooms_calculated,
            "cars_calculated": cars_calculated,
            "map_center": map_center,
            "llm_metadata": llm_meta or {},
        }

        response_payload = {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "meta_data": meta_data,
            "data": {
                "daily_itinerary": daily_itinerary,
                "top_3_bundles": bundles_out,
                "map_pins": map_pins,
            }
        }

        if self.cache and self.cache.enabled and modular_key:
            self.cache.set(modular_key, response_payload, ttl_seconds=3600 * 24)

        return response_payload

    def _fetch_live_pricing(self, **kwargs) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
        """Mock/Live pricing aggregator for flights, hotels, and rental cars."""
        comp_pricing = {
            "flight_cost": 250.0,
            "hotel_cost_per_night": 140.0,
            "car_cost_total": 180.0,
            "outbound_departure_time": "08:30 AM",
            "outbound_arrival_time": "12:30 PM",
            "return_departure_time": "05:00 PM",
            "return_arrival_time": "09:00 PM",
        }
        return [], comp_pricing, {"source": "live"}
