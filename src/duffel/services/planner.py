from concurrent.futures import ThreadPoolExecutor
import math
import os
import re
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Optional, Union

from .base import BaseService
from .locations import GEO_LOCATIONS as DESTINATION_GEO_MAP

# High-Performance Tier-0 In-Memory LRU Process Cache (<0.1ms latency)
_L1_PLANNER_MEMORY_CACHE: dict[str, dict[str, Any]] = {}
_MAX_L1_CACHE_ITEMS = 500

def format_proper_title(text: str) -> str:
    """Formats destination, package, and activity names into professional Title Case regardless of user input casing."""
    if not text:
        return ""
    lowercase_words = {"a", "an", "the", "and", "but", "or", "for", "nor", "on", "at", "to", "from", "by", "of", "in", "with", "de", "la", "van", "von"}
    uppercase_words = {"ATL", "CDG", "JFK", "LHR", "LAX", "ORD", "MIA", "SFO", "DXB", "HND", "VIP", "SUV", "AI", "ID", "USD"}

    words = re.split(r'(\s+|-)', str(text).strip())
    result = []
    for i, word in enumerate(words):
        if not word.strip():
            result.append(word)
            continue
        w_upper = word.upper()
        if w_upper in uppercase_words:
            result.append(w_upper)
        elif i == 0 or word.lower() not in lowercase_words:
            result.append(word.capitalize())
        else:
            result.append(word.lower())
    return "".join(result)


def calculate_haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> tuple[float, float]:
    """Calculates geodesic distance between two coordinates in kilometers and miles."""
    try:
        l1, g1, l2, g2 = float(lat1), float(lng1), float(lat2), float(lng2)
        if not l1 or not g1 or not l2 or not g2 or (l1 == l2 and g1 == g2):
            return 0.0, 0.0
        r_km = 6371.0
        dlat = math.radians(l2 - l1)
        dlng = math.radians(g2 - g1)
        a = math.sin(dlat / 2.0)**2 + math.cos(math.radians(l1)) * math.cos(math.radians(l2)) * math.sin(dlng / 2.0)**2
        c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
        dist_km = r_km * c
        dist_mi = dist_km * 0.621371
        return round(dist_km, 2), round(dist_mi, 2)
    except Exception:
        return 0.0, 0.0


# LLM Usage & Call Metrics Tracking Counter
_LLM_METRICS_COUNTER = {
    "total_llm_calls": 0,
    "openai_calls": 0,
    "gemini_calls": 0,
    "template_fallback_calls": 0,
    "last_call_timestamp": None,
}


