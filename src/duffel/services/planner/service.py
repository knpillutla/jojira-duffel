from datetime import datetime, timedelta, timezone
import math, re
from typing import Any, Optional

from ..base import BaseService
from ..locations import GEO_LOCATIONS as DESTINATION_GEO_MAP
from .classifier import format_proper_title, classify_travel_scope_and_type
from ...prompts import build_planner_system_prompt, build_planner_user_prompt
from .activities import enrich_activity_urls_and_geo, calculate_haversine_distance, enrich_items_with_next_activity, build_google_maps_route_url
from .timeline import (
    parse_time_to_minutes, parse_end_time_to_minutes, format_minutes_to_time,
    build_flight_item, build_car_rental_item, build_hotel_checkin_item, fetch_live_component_pricing,
)
from .bundles import build_top_3_bundles
from .cache import (
    get_memory_cached_plan, set_memory_cached_plan, lookup_modular_cache_and_modules,
    seed_itinerary_to_postgres, build_execution_and_cache_insights,
)
from .llm import orchestrate_llm_itinerary, _LLM_METRICS_COUNTER, save_llm_debug_output
from .summary import build_trip_summary
from ...timing import StepLogger


class TravelPlannerService(BaseService):
    """Modular AI Travel Planner Service (<300 lines)."""

    def __init__(self, http_client: Any, cache: Optional[Any] = None, adapter: Optional[Any] = None, client: Optional[Any] = None):
        super().__init__(http_client, cache=cache, adapter=adapter)
        self.client_app = self.client = client or http_client

    def generate_itinerary(
        self, prompt: str, include_flights: bool = True, include_hotels: bool = True,
        include_cars: bool = True, include_trains: bool = True, include_buses: bool = True,
        include_attractions: bool = True, include_activities: bool = True,
        include_seasonal_attractions: bool = True, include_seasonal_activities: bool = True,
        origin: Optional[str] = None, destination: Optional[str] = None, days: Optional[int] = None,
        style: Optional[str] = "balanced", budget: Optional[str] = "moderate",
        start_date: Optional[str] = None, end_date: Optional[str] = None, passengers_count: int = 1,
        rooms: Optional[int] = None, driver_age: int = 30, interests: Optional[list[str]] = None,
        user_location: Optional[str] = None, user_timezone: Optional[str] = None, user_language: Optional[str] = None,
        user_coordinates: Optional[str] = None, force_refresh: bool = False, road_trip: Optional[bool] = None,
        fly_and_drive: Optional[bool] = None,
    ) -> dict[str, Any]:
        """Generates structured daily itinerary with geo-coordinates, ratings, daily pricing, and travel bundles."""
        if road_trip is True:
            include_flights = False
        if fly_and_drive is True:
            include_flights = True
            include_cars = True

        with StepLogger.step(1, 6, "Prompt Intent Extraction & Route Classification", f"Query: {prompt[:35]}..."):
            from ...cli.parser import PromptExtractor, PromptParserTracker
            intent = PromptExtractor.extract_natural_intent(prompt, user_location=user_location)
            prompt_tracker = PromptParserTracker.get_latest() or {}
            is_prompt_evaluation_llm = bool(prompt_tracker.get("llm_used", False))

            raw_dest_input = destination or intent.get("destination_city") or intent.get("destination")
            if not raw_dest_input:
                raise ValueError("No Destination Found. Please specify your travel destination city in your query or request body.")

            raw_dest_str = re.sub(r"^(?:to|in|for|visit|trip\s+to)\s+", "", str(raw_dest_input).strip(), flags=re.IGNORECASE).strip()
            resolved_origin = origin or intent.get("origin_city") or intent.get("origin") or user_location
            if not resolved_origin:
                raise ValueError("No Origin Found. Please specify your departure origin city or airport in your prompt.")

            classification = classify_travel_scope_and_type(
                prompt=prompt, resolved_origin=resolved_origin, dest_clean=raw_dest_str,
                user_location=user_location, include_flights=include_flights, include_cars=include_cars, road_trip=road_trip,
            )
            is_road_trip, is_cruise, include_flights = classification["is_road_trip"], classification["is_cruise"], classification["include_flights"]

            if not include_flights:
                dest_clean, origin_clean = PromptExtractor._resolve_city_name(raw_dest_str), PromptExtractor._resolve_city_name(str(resolved_origin).strip())
                origin_code, dest_upper = origin_clean, dest_clean
            else:
                dest_clean, origin_clean = format_proper_title(raw_dest_str), format_proper_title(str(resolved_origin).strip())
                origin_code = str(PromptExtractor._resolve_iata(origin_clean) or origin_clean).upper().strip()
                dest_upper = str(PromptExtractor._resolve_iata(dest_clean) or dest_clean).upper().strip()

            has_fixed_dates = bool(start_date and end_date)
            now = datetime.now(timezone.utc)
            duration_days = days or intent.get("duration_days") or 7
            if duration_days > 30:
                err_m = f"Trip duration of {duration_days} days exceeds the maximum allowed limit of 30 days. Please select 30 days or less."
                return {"status": "error", "error": "duration_exceeded", "message": err_m, "meta_data": {"type": "planner", "error": err_m}, "data": {"summary": {}, "daily_itinerary": [], "bundles": []}}
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc) if start_date else (now + timedelta(days=15))
            start_date, end_date = start_dt.strftime("%Y-%m-%d"), (end_date or (start_dt + timedelta(days=max(1, duration_days))).strftime("%Y-%m-%d"))

            pax_info = intent.get("passengers") or {}
            raw_adults, raw_children, c_ages = pax_info.get("adults"), pax_info.get("children", 0), pax_info.get("children_ages") or []
            if raw_adults is None:
                m_ad = re.search(r"(\d+)\s*adult", prompt, re.I)
                raw_adults = int(m_ad.group(1)) if m_ad else (passengers_count if not raw_children else max(1, passengers_count - raw_children))
            if not raw_children and re.search(r"(\d+)\s*(?:kid|child|children)", prompt, re.I):
                raw_children = int(re.search(r"(\d+)\s*(?:kid|child|children)", prompt, re.I).group(1))
            if not c_ages and raw_children > 0:
                c_ages = [int(a) for a in re.findall(r"\b(?:age[s]?|aged)?\s*(\d{1,2})\b", prompt, re.I) if 1 <= int(a) <= 17][:raw_children]

            adults_count, children_count = int(raw_adults or 1), int(raw_children or 0)
            passengers_count = max(1, passengers_count, adults_count + children_count)
            rooms_calculated, cars_calculated = (rooms if (rooms and rooms >= 1) else max(1, math.ceil(passengers_count / 2))), max(1, math.ceil(passengers_count / 5))

            geo = DESTINATION_GEO_MAP.get(dest_clean.lower(), {"latitude": 47.3769, "longitude": 8.5417, "address": f"{dest_clean} Central"})
            base_lat, base_lng = geo.get("latitude", 47.3769), geo.get("longitude", 8.5417)
            map_center = {"latitude": base_lat, "longitude": base_lng, "name": dest_clean, "address": geo.get("address", dest_clean)}
            cfg, is_test_mode = getattr(self.client, "config", None), bool(getattr(getattr(self.client, "config", None), "test_mode", False))

        with StepLogger.step(2, 6, "Live Component Pricing & Availability", f"Origin: {origin_code}, Dest: {dest_upper}"):
            top_3_bundles, component_pricing, _ = fetch_live_component_pricing(
                origin=origin_code, destination=dest_upper, departure_date=start_date, return_date=end_date,
                passengers_count=passengers_count, rooms=rooms_calculated, driver_age=driver_age, include_flights=include_flights, is_test=is_test_mode, client=self.client, prompt=prompt,
            )
            disc_s, disc_e = component_pricing.get("discovered_start_date"), component_pricing.get("discovered_end_date")
            if include_flights and disc_s and not has_fixed_dates:
                start_date = disc_s
                start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if disc_e:
                    end_date = disc_e
                    try:
                        d_span = (datetime.strptime(disc_e, "%Y-%m-%d") - datetime.strptime(disc_s, "%Y-%m-%d")).days
                        if d_span > 0:
                            duration_days = d_span
                    except Exception:
                        pass
            outbound_dep, outbound_arr = component_pricing.get("outbound_departure_time", "08:30 AM" if is_road_trip else "06:30 AM"), component_pricing.get("outbound_arrival_time", "04:30 PM" if is_road_trip else "12:30 PM")
            return_dep, return_arr = component_pricing.get("return_departure_time", "10:00 AM" if is_road_trip else "05:00 PM"), component_pricing.get("return_arrival_time", "06:00 PM" if is_road_trip else "11:00 PM")

        with StepLogger.step(3, 6, "Prompt Template Loading & User Prompt Assembly", f"Style: {style or 'balanced'}"):
            system_prompt = build_planner_system_prompt(cfg)
            user_prompt, effective_style = build_planner_user_prompt(
                prompt=prompt, origin_code=origin_code, dest_clean=dest_clean, start_date=start_date, end_date=end_date,
                duration_days=duration_days, passengers_count=passengers_count, rooms_calculated=rooms_calculated,
                cars_calculated=cars_calculated, style=style, budget=budget, include_flights=include_flights,
                include_hotels=include_hotels, include_cars=include_cars, include_trains=include_trains,
                include_buses=include_buses, include_attractions=include_attractions, include_activities=include_activities,
                include_seasonal_attractions=include_seasonal_attractions, include_seasonal_activities=include_seasonal_activities,
                is_road_trip=is_road_trip, is_cruise=is_cruise,
                outbound_dep=outbound_dep, outbound_arr=outbound_arr, return_dep=return_dep, return_arr=return_arr,
            )

        with StepLogger.step(4, 6, "Cache Lookup & LLM Generation", f"Modality: {'Road Trip' if is_road_trip else 'Flight Vacation'}"):
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

            is_from_postgres, is_from_redis = (src_type == "modular_postgres_assembly"), (src_type == "modular_redis_cache")

            if not llm_days:
                if is_from_redis and isinstance(llm_meta, dict) and "data" in llm_meta:
                    print(f"[CACHE HIT: REDIS] Returning cached payload for '{dest_clean}' (<1ms).")
                    return llm_meta
                print(f"[CACHE MISS] Pre-generated itinerary not found in database for '{dest_clean}' ({duration_days} days). Generating live via LLM.")
                llm_days, llm_meta = orchestrate_llm_itinerary(
                    config=cfg, system_prompt=system_prompt, user_prompt=user_prompt, destination=dest_clean,
                    duration_days=duration_days, start_dt=start_dt, base_lat=base_lat, base_lng=base_lng,
                    include_attractions=include_attractions, include_activities=include_activities,
                    include_cars=include_cars, origin=origin_code, is_road_trip=is_road_trip,
                )
                seed_itinerary_to_postgres(
                    config=cfg, days_list=llm_days, destination=dest_clean, duration_days=duration_days,
                    trip_type="road_trip" if is_road_trip else "flight", style=effective_style,
                    arrival_slot="12_14", departure_slot="16_18", is_test_mode=is_test_mode,
                )
            else:
                c_lbl = "PostgreSQL" if is_from_postgres else "Redis"
                print(f"[CACHE HIT: {c_lbl.upper()}] Pre-generated {duration_days}-day itinerary from {c_lbl} for '{dest_clean}'. Dates: {start_date} to {end_date}.")

        daily_itinerary, map_pins, all_highlights = [], [], []
        city_hotel_registry, current_overnight_hotel = {}, ""
        airline_name = str(component_pricing.get("airline_name") or component_pricing.get("airline") or "Delta Air Lines")
        flight_cost = component_pricing.get("flight_cost", 0.0) * passengers_count if include_flights else 0.0
        hotel_cost_pn, car_cost_tot = component_pricing.get("hotel_cost_per_night", 0.0) * rooms_calculated if include_hotels else 0.0, component_pricing.get("car_cost_total", 0.0) * cars_calculated if include_cars else 0.0

        with StepLogger.step(5, 6, "Daily Timeline Assembly & Chronological Sequencing", f"{len(llm_days)} Days"):
            for d_idx, day_elem in enumerate(llm_days, start=1):
                d_num = day_elem.get("day_number", d_idx)
                d_date = (start_dt + timedelta(days=d_num - 1)).strftime("%Y-%m-%d")
                items = []
                if include_flights and d_num == 1:
                    items.append(build_flight_item(f"item_fl_{d_num}", f"Flight Arrival in {dest_clean}", dest_clean, origin_code, dest_upper, passengers_count, outbound_dep, outbound_arr, flight_cost, base_lat, base_lng, airline_name=airline_name))
                elif include_flights and d_num == duration_days:
                    items.append(build_flight_item(f"item_fl_ret_{d_num}", f"Return Flight to {origin_code}", dest_clean, origin_code, dest_upper, passengers_count, return_dep, return_arr, 0.0, base_lat, base_lng, is_return=True, airline_name=airline_name))
                if include_cars and d_num == 1:
                    pickup_city = origin_clean if (is_road_trip or not include_flights) else dest_clean
                    pickup_code = origin_code if (is_road_trip or not include_flights) else dest_upper
                    pickup_dep, pickup_arr = ("08:30 AM", "09:00 AM") if (is_road_trip or not include_flights) else ("01:30 PM", "02:00 PM")
                    items.append(build_car_rental_item(f"item_car_{d_num}", f"Rental Vehicle Pickup ({cars_calculated} car)", pickup_city, pickup_code, duration_days, passengers_count, cars_calculated, pickup_dep, pickup_arr, car_cost_tot, False, base_lat, base_lng, is_road_trip=(is_road_trip or not include_flights)))
                if include_hotels and d_num == 1 and not is_road_trip:
                    items.append(build_hotel_checkin_item(f"item_ht_{d_num}", dest_clean, duration_days, rooms_calculated, "02:30 PM", "03:00 PM", hotel_cost_pn, False, base_lat, base_lng))
                day_checkin_hotel = ""
                for act_idx, act in enumerate(day_elem.get("activities", [])):
                    act_enriched = enrich_activity_urls_and_geo(act, dest_clean, base_lat, base_lng, d_num, act_idx)
                    act_name = act_enriched.get("name") or act_enriched.get("title") or act_enriched.get("activity")
                    if act_name and act_name not in all_highlights:
                        all_highlights.append(act_name)
                    aname_l = str(act_name or "").lower()
                    adetails_l = str(act_enriched.get("details") or act_enriched.get("description") or "").lower()

                    # Normalize hotel continuity across consecutive nights in the same city
                    if act_enriched.get("category", "").lower() == "hotel" or any(k in aname_l for k in ["check-in at", "check in at", "hotel", "resort"]):
                        c_loc = act_enriched.get("location") or dest_clean
                        c_norm = str(c_loc).lower().split(",")[0].strip()
                        raw_hn = re.sub(r"^(check-in at|check in at|check into|stay at|hotel)\s+", "", act_name or "", flags=re.I).strip()
                        if raw_hn and len(raw_hn) > 3:
                            day_checkin_hotel = current_overnight_hotel = raw_hn
                            if c_norm not in city_hotel_registry:
                                city_hotel_registry[c_norm] = raw_hn
                            elif raw_hn != city_hotel_registry[c_norm]:
                                act_enriched["name"] = act_enriched["title"] = re.sub(re.escape(raw_hn), city_hotel_registry[c_norm], act_name or "", flags=re.I)
                                day_checkin_hotel = current_overnight_hotel = city_hotel_registry[c_norm]

                    is_car_pickup = any(k in aname_l or k in adetails_l for k in ["pickup rental", "rental car pickup", "collect your rental", "pick up rental", "rental vehicle pickup"])
                    if include_cars and d_num == 1 and is_car_pickup:
                        continue
                    is_car_return = any(k in aname_l or k in adetails_l for k in ["return rental", "drop off rental", "rental car return", "drop-off rental", "rental vehicle return"]) or (d_num == duration_days and any(k in aname_l for k in ["arrive in ", "arrival in "]) and "rental" in adetails_l)
                    if include_cars and d_num == duration_days and is_car_return:
                        continue
                    is_flight_act = any(k in aname_l or k in adetails_l for k in ["flight from", "flight to", "fly from", "fly to", "flight arrival", "flight departure", "board flight", "catch flight", "direct flight to"]) or act_enriched.get("travel_mode") == "flight"
                    if include_flights and is_flight_act:
                        continue
                    if (is_road_trip or not include_flights) and d_num == duration_days and (act_enriched.get("category", "").lower() == "shopping" or "shopping" in aname_l or parse_time_to_minutes(act_enriched) >= 1050):
                        continue
                    items.append(act_enriched)

                if include_cars and d_num == duration_days:
                    ret_city = origin_clean if (is_road_trip or not include_flights) else dest_clean
                    ret_code = origin_code if (is_road_trip or not include_flights) else dest_upper
                    ret_dep, ret_arr = ("05:30 PM", "06:00 PM") if (is_road_trip or not include_flights) else (return_dep or "03:00 PM", return_arr or "03:30 PM")
                    items.append(build_car_rental_item(f"item_car_ret_{d_num}", "Rental Vehicle Return", ret_city, ret_code, duration_days, passengers_count, cars_calculated, ret_dep, ret_arr, 0.0, False, base_lat, base_lng, is_return=True, is_road_trip=(is_road_trip or not include_flights)))

                items.sort(key=lambda it: parse_time_to_minutes(it.get("start_time") or it.get("departure_time") or it.get("time_slot") or it.get("time") or "12:00 PM"))
                active_hname = day_checkin_hotel or current_overnight_hotel or next((v for v in reversed(city_hotel_registry.values()) if v), "")
                items = enrich_items_with_next_activity(items, dest_clean, hotel_name=active_hname)
                r_info = build_google_maps_route_url(items, dest_clean)
                daily_itinerary.append({
                    "day_number": d_num, "date": d_date, "theme": day_elem.get("theme", f"Day {d_num}"),
                    "google_maps_route_url": r_info["google_maps_route_url"], "directions_url": r_info["directions_url"],
                    "map_route_url": r_info["map_route_url"], "route_summary": r_info["route_summary"],
                    "route_stops": r_info["route_stops"], "items": items,
                })

        with StepLogger.step(6, 6, "Package Bundles Assembly & Output Export", f"Destination: {dest_clean}"):
            bundles_out = build_top_3_bundles(
                dest_clean=dest_clean, origin_code=origin_code, prompt=prompt, opt_highlights=all_highlights,
                is_road_trip=is_road_trip, is_cruise=is_cruise, duration_days=duration_days, passengers_count=passengers_count,
                rooms_count=rooms_calculated, cars_count=cars_calculated, flight_cost=component_pricing.get("flight_cost", 0.0),
                hotel_cost_per_night=component_pricing.get("hotel_cost_per_night", 0.0), car_cost_total=component_pricing.get("car_cost_total", 0.0),
                is_hotel_tbd=False, is_car_tbd=False, activities_total_cost=150.0 * duration_days * passengers_count, base_itinerary=daily_itinerary,
                start_date=start_date, end_date=end_date, outbound_dep=outbound_dep, return_arr=return_arr,
                include_flights=include_flights, include_hotels=include_hotels, include_cars=include_cars,
                adults_count=adults_count, children_count=children_count, children_ages=c_ages, airline_name=airline_name,
            )

            trip_summary = bundles_out[1]["summary"] if len(bundles_out) > 1 else bundles_out[0]["summary"]
            trip_summary["itinerary_options"] = [{"tier": b["tier"], "name": b["name"], "total_price": b["total_price"], "price_per_person": b["price_per_person"], "description": b["description"]} for b in bundles_out]

            ins_fields, insights_list = build_execution_and_cache_insights(
                src_type=src_type, dest_clean=dest_clean, duration_days=duration_days,
                start_date=start_date, end_date=end_date, include_flights=include_flights,
                is_road_trip=is_road_trip, component_pricing=component_pricing,
                outbound_dep=outbound_dep, outbound_arr=outbound_arr,
                return_dep=return_dep, return_arr=return_arr, llm_meta=llm_meta,
            )
            trip_summary.update(ins_fields)
            resp_orig, resp_dest = (origin_code.upper(), dest_upper.upper()) if include_flights else (origin_clean, dest_clean)
            trip_summary["origin"], trip_summary["destination"] = resp_orig, resp_dest
            if include_flights:
                trip_summary["airline"] = trip_summary["airline_name"] = airline_name
                if isinstance(trip_summary.get("flights"), dict):
                    trip_summary["flights"]["origin"], trip_summary["flights"]["destination"], trip_summary["flights"]["airline"], trip_summary["flights"]["airline_name"] = resp_orig, resp_dest, airline_name, airline_name
            for b in bundles_out: b["origin"], b["destination"] = resp_orig, resp_dest
            meta_data = {
                "type": "planner", "title": classification["trip_category_display"], "trip_title": classification["trip_category_display"],
                **classification, "destination": resp_dest, "origin": resp_orig, "destination_city": dest_clean, "origin_city": origin_clean,
                "start_date": start_date, "end_date": end_date, "trip_duration_days": duration_days, "passengers_count": passengers_count,
                "passengers": {"adults": adults_count, "children": children_count, "children_ages": c_ages, "total": passengers_count},
                "adults_count": adults_count, "children_count": children_count, "children_ages": c_ages, "rooms_calculated": rooms_calculated,
                "cars_calculated": cars_calculated, "map_center": map_center, "llm_metadata": llm_meta or {}, **ins_fields, "trip_summary": trip_summary,
            }
            response_payload = {
                "status": "success", "timestamp": datetime.now(timezone.utc).isoformat(), "origin": resp_orig, "destination": resp_dest,
                "summary": trip_summary, "meta_data": meta_data, "bundles": bundles_out,
                "data": {"origin": resp_orig, "destination": resp_dest, "summary": trip_summary, "daily_itinerary": daily_itinerary, "bundles": bundles_out, "top_3_bundles": bundles_out, "map_pins": map_pins},
            }

            save_llm_debug_output("final_response", response_payload, identifier=dest_clean)
            if self.cache and self.cache.enabled and modular_key:
                self.cache.set(modular_key, response_payload, ttl_seconds=3600 * 24)
            return response_payload