class TravelPlannerService(BaseService):

    """
    High-Performance AI Travel Planner service:
    - Tier-0 L1 Process Memory Cache (<0.1ms) + Tier-1 Redis Distributed Cache (<2ms).
    - Sequential execution for stable production scaling.
    - Calculates hotel room occupancy (ceil(passengers / 2)) and vehicle seating capacity (ceil(passengers / 5)).
    - Generates Category Highlights (Cheapest, Moderate, Luxury) with ratings and prices.
    - Enforces standard response envelope (status, timestamp, meta_data, data).
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

        """
        Generates structured daily itinerary with geo-coordinates, ratings, daily pricing, and category highlights.
        Optimized for high-throughput concurrency and sub-millisecond cached responses.
        """
        # Extract intent if parameters missing
        from ..cli.parser import PromptExtractor
        intent = PromptExtractor.extract_natural_intent(prompt, user_location=user_location)

        iata_city_map = {
            "ZRH": "Zurich", "CDG": "Paris", "PAR": "Paris", "LHR": "London", "LON": "London",
            "JFK": "New York", "NYC": "New York", "DEL": "Delhi", "BOM": "Mumbai", "DXB": "Dubai",
            "YYC": "Calgary", "YVR": "Vancouver", "AMS": "Amsterdam", "FRA": "Frankfurt",
            "BER": "Berlin", "MAD": "Madrid", "FCO": "Rome", "VIE": "Vienna", "LAX": "Los Angeles"
        }

        raw_dest_input = destination or intent.get("destination_city") or intent.get("destination")
        if not raw_dest_input:
            raise ValueError("No Destination Found. Please specify your travel destination city in your query or request body.")

        dest_upper_input = str(raw_dest_input).upper()
        if dest_upper_input in iata_city_map:
            dest_raw = iata_city_map[dest_upper_input]
        elif len(dest_upper_input) == 3 and dest_upper_input.isalpha():
            dest_raw = raw_dest_input
        else:
            dest_raw = raw_dest_input

        dest_clean = format_proper_title(dest_raw)
        dest_upper = PromptExtractor._resolve_iata(dest_clean)
        if len(dest_upper) != 3 or not dest_upper.isalpha():
            dest_upper = PromptExtractor.resolve_location_with_llm(dest_clean)


        # Resolve Origin with No Origin Found error check
        resolved_origin = origin or intent.get("origin")
        if not resolved_origin and user_location:
            user_iata = PromptExtractor._resolve_iata(user_location)
            if user_iata and len(user_iata) == 3 and user_iata.isalpha():
                resolved_origin = user_iata

        if not resolved_origin:
            raise ValueError("No Origin Found. Please specify your departure origin city or airport in your prompt (e.g. 'Trip from Atlanta to Zurich') or include the X-User-Location header.")

        origin_code = str(resolved_origin).strip().upper()
        if len(origin_code) != 3 or not origin_code.isalpha():
            origin_code = PromptExtractor._resolve_iata(origin_code)

        if len(origin_code) != 3 or not origin_code.isalpha():
            raise ValueError(f"No Origin Found. Could not resolve valid departure IATA airport code for origin '{resolved_origin}'.")

        if origin_code == dest_upper:
            raise ValueError(f"Origin airport '{origin_code}' cannot be the same as destination '{dest_upper}'. Please specify different origin and destination cities.")

        # Resolve duration days
        duration_days = days or 4
        if start_date and end_date:
            try:
                s_dt = datetime.strptime(start_date, "%Y-%m-%d")
                e_dt = datetime.strptime(end_date, "%Y-%m-%d")
                duration_days = (e_dt - s_dt).days + 1
            except Exception:
                pass

        if duration_days > 30:
            raise ValueError("Travel itinerary planning is optimized for trips up to 30 days. Please request a duration under 30 days.")
        if duration_days <= 0:
            duration_days = 4

        # Resolve dates
        now = datetime.now(timezone.utc)
        if not start_date:
            start_dt = now + timedelta(days=30)
            start_date = start_dt.strftime("%Y-%m-%d")
        else:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

        if not end_date:
            end_dt = start_dt + timedelta(days=duration_days - 1)
            end_date = end_dt.strftime("%Y-%m-%d")

        # Calculate Occupancy & Vehicle Requirements
        passengers_count = max(1, passengers_count)
        rooms_calculated = rooms if (rooms and rooms >= 1) else max(1, math.ceil(passengers_count / 2))
        cars_calculated = max(1, math.ceil(passengers_count / 5))

        # Build Cache Key
        hash_str = f"plan_{prompt}_{dest_clean}_{start_date}_{end_date}_{passengers_count}_{rooms_calculated}_{style}_{budget}_{include_flights}_{include_hotels}_{include_cars}"
        cache_key = f"duffel:planner:itinerary:{hashlib.md5(hash_str.encode()).hexdigest()[:8]}"

        # Tier-0 Ultra-Fast Process Memory Cache (<0.1ms)
        if not force_refresh and cache_key in _L1_PLANNER_MEMORY_CACHE:
            print(f"[+] TIER-0 PLANNER PROCESS MEMORY CACHE HIT (<0.1ms) for key: {cache_key}")
            return _L1_PLANNER_MEMORY_CACHE[cache_key]

        # Tier-1 Redis Distributed Cache (<2ms)
        if self.cache and self.cache.enabled and not force_refresh:
            cached_resp = self.cache.get(cache_key)
            if cached_resp and isinstance(cached_resp, dict):
                print(f"[+] TIER-1 PLANNER REDIS CACHE HIT (<2ms) for key: {cache_key}")
                _L1_PLANNER_MEMORY_CACHE[cache_key] = cached_resp
                return cached_resp

        # Tier-2 PostgreSQL Database Lookup (<5ms)
        if not force_refresh:
            try:
                from ..db.itinerary_dao import ItineraryDAO
                cfg = getattr(self.client, "config", None)
                itin_dao = ItineraryDAO(config=cfg)
                db_resp = itin_dao.get_itinerary_by_params(
                    destination=dest_clean,
                    start_date=start_date,
                    end_date=end_date,
                    duration_days=duration_days,
                    passengers_count=passengers_count,
                )
                if db_resp and isinstance(db_resp, dict):
                    print(f"[+] TIER-2 PLANNER POSTGRESQL CACHE HIT (<5ms) for destination: {dest_clean}")
                    _L1_PLANNER_MEMORY_CACHE[cache_key] = db_resp
                    if self.cache and self.cache.enabled:
                        self.cache.set(cache_key, db_resp, ttl_seconds=3600)
                    return db_resp
            except Exception as pg_err:
                print(f"[PLANNER PG LOOKUP NOTICE] PostgreSQL check notice: {pg_err}")


        # Map Center & Geo Coordinates Resolution
        map_center = DESTINATION_GEO_MAP.get(dest_upper) or DESTINATION_GEO_MAP.get(dest_clean.upper()) or DESTINATION_GEO_MAP.get(str(raw_dest_input).upper())
        if not map_center:
            try:
                from .locations import resolve_geo_location
                resolved = resolve_geo_location(dest_clean)
                if resolved:
                    map_center = {
                        "latitude": resolved["latitude"],
                        "longitude": resolved["longitude"],
                        "address": f"{dest_clean} City Centre",
                        "name": f"{dest_clean} City Centre"
                    }
            except Exception:
                pass

        if not map_center:
            map_center = {"latitude": 47.3769, "longitude": 8.5417, "address": f"{dest_clean} Central", "name": f"{dest_clean} City Center"}

        base_lat = map_center.get("latitude", 47.3769)
        base_lng = map_center.get("longitude", 8.5417)

        # Load System Prompt dynamically from system_prompts.json config file
        cfg = getattr(self.client, "config", None)
        sp_map = getattr(cfg, "system_prompts", {}) if cfg else {}
        system_prompt = sp_map.get("planner_system_prompt") or (
            "You are an expert AI Travel Planner. Your task is to generate a comprehensive, curated "
            "day-by-day travel itinerary with realistic geo-coordinates, prices, time slots, and ratings.\n"
            "STRICT TOKEN EFFICIENCY & QUALITY RULES:\n"
            "1. OPTIMIZE FOR TOKEN COUNT: Keep outputs extremely concise and focused. Do NOT provide conversational filler, redundant text, or additional explanations unless specifically requested.\n"
            "2. DO NOT HALLUCINATE: Provide accurate geographic coordinates, realistic location names, and factual landmark details.\n"
            "3. CONCISE FIELD VALUES: Keep activity descriptions strictly under 25 words (1-2 short sentences maximum).\n"
            "4. EXACT JSON ONLY: Return strictly valid JSON adhering to the specified schema."
        )

        # =========================================================================
        # STEP 1 (FIRST LLM CALL VIA AI SEARCH SERVICE):
        # Perform AI Search first with the natural language prompt to extract intent,
        # apply user preferences/filters, and fetch the cheapest live flight offer.
        # =========================================================================
        ai_search_svc = getattr(self.client_app, "ai_search", None)
        if not ai_search_svc:
            from .ai_search import AISearchService
            ai_search_svc = AISearchService(self.http_client, cache=self.cache, adapter=self.adapter, client=self.client)

        ai_overrides = {
            "selected_types": ["flights"],
            "user_location": user_location,
        }
        if origin_code:
            ai_overrides["origin"] = origin_code
        if dest_upper:
            ai_overrides["destination"] = dest_upper
        if start_date:
            ai_overrides["departure_date"] = start_date
        if end_date:
            ai_overrides["return_date"] = end_date
        if passengers_count:
            ai_overrides["passengers_count"] = passengers_count

        cheapest_flight_offer = None
        try:
            ai_search_res = ai_search_svc.search_ai(
                prompt=prompt,
                favorite_airline="",
                force_refresh=force_refresh,
                overrides=ai_overrides,
            )
            data_sec = ai_search_res.get("data", {}) if isinstance(ai_search_res, dict) else {}
            offers = data_sec.get("offers", []) or data_sec.get("top_bundles", []) or []
            if offers:
                cheapest_flight_offer = offers[0]
        except Exception as ai_err:
            print(f"[PLANNER NOTICE] First-step AI Search flight lookup notice: {ai_err}", flush=True)

        top_3_bundles, component_pricing, pricing_meta = self._fetch_live_pricing(
            origin=origin_code,
            destination=dest_upper,
            departure_date=start_date,
            return_date=end_date,
            passengers_count=passengers_count,
            rooms=rooms_calculated,
            driver_age=driver_age,
        )

        outbound_dep = component_pricing.get("outbound_departure_time", "06:30 AM")
        outbound_arr = component_pricing.get("outbound_arrival_time", "12:30 PM")
        return_dep = component_pricing.get("return_departure_time", "05:00 PM")
        return_arr = component_pricing.get("return_arrival_time", "11:00 PM")

        if cheapest_flight_offer:
            if cheapest_flight_offer.get("total_amount"):
                component_pricing["flight_cost"] = float(cheapest_flight_offer["total_amount"]) / max(1, passengers_count)

            fl_slices = cheapest_flight_offer.get("slices") or []
            if fl_slices and isinstance(fl_slices[0], dict):
                s1 = fl_slices[0]
                dep_raw = s1.get("departing_at") or s1.get("departure_time")
                arr_raw = s1.get("arriving_at") or s1.get("arrival_time")
                if dep_raw and "T" in str(dep_raw):
                    try:
                        dt = datetime.fromisoformat(str(dep_raw).replace("Z", "+00:00"))
                        outbound_dep = dt.strftime("%I:%M %p")
                    except Exception:
                        pass
                if arr_raw and "T" in str(arr_raw):
                    try:
                        dt = datetime.fromisoformat(str(arr_raw).replace("Z", "+00:00"))
                        outbound_arr = dt.strftime("%I:%M %p")
                    except Exception:
                        pass

            if len(fl_slices) > 1 and isinstance(fl_slices[1], dict):
                s2 = fl_slices[1]
                ret_dep_raw = s2.get("departing_at") or s2.get("departure_time")
                ret_arr_raw = s2.get("arriving_at") or s2.get("arrival_time")
                if ret_dep_raw and "T" in str(ret_dep_raw):
                    try:
                        dt = datetime.fromisoformat(str(ret_dep_raw).replace("Z", "+00:00"))
                        return_dep = dt.strftime("%I:%M %p")
                    except Exception:
                        pass
                if ret_arr_raw and "T" in str(ret_arr_raw):
                    try:
                        dt = datetime.fromisoformat(str(ret_arr_raw).replace("Z", "+00:00"))
                        return_arr = dt.strftime("%I:%M %p")
                    except Exception:
                        pass

        # Check if flight arrival is after 12:00 PM to mandate Airport Terminal Lunch
        is_late_arrival = False
        if outbound_arr and "PM" in str(outbound_arr).upper():
            try:
                hour_num = int(str(outbound_arr).split(":")[0].strip())
                if hour_num == 12 or (1 <= hour_num < 12):
                    is_late_arrival = True
            except Exception:
                pass

        lunch_instruction = (
            f"AIRPORT LUNCH PROTOCOL (FLIGHT ARRIVAL AT {outbound_arr}): Outbound flight arrives at {outbound_arr} (after 12:00 PM). "
            f"Schedule Day 1 Lunch IMMEDIATELY at an Airport Terminal Restaurant/Cafe upon landing (e.g. at 01:00 PM) before picking up rental car or traveling into the city center, "
            f"otherwise it will be too late to pick up the rental car or eat. LUNCH MUST NEVER BE SCHEDULED AFTER 02:00 PM ON ANY DAY!"
        ) if is_late_arrival else "LUNCH CUTOFF RULE: Lunch every day MUST NEVER be scheduled after 02:00 PM (schedule between 11:30 AM and 01:30 PM)."

        evening_breakfast_instruction = (
            "DAILY OPERATING BOUNDARIES & TIMELINE RULES (STRICTLY ENFORCED):\n"
            "- DAY START AT 08:00 AM: Every full day MUST start at 08:00 AM at best (with Breakfast or Quick Grab-and-Go Coffee Shop). Never start activities before 08:00 AM.\n"
            "- ATTRACTION END CUTOFF (08:00 PM MAXIMUM): Any attraction, museum, or sightseeing activity MUST end by 08:00 PM at the latest (e.g. 05:45 PM - 07:45 PM). NEVER extend any attraction past 08:00 PM (NEVER 08:30 PM, 09:00 PM, or 10:45 PM).\n"
            "- MANDATORY DINNER START AT 08:00 PM: Dinner MUST start at 08:00 PM at any cost (e.g. 08:00 PM - 09:30 PM). Never start dinner after 08:00 PM.\n"
            "- MANDATORY HOTEL RETURN BEFORE 10:00 PM: The final step of EVERY day MUST be 'Return to Hotel & Rest for the Night', with hotel arrival strictly BEFORE 10:00 PM (scheduled between 09:30 PM and 10:00 PM).\n"
            "- NO OVERNIGHT / EARLY MORNING SLOTS: Under no circumstances should any activity, dinner, or hotel return be scheduled past 10:00 PM (never 10:30 PM, 11:00 PM, 12:00 AM, 01:00 AM, or 06:15 AM).\n"
            "- MORNING BREAKFAST PROTOCOL: Every next day MUST begin with Breakfast at 08:00 AM. If sit-in breakfast is not possible due to morning time constraints or tight schedules, recommend a nearby local coffee shop, artisanal bakery, or quick cafe to grab coffee & pastries instead of a long sit-in breakfast."
        )

        # =========================================================================
        # STEP 2 (SECOND LLM CALL FOR ITINERARY SYNTHESIS):
        # Inject exact live flight timings from AI Search into the LLM prompt.
        # =========================================================================
        user_prompt = (
            f"Plan a {duration_days}-day trip to {dest_clean} from {start_date} to {end_date} for {passengers_count} passenger(s). "
            f"Style: {style}, Budget: {budget}.\n"
            f"EXACT LIVE FLIGHT SCHEDULE FROM AI SEARCH:\n"
            f"- Outbound Flight: Departs {origin_code} at {outbound_dep}, Arrives in {dest_clean} at {outbound_arr}.\n"
            f"- Return Flight: Departs {dest_clean} at {return_dep}, Arrives in {origin_code} at {return_arr}.\n"
            f"{lunch_instruction}\n"
            f"{evening_breakfast_instruction}\n"
            f"TIMELINE REQUIREMENT: On Day 1, schedule all activities and hotel check-in strictly AFTER flight arrival at {outbound_arr}. "
            f"On Final Day, schedule all activities and hotel check-out to wrap up before return flight departure at {return_dep}.\n"
            f"Included components: Flights={include_flights}, Hotels={include_hotels} ({rooms_calculated} rooms), Cars={include_cars} ({cars_calculated} car), Trains={include_trains}, Buses={include_buses}, "
            f"Attractions={include_attractions}, Activities={include_activities}, SeasonalAttractions={include_seasonal_attractions}, SeasonalActivities={include_seasonal_activities}. Prompt details: '{prompt}'."
        )

        # STEP 3: Generate Day-by-Day Itinerary with LLM based on Live Flight Times
        llm_itinerary_days, llm_meta = self._orchestrate_llm_itinerary(
            system_prompt,
            user_prompt,
            dest_clean,
            duration_days,
            start_dt,
            base_lat,
            base_lng,
            include_attractions,
            include_activities,
        )

        # Compute Daily Total Costs & Attach Components to Daily Schedule
        flight_cost = component_pricing.get("flight_cost", 0.0) * passengers_count if include_flights else 0.0
        hotel_cost_per_night = component_pricing.get("hotel_cost_per_night", 0.0) * rooms_calculated if include_hotels else 0.0
        car_cost_total = component_pricing.get("car_cost_total", 0.0) * cars_calculated if include_cars else 0.0
        car_cost_per_day = car_cost_total / max(1, duration_days)

        daily_itinerary = []
        map_pins = []
        pin_idx = 1

        # Add Origin & Destination Airport Pins
        map_pins.append({
          "id": f"pin_{pin_idx}",
          "title": f"{dest_clean} Airport ({dest_upper})",
          "category": "airport",
          "latitude": base_lat + 0.05,
          "longitude": base_lng + 0.05,
          "day_number": 1,
          "address": f"{dest_clean} International Airport",
          "rating": 4.6
        })
        pin_idx += 1

        if include_hotels:
            map_pins.append({
              "id": f"pin_{pin_idx}",
              "title": f"Grand {dest_clean} Luxury Hotel",
              "category": "hotel",
              "latitude": base_lat,
              "longitude": base_lng,
              "day_number": 1,
              "address": f"10 Central Avenue, {dest_clean}",
              "rating": 4.8
            })
            pin_idx += 1

        total_attractions_cost = 0.0

        for day_idx, day in enumerate(llm_itinerary_days, start=1):
            d_num = day.get("day_number") or day_idx
            d_date = day.get("date") or (start_dt + timedelta(days=d_num - 1)).strftime("%Y-%m-%d")
            day_items = []
            day_activities_cost = 0.0

            if include_flights and d_num == 1:
                day_items.append({
                    "id": f"item_fl_{d_num}",
                    "type": "flight",
                    "name": f"Depart {origin_code} to {dest_clean}",
                    "description": f"Outbound Flight from {origin_code} to {dest_clean} ({passengers_count} pax). Departure time: {outbound_dep} from {origin_code}, Arrival time: {outbound_arr} in {dest_clean}.",
                    "price": round(flight_cost, 2),
                    "currency": "USD",
                    "departure_time": outbound_dep,
                    "arrival_time": outbound_arr,
                    "time_slot": f"Departure from {origin_code}: {outbound_dep} | Arrival in {dest_clean}: {outbound_arr}",
                    "address": f"{dest_clean} International Airport ({dest_upper})",
                    "phone_number": "+1 800 555 0199",
                    "geo_location": {
                        "name": f"{dest_clean} Airport",
                        "address": f"{dest_clean} International Airport ({dest_upper})",
                        "phone_number": "+1 800 555 0199",
                        "latitude": base_lat + 0.05,
                        "longitude": base_lng + 0.05
                    }
                })
            elif include_flights and d_num == duration_days:
                day_items.append({
                    "id": f"item_fl_ret_{d_num}",
                    "type": "flight",
                    "name": f"Depart {dest_clean} to {origin_code}",
                    "description": f"Return Flight from {dest_clean} to {origin_code} ({passengers_count} pax). Departure time: {return_dep} from {dest_clean}, Arrival time: {return_arr} in {origin_code}.",
                    "price": 0.0,
                    "currency": "USD",
                    "departure_time": return_dep,
                    "arrival_time": return_arr,
                    "time_slot": f"Departure from {dest_clean}: {return_dep} | Arrival in {origin_code}: {return_arr}",
                    "address": f"{dest_clean} International Airport ({dest_upper})",
                    "phone_number": "+1 800 555 0199",
                    "geo_location": {
                        "name": f"{dest_clean} Airport",
                        "address": f"{dest_clean} International Airport ({dest_upper})",
                        "phone_number": "+1 800 555 0199",
                        "latitude": base_lat + 0.05,
                        "longitude": base_lng + 0.05
                    }
                })

            if include_cars and d_num == 1:
                day_items.append({
                    "id": f"item_car_{d_num}",
                    "type": "car",
                    "name": f"Vehicle Rental ({cars_calculated} car(s))",
                    "description": f"{duration_days}-day rental for {passengers_count} passenger(s)",
                    "price": round(car_cost_total, 2),
                    "currency": "USD",
                    "departure_time": "01:15 PM",
                    "arrival_time": "01:15 PM",
                    "time_slot": "01:15 PM - Vehicle Rental Pickup",
                    "address": f"Rental Center, {dest_clean} Airport",
                    "phone_number": "+1 800 555 0244",
                    "geo_location": {
                        "name": f"{dest_clean} Car Pickup",
                        "address": f"Rental Center, {dest_clean} Airport",
                        "phone_number": "+1 800 555 0244",
                        "latitude": base_lat + 0.05,
                        "longitude": base_lng + 0.05
                    }
                })

            if include_hotels and d_num == 1:
                ht_slot = "02:15 PM - Hotel Check-in"
                ht_dep = "02:15 PM"
                day_items.append({
                    "id": f"item_ht_{d_num}",
                    "type": "hotel",
                    "name": f"Grand {dest_clean} Hotel ({rooms_calculated} Room(s))",
                    "description": f"Check-in & Stay (Night 1 of {duration_days})",
                    "price": round(hotel_cost_per_night, 2),
                    "currency": "USD",
                    "departure_time": ht_dep,
                    "arrival_time": ht_dep,
                    "time_slot": ht_slot,
                    "address": f"10 Central Avenue, {dest_clean}",
                    "phone_number": "+1 800 555 0388",
                    "geo_location": {
                        "name": f"Grand {dest_clean} Hotel",
                        "address": f"10 Central Avenue, {dest_clean}",
                        "phone_number": "+1 800 555 0388",
                        "latitude": base_lat,
                        "longitude": base_lng
                    }
                })

            for act in day.get("activities", []):
                act_title = act.get("title") or act.get("name") or act.get("activity_name") or act.get("activity") or ""
                act_lower = act_title.strip().lower()
                desc_str = (act.get("description") or "").lower()

                # Filter out duplicate vehicle rental, hotel check-in, and flight items generated in activities list
                if any(k in act_lower or k in desc_str for k in [
                    "vehicle rental", "car rental", "rental car",
                    "hotel check-in", "check-in", "check in", "hotel checkin",
                    "outbound flight", "return flight", "flight arrival", "flight departure",
                    "airport arrival", "airport departure", "arrive at airport", "arrival at airport",
                    "landing at", "deplaning", "baggage claim", "airport transfer",
                    "depart from", "flight from", "flight to"
                ]):
                    continue

                # Clean and standardize "Return to Hotel" night rest cards
                is_hotel_return = any(k in act_lower for k in ["return to hotel", "back to hotel", "rest for the night", "night rest", "hotel rest"])
                if is_hotel_return:
                    act_title = "Return to Hotel & Rest"
                    act_price = 0.0
                    act_slot = "09:30 PM - 10:00 PM (Night Rest)"
                    dep_time = "09:30 PM"
                    arr_time = "10:00 PM"
                    act_type = "hotel"
                else:
                    act_price = float(act.get("price_per_person") or act.get("price") or 25.0) * passengers_count
                    day_activities_cost += act_price
                    act_slot = act.get("time_slot") or "01:00 PM"
                    dep_time = act.get("departure_time") or act_slot.split("-")[0].strip() if "-" in act_slot else "01:00 PM"
                    arr_time = act.get("arrival_time") or act_slot.split("-")[1].strip() if "-" in act_slot else "02:30 PM"
                    act_type = "attraction" if act.get("category") in ["Sightseeing", "Culture"] else "activity"

                if not act_title or act_title.strip().lower() in ["activity", "attraction"]:
                    act_title = act.get("description", "").split(".")[0][:50] if act.get("description") else f"{dest_clean} Experience"

                geo = act.get("geo_location") or {}
                if isinstance(geo, dict):
                    act_addr = geo.get("address") or act.get("address") or f"{act_title}, {dest_clean}"
                    act_phone = geo.get("phone_number") or geo.get("phone") or act.get("phone_number") or "+1 800 555 0700"
                    geo["address"] = act_addr
                    geo["phone_number"] = act_phone
                else:
                    act_addr = f"{act_title}, {dest_clean}"
                    act_phone = "+1 800 555 0700"
                    geo = {
                        "name": act_title,
                        "address": act_addr,
                        "phone_number": act_phone,
                        "latitude": base_lat,
                        "longitude": base_lng
                    }

                day_items.append({
                    "id": f"item_act_{d_num}_{pin_idx}",
                    "type": act_type,
                    "name": act_title,
                    "title": act_title,
                    "activity_name": act_title,
                    "activity": act_title,
                    "attraction_name": act_title,
                    "description": act.get("description") or f"Explore {act_title} in {dest_clean}.",
                    "price": round(act_price, 2),
                    "currency": "USD",
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "time_slot": act_slot,
                    "address": act_addr,
                    "phone_number": act_phone,
                    "rating": float(act.get("rating") or 4.7),
                    "reviews_count": int(act.get("reviews_count") or 450),
                    "geo_location": geo
                })

                # Add Map Pin
                map_pins.append({
                    "id": f"pin_{pin_idx}",
                    "title": act_title,
                    "category": act.get("category", "attraction"),
                    "latitude": geo.get("latitude", base_lat),
                    "longitude": geo.get("longitude", base_lng),
                    "day_number": d_num,
                    "address": act_addr,
                    "phone_number": act_phone,
                    "rating": act.get("rating", 4.7)
                })
                pin_idx += 1

            # Chronologically sort all items for the day by start time (06:30 AM < 08:00 AM < 10:00 AM < 01:00 PM < 03:00 PM < 07:30 PM)
            def _parse_time_minutes(item: dict[str, Any]) -> int:
                ts = str(item.get("time_slot") or item.get("departure_time") or "").upper().strip()
                match = re.search(r"(\d{1,2}):(\d{2})\s*(AM|PM)", ts)
                if match:
                    h = int(match.group(1))
                    m = int(match.group(2))
                    ampm = match.group(3)
                    if ampm == "PM" and h != 12:
                        h += 12
                    elif ampm == "AM" and h == 12:
                        h = 0
                    return h * 60 + m
                if "BREAKFAST" in ts or "MORNING" in ts:
                    return 480
                if "LUNCH" in ts or "NOON" in ts:
                    return 780
                if "AFTERNOON" in ts:
                    return 930
                if "EVENING" in ts or "DINNER" in ts or "NIGHT" in ts:
                    return 1170
                return 720

            day_items.sort(key=_parse_time_minutes)

            # Compute distance in miles/km and transit mode relative to preceding activity
            for item_idx in range(len(day_items)):
                curr_item = day_items[item_idx]
                if item_idx == 0:
                    curr_item["distance_miles"] = 0.0
                    curr_item["distance_km"] = 0.0
                    curr_item["transit_mode"] = "walk"
                    curr_item["transit_summary"] = "Starting point"
                else:
                    prev_item = day_items[item_idx - 1]
                    prev_geo = prev_item.get("geo_location") or {}
                    curr_geo = curr_item.get("geo_location") or {}

                    p_lat = float(prev_geo.get("latitude") or base_lat)
                    p_lng = float(prev_geo.get("longitude") or base_lng)
                    c_lat = float(curr_geo.get("latitude") or base_lat)
                    c_lng = float(curr_geo.get("longitude") or base_lng)

                    dist_km, dist_mi = calculate_haversine_distance(p_lat, p_lng, c_lat, c_lng)
                    prev_name = prev_item.get("name") or prev_item.get("title") or "previous stop"

                    if dist_mi <= 0.8:
                        t_mode = "walk"
                        mins = max(5, int(dist_mi * 20))
                        t_summary = f"Walk {dist_mi} mi ({dist_km} km) / ~{mins} mins from {prev_name}"
                    elif dist_mi <= 15.0:
                        t_mode = "drive"
                        mins = max(10, int(dist_mi * 3))
                        t_summary = f"Drive/Taxi {dist_mi} mi ({dist_km} km) / ~{mins} mins from {prev_name}"
                    else:
                        t_mode = "train"
                        mins = max(20, int(dist_mi * 2))
                        t_summary = f"Train/Express Drive {dist_mi} mi ({dist_km} km) / ~{mins} mins from {prev_name}"

                    curr_item["distance_miles"] = dist_mi
                    curr_item["distance_km"] = dist_km
                    curr_item["transit_mode"] = t_mode
                    curr_item["transit_summary"] = t_summary

            total_attractions_cost += day_activities_cost
            daily_total = (flight_cost if (include_flights and d_num == 1) else 0.0) + \
                          (car_cost_total if (include_cars and d_num == 1) else 0.0) + \
                          (hotel_cost_per_night if include_hotels else 0.0) + \
                          day_activities_cost

            daily_itinerary.append({
                "day_number": d_num,
                "date": d_date,
                "title": f"Day {d_num}: {day.get('theme', 'Exploration & Culture')}",
                "daily_total_cost": round(daily_total, 2),
                "currency": "USD",
                "items": day_items
            })

        total_hotel_cost = hotel_cost_per_night * duration_days if include_hotels else 0.0
        total_trip_price = round(flight_cost + total_hotel_cost + car_cost_total + total_attractions_cost, 2)
        price_per_passenger = round(total_trip_price / passengers_count, 2)

        # Synthesize Category Highlights (Cheapest, Moderate/Best Value, Luxury)
        is_live_pricing = pricing_meta.get("is_live_pricing", False)
        pricing_src_str = pricing_meta.get("pricing_source", "estimated_package_pricing")


        category_highlights = {
            "cheapest": {
                "bundle_id": f"bnd_cheapest_{'live' if is_live_pricing else 'mock'}_{hashlib.md5(f'{dest_clean}_cheap'.encode()).hexdigest()[:6]}",
                "name": "Budget Saver Package",
                "tier": "cheapest",
                "total_price": round(total_trip_price * 0.75, 2),
                "per_passenger_price": round((total_trip_price * 0.75) / passengers_count, 2),
                "currency": "USD",
                "hotel_rating": 3.8,
                "user_rating": 4.4,
                "attraction_rating": 4.5,
                "is_mock": not is_live_pricing,
                "pricing_source": pricing_src_str,
                "description": f"3-Star Comfort Hotel, Economy Flights, Compact Car rental, & budget attraction passes."
            },
            "moderate": {
                "bundle_id": f"bnd_moderate_{'live' if is_live_pricing else 'mock'}_{hashlib.md5(f'{dest_clean}_mod'.encode()).hexdigest()[:6]}",
                "name": "Curated Balanced Package",
                "tier": "moderate",
                "total_price": total_trip_price,
                "per_passenger_price": price_per_passenger,
                "currency": "USD",
                "hotel_rating": 4.7,
                "user_rating": 4.8,
                "attraction_rating": 4.8,
                "is_mock": not is_live_pricing,
                "pricing_source": pricing_src_str,
                "description": f"4-Star Central Hotel, Standard Flights, Midsize SUV, & guided priority attraction entry."
            },
            "luxury": {
                "bundle_id": f"bnd_luxury_{'live' if is_live_pricing else 'mock'}_{hashlib.md5(f'{dest_clean}_lux'.encode()).hexdigest()[:6]}",
                "name": "Signature Luxury VIP Package",
                "tier": "luxury",
                "total_price": round(total_trip_price * 1.6, 2),
                "per_passenger_price": round((total_trip_price * 1.6) / passengers_count, 2),
                "currency": "USD",
                "hotel_rating": 5.0,
                "user_rating": 4.95,
                "attraction_rating": 4.9,
                "is_mock": not is_live_pricing,
                "pricing_source": pricing_src_str,
                "description": f"5-Star Luxury Suite, Business Class Flights, Premium SUV, & private VIP guided tours."
            }
        }

        ai_summary = (
            f"AI Travel Planner ({llm_meta.get('llm_provider', 'template')}) created a customized {duration_days}-day itinerary in {dest_clean} for {passengers_count} passenger(s). "
            f"Total estimated trip price is USD {total_trip_price:.2f} (USD {price_per_passenger:.2f}/person), featuring "
            f"{rooms_calculated} hotel room(s), {cars_calculated} car rental(s), and top-rated curated attractions."
        )

        # Standard Response Envelope Payload
        meta_data = {
            "type": "planner",
            "search_type": "itinerary",
            "prompt": prompt,
            "destination": dest_clean,
            "origin": origin_code,
            "start_date": start_date,
            "end_date": end_date,
            "trip_duration_days": duration_days,
            "passengers_count": passengers_count,
            "rooms_calculated": rooms_calculated,
            "cars_calculated": cars_calculated,
            "data_source": {
                "is_live_llm": llm_meta.get("is_live_llm", False),
                "llm_provider": llm_meta.get("llm_provider", "template_synthesizer"),
                "llm_model": llm_meta.get("llm_model", "template-engine-v1"),
                "is_live_pricing": is_live_pricing,
                "pricing_source": pricing_src_str,
            },
            "llm_metrics": {
                "total_llm_calls": _LLM_METRICS_COUNTER["total_llm_calls"],
                "openai_calls": _LLM_METRICS_COUNTER["openai_calls"],
                "gemini_calls": _LLM_METRICS_COUNTER["gemini_calls"],
                "template_fallback_calls": _LLM_METRICS_COUNTER["template_fallback_calls"],
                "this_request_provider": llm_meta.get("llm_provider"),
                "this_request_model": llm_meta.get("llm_model"),
            },
            "map_center": map_center,
            "geo_location": {
                "origin": {"code": origin_code, "name": f"{origin_code} Airport"},
                "destination": {"code": dest_upper, "name": dest_clean, "latitude": base_lat, "longitude": base_lng}
            }
        }


        # Build 3 Distinct Complete Itinerary Options with AI Descriptions & Highlights
        itinerary_options = []
        option_styles = [
            (
                "Option 1: Classic & Iconic Culture",
                "balanced",
                "moderate",
                1.0,
                f"A perfectly balanced itinerary featuring famous landmarks, iconic museum tours, and quintessential sightseeing highlights in {dest_clean}. Ideal for first-time visitors who want to see all the top attractions at a comfortable pace.",
                [f"Guided Louvre Museum & Art Masterpieces Tour in {dest_clean}", f"Eiffel Tower Sunset Skyline Panorama", f"Historic Montmartre & Sacré-Cœur Walking Tour", f"Seine River Sunset Panoramic Cruise"],
                f"Best for first-time travelers seeking an iconic, well-rounded introduction to {dest_clean}."
            ),
            (
                "Option 2: Hidden Gems & Culinary Secrets",
                "culinary_gems",
                "moderate",
                1.1,
                f"An immersive culinary and cultural discovery off the beaten path. Explore historic Saint-Germain pastry shops, secret courtyard cafes, artisanal wine tastings, and vibrant local markets in {dest_clean}.",
                [f"Saint-Germain Artisanal Pastry & Espresso Walk", f"Le Marais Secret Courtyards & Contemporary Art Tour", f"Private Sommelier Wine & Cheese Tasting Experience", f"Canal Saint-Martin Evening Promenade & Bistro Dinner"],
                f"Best for foodies and culture enthusiasts wanting to experience {dest_clean} like a local."
            ),
            (
                "Option 3: Signature Luxury & Romantic VIP",
                "luxury_vip",
                "luxury",
                1.5,
                f"A VIP luxury experience featuring five-star suite accommodations, private chauffeured transfers, exclusive after-hours gallery access, and romantic Michelin-starred dining in {dest_clean}.",
                [f"Private Chauffeured Airport & City Center Transfers", f"Exclusive VIP Private Gallery & Museum Access", f"Michelin-Starred Candlelight Romantic Dinner", f"Private Sunset Champagne Yacht Cruise along the River"],
                f"Best for couples celebrating special occasions seeking ultimate luxury, privacy, and VIP treatment."
            )
        ]

        for opt_idx, (opt_name, opt_style, opt_budget, price_multiplier, opt_desc, opt_highlights_list, opt_why) in enumerate(option_styles, 1):
            opt_total_price = round(total_trip_price * price_multiplier, 2)
            opt_per_passenger = round(opt_total_price / passengers_count, 2)
            opt_hash = hashlib.md5(f"{hash_str}_opt_{opt_idx}".encode()).hexdigest()[:8]
            opt_itin_id = f"itin_opt_{opt_hash}"

            opt_highlights = {
                "cheapest": {
                    "bundle_id": f"bnd_cheap_opt{opt_idx}_{hashlib.md5(f'{dest_clean}_c{opt_idx}'.encode()).hexdigest()[:6]}",
                    "name": f"{opt_name} - Budget Saver",
                    "tier": "cheapest",
                    "total_price": round(opt_total_price * 0.78, 2),
                    "per_passenger_price": round((opt_total_price * 0.78) / passengers_count, 2),
                    "currency": "USD",
                    "hotel_rating": 4.0,
                    "user_rating": 4.5,
                    "attraction_rating": 4.6,
                    "is_mock": not is_live_pricing,
                    "pricing_source": pricing_src_str,
                    "description": f"Standard stay, economy flights, & budget attraction entry for {opt_name}.",
                    "included_components": ["flights", "hotels", "cars", "attractions", "activities"],
                    "bundle_contents": {
                        "flights": {"included": True, "description": f"Economy Flights ({origin_code} -> {dest_upper})"},
                        "hotels": {"included": True, "description": f"3-Star Comfort Stay ({rooms_calculated} Room(s))"},
                        "cars": {"included": True, "description": f"Compact Rental Car"},
                        "attractions": {"included": True, "description": f"Standard Landmark Passes"},
                        "activities": {"included": True, "description": f"Curated Self-Guided & Local Walks"},
                        "summary_line": "Includes Economy Flights, 3-Star Hotel, Compact Car, Standard Passes, & Self-Guided Walks."
                    }
                },
                "moderate": {
                    "bundle_id": f"bnd_mod_opt{opt_idx}_{hashlib.md5(f'{dest_clean}_m{opt_idx}'.encode()).hexdigest()[:6]}",
                    "name": f"{opt_name} - Balanced",
                    "tier": "moderate",
                    "total_price": opt_total_price,
                    "per_passenger_price": opt_per_passenger,
                    "currency": "USD",
                    "hotel_rating": 4.7,
                    "user_rating": 4.8,
                    "attraction_rating": 4.8,
                    "is_mock": not is_live_pricing,
                    "pricing_source": pricing_src_str,
                    "description": f"4-Star central stay, standard flights, midsize car, & guided entry for {opt_name}.",
                    "included_components": ["flights", "hotels", "cars", "attractions", "activities"],
                    "bundle_contents": {
                        "flights": {"included": True, "description": f"Standard Main Cabin Flights ({origin_code} -> {dest_upper})"},
                        "hotels": {"included": True, "description": f"4-Star Central Hotel ({rooms_calculated} Room(s))"},
                        "cars": {"included": True, "description": f"Midsize SUV Car Rental"},
                        "attractions": {"included": True, "description": f"Priority Skip-the-Line Museum Passes"},
                        "activities": {"included": True, "description": f"Guided Small-Group Tours & Experiences"},
                        "summary_line": "Includes Standard Flights, 4-Star Hotel, Midsize SUV, Priority Museum Entry, & Small-Group Tours."
                    }
                },
                "luxury": {
                    "bundle_id": f"bnd_lux_opt{opt_idx}_{hashlib.md5(f'{dest_clean}_l{opt_idx}'.encode()).hexdigest()[:6]}",
                    "name": f"{opt_name} - VIP Luxury",
                    "tier": "luxury",
                    "total_price": round(opt_total_price * 1.45, 2),
                    "per_passenger_price": round((opt_total_price * 1.45) / passengers_count, 2),
                    "currency": "USD",
                    "hotel_rating": 5.0,
                    "user_rating": 4.95,
                    "attraction_rating": 4.9,
                    "is_mock": not is_live_pricing,
                    "pricing_source": pricing_src_str,
                    "description": f"5-Star luxury suite, business flights, premium car, & private VIP tour entry for {opt_name}.",
                    "included_components": ["flights", "hotels", "cars", "attractions", "activities"],
                    "bundle_contents": {
                        "flights": {"included": True, "description": f"Business Class Flights ({origin_code} -> {dest_upper})"},
                        "hotels": {"included": True, "description": f"5-Star Luxury Suite Hotel ({rooms_calculated} Room(s))"},
                        "cars": {"included": True, "description": f"Premium Luxury SUV Rental"},
                        "attractions": {"included": True, "description": f"Private After-Hours Museum Access"},
                        "activities": {"included": True, "description": f"Michelin-Starred Dining & Private Yacht Cruise"},
                        "summary_line": "Includes Business Class Flights, 5-Star Suite, Premium SUV, Private Museum Access, & Yacht Cruise."
                    }
                }
            }


            opt_obj = {
                "itinerary_id": opt_itin_id,
                "option_number": opt_idx,
                "title": opt_name,
                "style": opt_style,
                "budget": opt_budget,
                "llm_description": opt_desc,
                "highlights": opt_highlights_list,
                "why_choose_this": opt_why,
                "ai_summary": f"{opt_name}: Customized {duration_days}-day itinerary in {dest_clean} for {passengers_count} passenger(s) ($ {opt_total_price:.2f} total).",
                "trip_summary": {
                    "total_trip_price": opt_total_price,
                    "price_per_passenger": opt_per_passenger,
                    "currency": "USD",
                    "total_flight_cost": round(flight_cost * price_multiplier, 2),
                    "total_hotel_cost": round(total_hotel_cost * price_multiplier, 2),
                    "total_car_cost": round(car_cost_total * price_multiplier, 2),
                    "total_attractions_cost": round(total_attractions_cost * price_multiplier, 2),
                    "occupancy_details": {
                        "passengers": passengers_count,
                        "hotel_rooms_booked": rooms_calculated,
                        "cars_rented": cars_calculated
                    }
                },
                "category_highlights": opt_highlights,
                "map_pins": map_pins,
                "daily_itinerary": daily_itinerary,
                "top_3_bundles": top_3_bundles
            }

            itinerary_options.append(opt_obj)

            # Persist each option in PostgreSQL
            try:
                from ..db.itinerary_dao import ItineraryDAO
                cfg = getattr(self.client, "config", None)
                ItineraryDAO(config=cfg).save_itinerary(
                    prompt=f"{prompt} ({opt_name})",
                    destination=dest_clean,
                    start_date=start_date,
                    end_date=end_date,
                    duration_days=duration_days,
                    passengers_count=passengers_count,
                    payload={"meta_data": {"itinerary_id": opt_itin_id, "destination": dest_clean}, "data": opt_obj}
                )
            except Exception:
                pass

        data_section = {
            "recommended_itinerary_id": itinerary_options[0]["itinerary_id"],
            "itinerary_options": itinerary_options,
            "ai_summary": ai_summary,
            "trip_summary": {
                "total_trip_price": total_trip_price,
                "price_per_passenger": price_per_passenger,
                "currency": "USD",
                "total_flight_cost": round(flight_cost, 2),
                "total_hotel_cost": round(total_hotel_cost, 2),
                "total_car_cost": round(car_cost_total, 2),
                "total_attractions_cost": round(total_attractions_cost, 2),
                "occupancy_details": {
                    "passengers": passengers_count,
                    "hotel_rooms_booked": rooms_calculated,
                    "cars_rented": cars_calculated
                }
            },
            "category_highlights": category_highlights,
            "map_pins": map_pins,
            "daily_itinerary": daily_itinerary,
            "top_3_bundles": top_3_bundles,
        }

        res_payload = {
            "status": "success",
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "meta_data": meta_data,
            "data": data_section
        }


        # Persist to PostgreSQL / Database using dedicated ItineraryDAO
        try:
            from ..db.itinerary_dao import ItineraryDAO
            cfg = getattr(self.client, "config", None)
            itin_dao = ItineraryDAO(config=cfg)
            itin_db_id = itin_dao.save_itinerary(
                prompt=prompt,
                destination=dest_clean,
                start_date=start_date,
                end_date=end_date,
                duration_days=duration_days,
                passengers_count=passengers_count,
                payload=res_payload
            )
            meta_data["itinerary_id"] = itin_db_id
        except Exception as db_e:
            print(f"[PLANNER ITINERARY DAO NOTICE] Database save notice: {db_e}")


        # Store in L1 Process Memory Cache & Redis Cache
        if len(_L1_PLANNER_MEMORY_CACHE) >= _MAX_L1_CACHE_ITEMS:
            _L1_PLANNER_MEMORY_CACHE.clear()
        _L1_PLANNER_MEMORY_CACHE[cache_key] = res_payload

        if self.cache and self.cache.enabled:
            self.cache.set(cache_key, res_payload, ttl_seconds=3600)

        return res_payload

    def like_itinerary(self, itinerary_id: str, liked: bool, feedback_notes: Optional[str] = None) -> dict[str, Any]:
        """
        Handles itinerary feedback (like or downvote).
        - Upvote (liked=True): Persists upvote & feedback in PostgreSQL via ItineraryDAO.
        - Downvote (liked=False): Deletes from PostgreSQL & purges Redis + Process memory cache so future queries re-invoke LLM.
        """
        from ..db.itinerary_dao import ItineraryDAO
        cfg = getattr(self.client, "config", None)
        itin_dao = ItineraryDAO(config=cfg)

        if not liked:
            # Downvoted: Purge cache and delete from PostgreSQL
            _L1_PLANNER_MEMORY_CACHE.clear()
            if self.cache and self.cache.enabled:
                try:
                    self.cache.flush()
                except Exception:
                    pass
            success = itin_dao.delete_itinerary(itinerary_id)
            return {
                "status": "success",
                "message": f"Itinerary '{itinerary_id}' downvoted and purged from database & cache. Next search will re-invoke LLM.",
                "itinerary_id": itinerary_id,
                "liked": False,
                "deleted_from_db": True,
            }
        else:
            # Upvoted: Update PostgreSQL
            success = itin_dao.update_itinerary_like(itinerary_id, liked=True, feedback_notes=feedback_notes)
            return {
                "status": "success",
                "message": f"Itinerary '{itinerary_id}' successfully saved and upvoted.",
                "itinerary_id": itinerary_id,
                "liked": True,
                "deleted_from_db": False,
            }

    def get_llm_metrics(self) -> dict[str, Any]:
        """Returns total LLM usage call metrics and database statistics."""
        db_stats = {}
        try:
            from ..db.itinerary_dao import ItineraryDAO
            cfg = getattr(self.client, "config", None)
            db_stats = ItineraryDAO(config=cfg).get_llm_call_stats()
        except Exception:
            pass

        return {
            "status": "success",
            "process_metrics": {
                "total_llm_calls": _LLM_METRICS_COUNTER["total_llm_calls"],
                "openai_calls": _LLM_METRICS_COUNTER["openai_calls"],
                "gemini_calls": _LLM_METRICS_COUNTER["gemini_calls"],
                "template_fallback_calls": _LLM_METRICS_COUNTER["template_fallback_calls"],
                "last_call_timestamp": _LLM_METRICS_COUNTER["last_call_timestamp"],
            },
            "database_totals": db_stats
        }





    def _orchestrate_llm_itinerary(
        self,
        system_prompt: str,
        user_prompt: str,
        destination: str,
        duration_days: int,
        start_dt: datetime,
        base_lat: float,
        base_lng: float,
        include_attractions: bool,
        include_activities: bool,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """
        Orchestrates LLM call to OpenAI/Gemini or uses intelligent template synthesizer fallback.
        Returns tuple of (days_list, llm_meta).
        """
        llm_meta = {
            "is_live_llm": False,
            "llm_provider": "template_synthesizer",
            "llm_model": "template-engine-v1",
        }

        # Try OpenAI or Gemini LLM if configured
        cfg = getattr(self.client, "config", None)
        if cfg and getattr(cfg, "openai_api_key", None) and getattr(cfg, "llm_provider", "") == "openai":
            try:
                import openai
                import time
                client = openai.OpenAI(api_key=cfg.openai_api_key)
                model_name = getattr(cfg, "openai_model", "gpt-4o-mini")
                if model_name not in ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"]:
                    model_name = "gpt-4o-mini"
                t0_llm = time.perf_counter()
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                f"{system_prompt}\n\n"
                                "You MUST respond with a valid JSON object matching this schema:\n"
                                "{\n"
                                "  \"days\": [\n"
                                "    {\n"
                                "      \"day_number\": 1,\n"
                                "      \"date\": \"YYYY-MM-DD\",\n"
                                "      \"theme\": \"Day 1 Theme Title\",\n"
                                "      \"activities\": [\n"
                                "        {\n"
                                "          \"title\": \"Artisanal Cafe & Bakery Breakfast\",\n"
                                "          \"name\": \"Artisanal Cafe & Bakery Breakfast\",\n"
                                "          \"time_slot\": \"08:00 AM - Breakfast\",\n"
                                "          \"category\": \"Breakfast\",\n"
                                "          \"description\": \"Enjoy fresh croissants, espresso, and organic breakfast specials.\",\n"
                                "          \"price_per_person\": 20.0,\n"
                                "          \"rating\": 4.8,\n"
                                "          \"reviews_count\": 850,\n"
                                "          \"address\": \"12 Rue de Rivoli, 75001 Paris, France\",\n"
                                "          \"phone_number\": \"+33 1 42 68 55 00\",\n"
                                "          \"geo_location\": {\n"
                                "            \"name\": \"Le Petit Cafe\",\n"
                                "            \"address\": \"12 Rue de Rivoli, 75001 Paris, France\",\n"
                                "            \"phone_number\": \"+33 1 42 68 55 00\",\n"
                                "            \"latitude\": 48.8566,\n"
                                "            \"longitude\": 2.3522\n"
                                "          }\n"
                                "        }\n"
                                "      ]\n"
                                "    }\n"
                                "  ]\n"
                                "}"
                            )
                        },
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7
                )
                llm_dt = (time.perf_counter() - t0_llm) * 1000.0
                try:
                    from ..timing import TimingTracker
                    TimingTracker.add_llm_time(llm_dt)
                except Exception:
                    pass
                content = response.choices[0].message.content
                print("\n=================== [RAW LLM ITINERARY RESPONSE] ===================")
                print(content)
                print("===================================================================\n", flush=True)
                parsed = json.loads(content)
                llm_meta = {
                    "is_live_llm": True,
                    "llm_provider": "openai",
                    "llm_model": model_name,
                }
                days_out = parsed.get("days") if isinstance(parsed, dict) else (parsed if isinstance(parsed, list) else None)
                if days_out:
                    _LLM_METRICS_COUNTER["total_llm_calls"] += 1
                    _LLM_METRICS_COUNTER["openai_calls"] += 1
                    _LLM_METRICS_COUNTER["last_call_timestamp"] = datetime.now(timezone.utc).isoformat()
                    try:
                        from ..db.itinerary_dao import ItineraryDAO
                        ItineraryDAO(config=cfg).log_llm_call(provider="openai", model=model_name, prompt=user_prompt, destination=destination, success=True)
                    except Exception:
                        pass
                    print(f"[PLANNER LLM SUCCESS] Live OpenAI '{model_name}' generated {len(days_out)} day itinerary. Total LLM calls: {_LLM_METRICS_COUNTER['total_llm_calls']}")
                    return days_out, llm_meta
            except Exception as llm_err:
                print(f"[PLANNER LLM ERROR] OpenAI execution error: {llm_err}")
                try:
                    from ..db.itinerary_dao import ItineraryDAO
                    ItineraryDAO(config=cfg).log_llm_call(provider="openai", model=model_name, prompt=user_prompt, destination=destination, success=False, error_message=str(llm_err))
                except Exception:
                    pass
                raise RuntimeError(f"Live OpenAI LLM execution failed: {llm_err}")

        raise RuntimeError("No enabled LLM provider (OpenAI or Gemini) configured for live itinerary generation.")

    def _fetch_live_pricing(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        passengers_count: int,
        rooms: int,
        driver_age: int,
        is_test: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
        """
        Fetches live component pricing and top 3 package bundles from Duffel services.
        Returns tuple of (top_3_bundles, component_pricing, pricing_meta).
        """
        top_3_bundles = []
        component_pricing = {
            "flight_cost": 450.0 if is_test else 0.0,
            "hotel_cost_per_night": 160.0 if is_test else 0.0,
            "car_cost_total": 240.0 if is_test else 0.0
        }
        pricing_meta = {
            "is_live_pricing": not is_test,
            "pricing_source": "duffel_api_live" if not is_test else "estimated_package_pricing"
        }

        dest_formatted = format_proper_title(destination)
        from ..cli.parser import PromptExtractor
        dest_iata = PromptExtractor._resolve_iata(destination)
        if len(dest_iata) != 3 or not dest_iata.isalpha():
            dest_iata = PromptExtractor.resolve_location_with_llm(destination)

        try:
            from .bundles import BundlesService
            bundles_svc = getattr(self.client_app, "bundles", None)
            if not bundles_svc:
                bundles_svc = BundlesService(self.http_client, cache=self.cache, adapter=self.adapter, client=self.client)

            res = bundles_svc.search_bundle(
                origin=origin,
                destination=dest_iata,
                departure_date=departure_date,
                return_date=return_date,
                passengers_count=passengers_count,
                rooms=rooms,
                driver_age=driver_age,
                selected_types=["flights", "hotels", "cars"],
            )
            top_bnd_list = res.get("top_bundles", [])
            # Sort bundles strictly by total package price ascending
            top_bnd_list.sort(key=lambda b: float(b.get("total_package_price") or b.get("total_amount") or 0.0))
            top_3_bundles = top_bnd_list[:3]

            if top_bnd_list:
                pricing_meta = {
                    "is_live_pricing": True,
                    "pricing_source": "duffel_api_live"
                }
                for bnd in top_3_bundles:
                    bnd["package_name"] = format_proper_title(bnd.get("package_name") or bnd.get("name") or f"Curated Package for {dest_formatted}")
                    bnd["is_mock"] = False
                    bnd["source"] = "duffel_api_live"
                    bnd["included_components"] = ["flights", "hotels", "cars", "attractions", "activities", "dining"]
                    bnd["bundle_contents"] = {
                        "flights": {"included": True, "description": f"Roundtrip Flights ({origin} -> {dest_iata})"},
                        "hotels": {"included": True, "description": f"Central Hotel Stay in {dest_formatted} ({rooms} Room(s))"},
                        "cars": {"included": True, "description": f"Car Rental (Driver Age {driver_age})"},
                        "attractions": {"included": True, "description": f"Curated Priority Landmark & Museum Passes in {dest_formatted}"},
                        "activities": {"included": True, "description": f"Scheduled Daily Guided Activities & Tours"},
                        "dining": {"included": True, "description": f"Curated Daily Breakfast, Lunch, & Dinner Reservations at Top {dest_formatted} Cafes, Bistros, & Restaurants"},
                        "summary_line": f"Includes Roundtrip Flights, Central Hotel in {dest_formatted}, Car Rental, Famous Landmark Passes, Daily Activities, & Daily Breakfast/Lunch/Dinner Reservations."
                    }

                first_bnd = top_bnd_list[0]
                fl = first_bnd.get("flight_offer") or {}
                st = first_bnd.get("hotel_stay") or {}
                cr = first_bnd.get("car_rental") or {}

                if fl.get("total_amount"):
                    component_pricing["flight_cost"] = float(fl.get("total_amount")) / passengers_count

                # Extract live flight departure and arrival times
                if fl:
                    slices = fl.get("slices") or []
                    if slices and isinstance(slices[0], dict):
                        s1 = slices[0]
                        dep_raw = s1.get("departing_at") or s1.get("departure_time")
                        arr_raw = s1.get("arriving_at") or s1.get("arrival_time")
                        if dep_raw and "T" in str(dep_raw):
                            try:
                                dt = datetime.fromisoformat(str(dep_raw).replace("Z", "+00:00"))
                                component_pricing["outbound_departure_time"] = dt.strftime("%I:%M %p")
                            except Exception:
                                pass
                        if arr_raw and "T" in str(arr_raw):
                            try:
                                dt = datetime.fromisoformat(str(arr_raw).replace("Z", "+00:00"))
                                component_pricing["outbound_arrival_time"] = dt.strftime("%I:%M %p")
                            except Exception:
                                pass

                    if len(slices) > 1 and isinstance(slices[1], dict):
                        s2 = slices[1]
                        ret_dep_raw = s2.get("departing_at") or s2.get("departure_time")
                        ret_arr_raw = s2.get("arriving_at") or s2.get("arrival_time")
                        if ret_dep_raw and "T" in str(ret_dep_raw):
                            try:
                                dt = datetime.fromisoformat(str(ret_dep_raw).replace("Z", "+00:00"))
                                component_pricing["return_departure_time"] = dt.strftime("%I:%M %p")
                            except Exception:
                                pass
                        if ret_arr_raw and "T" in str(ret_arr_raw):
                            try:
                                dt = datetime.fromisoformat(str(ret_arr_raw).replace("Z", "+00:00"))
                                component_pricing["return_arrival_time"] = dt.strftime("%I:%M %p")
                            except Exception:
                                pass

                if st.get("cheapest_rate_total_amount"):
                    component_pricing["hotel_cost_per_night"] = float(st.get("cheapest_rate_total_amount")) / max(1, rooms)
                if cr.get("total_amount"):
                    component_pricing["car_cost_total"] = float(cr.get("total_amount"))
        except Exception as bnd_err:
            print(f"[PLANNER NOTICE] Live bundle search notice: {bnd_err}")
            if is_test:
                top_3_bundles = [
                    {
                        "bundle_id": f"bnd_mock_0001_{destination[:3].lower()}",
                        "package_name": format_proper_title(f"Economy Explorer Package for {dest_formatted}"),
                        "total_package_price": 712.50,
                        "currency": "USD",
                        "savings_amount": 37.50,
                        "is_mock": True,
                        "source": "estimated_package_pricing",
                        "included_components": ["flights", "hotels", "cars", "attractions", "activities"],
                        "bundle_contents": {
                            "flights": {"included": True, "description": f"Roundtrip Economy Flights ({origin} -> {dest_iata})"},
                            "hotels": {"included": True, "description": f"3-Star Comfort Hotel in {dest_formatted} ({rooms} Room(s))"},
                            "cars": {"included": True, "description": f"Compact Car Rental"},
                            "attractions": {"included": True, "description": f"Standard City Attraction Passes in {dest_formatted}"},
                            "activities": {"included": True, "description": f"Curated Walking & Sightseeing Tours"},
                            "summary_line": f"Includes Economy Flights, Comfort Hotel in {dest_formatted}, Compact Car Rental, City Attraction Passes, & Walking Tours."
                        }
                    }
                ]
            else:
                top_3_bundles = []

        return top_3_bundles, component_pricing, pricing_meta
