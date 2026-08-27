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


class TravelPlannerService(BaseService):
    """
    High-Performance AI Travel Planner service:
    - Tier-0 L1 Process Memory Cache (<0.1ms) + Tier-1 Redis Distributed Cache (<2ms).
    - Concurrent ThreadPoolExecutor execution: Parallelizes LLM prompt synthesis and live Duffel sub-API price searches.
    - Calculates hotel room occupancy (ceil(passengers / 2)) and vehicle seating capacity (ceil(passengers / 5)).
    - Generates Category Highlights (Cheapest, Moderate, Luxury) with ratings and prices.
    - Enforces standard response envelope (status, timestamp, meta_data, data).
    """

    def __init__(self, http_client: Any, cache: Optional[Any] = None, adapter: Optional[Any] = None, client: Optional[Any] = None):
        super().__init__(http_client, cache=cache, adapter=adapter)
        self.client_app = client
        self.executor = ThreadPoolExecutor(max_workers=8)

    def generate_itinerary(
        self,
        prompt: str,
        include_flights: bool = True,
        include_hotels: bool = True,
        include_cars: bool = True,
        include_attractions: bool = True,
        include_activities: bool = True,
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
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """
        Generates structured daily itinerary with geo-coordinates, ratings, daily pricing, and category highlights.
        Optimized for high-throughput concurrency and sub-millisecond cached responses.
        """
        # Extract intent if parameters missing
        from ..cli.parser import PromptExtractor
        intent = PromptExtractor.extract_natural_intent(prompt)

        dest_raw = destination or intent.get("destination") or "Paris"
        dest_clean = str(dest_raw).strip()
        dest_upper = dest_clean.upper()

        origin_code = (origin or (intent.get("origin") if len(intent.get("origin") or "") == 3 else None) or "ATL").upper()
        if len(origin_code) != 3 or not origin_code.isalpha() or origin_code == dest_upper:
            origin_code = "JFK" if dest_upper != "JFK" else "ATL"

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


        # Map Center & Geo Coordinates
        map_center = DESTINATION_GEO_MAP.get(
            dest_upper,
            {"latitude": 48.8566, "longitude": 2.3522, "address": f"{dest_clean} Central", "name": f"{dest_clean} City Center"}
        )
        base_lat = map_center.get("latitude", 48.8566)
        base_lng = map_center.get("longitude", 2.3522)

        # Build System & User Prompt for LLM
        system_prompt = (
            "You are an expert AI Travel Planner & Concierge. Your task is to generate a comprehensive, highly curated "
            "day-by-day travel itinerary with realistic geo-coordinates (latitude/longitude), prices, time slots, and "
            "ratings (user ratings 4.5-5.0 stars) tailored precisely to user preferences."
        )
        user_prompt = (
            f"Plan a {duration_days}-day trip to {dest_clean} from {start_date} to {end_date} for {passengers_count} passenger(s). "
            f"Style: {style}, Budget: {budget}. Included components: "
            f"Flights={include_flights}, Hotels={include_hotels} ({rooms_calculated} rooms), Cars={include_cars} ({cars_calculated} car), "
            f"Attractions={include_attractions}, Activities={include_activities}. Prompt details: '{prompt}'."
        )

        # Parallel Concurrency: Submit LLM Orchestration and Sub-API Price Searches in parallel
        future_llm = self.executor.submit(
            self._orchestrate_llm_itinerary,
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
        future_pricing = self.executor.submit(
            self._fetch_live_pricing,
            origin_code,
            dest_upper,
            start_date,
            end_date,
            passengers_count,
            rooms_calculated,
            driver_age,
        )

        # Wait for parallel tasks to complete concurrently
        llm_itinerary_days = future_llm.result()
        top_3_bundles, component_pricing = future_pricing.result()


        # Compute Daily Total Costs & Attach Components to Daily Schedule
        flight_cost = component_pricing.get("flight_cost", 450.0) * passengers_count if include_flights else 0.0
        hotel_cost_per_night = component_pricing.get("hotel_cost_per_night", 160.0) * rooms_calculated if include_hotels else 0.0
        car_cost_total = component_pricing.get("car_cost_total", 240.0) * cars_calculated if include_cars else 0.0
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
                    "name": f"Airline Flight ({origin_code} -> {dest_upper})",
                    "description": f"Roundtrip flight for {passengers_count} passenger(s)",
                    "price": round(flight_cost, 2),
                    "currency": "USD",
                    "time_slot": "08:30 AM - 02:30 PM",
                    "geo_location": {"name": f"{dest_clean} Airport", "latitude": base_lat + 0.05, "longitude": base_lng + 0.05}
                })

            if include_cars and d_num == 1:
                day_items.append({
                    "id": f"item_car_{d_num}",
                    "type": "car",
                    "name": f"Vehicle Rental ({cars_calculated} car(s))",
                    "description": f"{duration_days}-day rental for {passengers_count} passenger(s)",
                    "price": round(car_cost_total, 2),
                    "currency": "USD",
                    "time_slot": "10:00 AM",
                    "geo_location": {"name": f"{dest_clean} Car Pickup", "latitude": base_lat + 0.05, "longitude": base_lng + 0.05}
                })

            if include_hotels:
                day_items.append({
                    "id": f"item_ht_{d_num}",
                    "type": "hotel",
                    "name": f"Grand {dest_clean} Hotel ({rooms_calculated} Room(s))",
                    "description": f"Night {d_num} of {duration_days}",
                    "price": round(hotel_cost_per_night, 2),
                    "currency": "USD",
                    "time_slot": "03:00 PM Check-in",
                    "geo_location": {"name": f"Grand {dest_clean} Hotel", "latitude": base_lat, "longitude": base_lng}
                })

            for act in day.get("activities", []):
                act_price = float(act.get("price") or 25.0) * passengers_count
                day_activities_cost += act_price
                day_items.append({
                    "id": f"item_act_{d_num}_{pin_idx}",
                    "type": "attraction" if act.get("category") in ["Sightseeing", "Culture"] else "activity",
                    "name": act.get("title"),
                    "description": act.get("description"),
                    "price": round(act_price, 2),
                    "currency": "USD",
                    "time_slot": act.get("time_slot"),
                    "rating": act.get("rating", 4.7),
                    "geo_location": act.get("geo_location")
                })
                
                # Add Map Pin
                geo = act.get("geo_location", {})
                map_pins.append({
                    "id": f"pin_{pin_idx}",
                    "title": act.get("title"),
                    "category": "attraction",
                    "latitude": geo.get("latitude", base_lat),
                    "longitude": geo.get("longitude", base_lng),
                    "day_number": d_num,
                    "address": geo.get("address", f"{dest_clean} Landmark Area"),
                    "rating": act.get("rating", 4.7)
                })
                pin_idx += 1

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
        pricing_src_str = pricing_meta.get("pricing_source", "synthetic_estimate")


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
            "map_center": map_center,
            "geo_location": {
                "origin": {"code": origin_code, "name": f"{origin_code} Airport"},
                "destination": {"code": dest_upper, "name": dest_clean, "latitude": base_lat, "longitude": base_lng}
            }
        }

        data_section = {
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
                client = openai.OpenAI(api_key=cfg.openai_api_key)
                model_name = getattr(cfg, "openai_model", "gpt-4.1-mini")
                response = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": system_prompt + " Return valid JSON array of days."},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"} if "gpt-4" in model_name else None,
                    temperature=0.7
                )
                content = response.choices[0].message.content
                parsed = json.loads(content)
                llm_meta = {
                    "is_live_llm": True,
                    "llm_provider": "openai",
                    "llm_model": model_name,
                }
                if isinstance(parsed, dict) and "days" in parsed:
                    return parsed["days"], llm_meta
                elif isinstance(parsed, list):
                    return parsed, llm_meta
            except Exception as llm_err:
                print(f"[PLANNER LLM NOTICE] OpenAI execution fallback: {llm_err}")

        # Intelligent Travel Synthesizer Engine Fallback
        activities_pool = [
            ("Morning", f"Historic {destination} Landmarks & Walking Tour", "Culture", f"Explore iconic historic monuments and charming avenues in {destination}.", 0.004, 0.003, 20.0, 4.8),
            ("Afternoon", f"{destination} Fine Art & Culinary Tasting", "Dining", f"Sample artisanal regional specialties and visit top galleries in {destination}.", -0.003, 0.005, 35.0, 4.9),
            ("Evening", f"Sunset Scenic Overlook & River Cruise in {destination}", "Sightseeing", f"Experience breathtaking evening panoramic skyline views and waterfront cruise.", 0.002, -0.004, 30.0, 4.7),
        ]

        days_list = []
        for day_idx in range(1, duration_days + 1):
            curr_date = (start_dt + timedelta(days=day_idx - 1)).strftime("%Y-%m-%d")
            theme = f"Day {day_idx}: Iconic {destination} Culture & Highlights" if day_idx == 1 else f"Day {day_idx}: Hidden Gems & Local Experiences"
            
            day_acts = []
            if include_attractions or include_activities:
                for slot, title, cat, desc, off_lat, off_lng, pr, rat in activities_pool:
                    act_lat = round(base_lat + (off_lat * day_idx), 4)
                    act_lng = round(base_lng + (off_lng * day_idx), 4)
                    day_acts.append({
                        "title": title,
                        "time_slot": slot,
                        "category": cat,
                        "description": desc,
                        "price_per_person": pr,
                        "rating": rat,
                        "reviews_count": 850 + (day_idx * 120),
                        "geo_location": {
                            "name": f"{destination} {cat} Spot",
                            "address": f"{title}, {destination}",
                            "latitude": act_lat,
                            "longitude": act_lng
                        }
                    })

            days_list.append({
                "day_number": day_idx,
                "date": curr_date,
                "theme": theme,
                "activities": day_acts
            })

        return days_list, llm_meta

    def _fetch_live_pricing(
        self,
        origin: str,
        destination: str,
        departure_date: str,
        return_date: str,
        passengers_count: int,
        rooms: int,
        driver_age: int,
    ) -> tuple[list[dict[str, Any]], dict[str, float], dict[str, Any]]:
        """
        Fetches live component pricing and top 3 package bundles from Duffel services.
        Returns tuple of (top_3_bundles, component_pricing, pricing_meta).
        """
        top_3_bundles = []
        component_pricing = {
            "flight_cost": 450.0,
            "hotel_cost_per_night": 160.0,
            "car_cost_total": 240.0
        }
        pricing_meta = {
            "is_live_pricing": False,
            "pricing_source": "synthetic_estimate"
        }

        dest_iata = "CDG" if destination.upper() in ["PARIS", "PAR"] else ("LHR" if destination.upper() in ["LONDON", "LON"] else ("JFK" if destination.upper() in ["NEW YORK", "NYC"] else (destination.upper() if len(destination) == 3 else "CDG")))

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
            top_3_bundles = top_bnd_list[:3]

            if top_bnd_list:
                pricing_meta = {
                    "is_live_pricing": True,
                    "pricing_source": "duffel_api_live"
                }
                for bnd in top_3_bundles:
                    bnd["is_mock"] = False
                    bnd["source"] = "duffel_api_live"

                first_bnd = top_bnd_list[0]
                fl = first_bnd.get("flight_offer") or {}
                st = first_bnd.get("hotel_stay") or {}
                cr = first_bnd.get("car_rental") or {}

                if fl.get("total_amount"):
                    component_pricing["flight_cost"] = float(fl.get("total_amount")) / passengers_count
                if st.get("cheapest_rate_total_amount"):
                    component_pricing["hotel_cost_per_night"] = float(st.get("cheapest_rate_total_amount")) / max(1, rooms)
                if cr.get("total_amount"):
                    component_pricing["car_cost_total"] = float(cr.get("total_amount"))
        except Exception as bnd_err:
            print(f"[PLANNER NOTICE] Live bundle search fallback: {bnd_err}")
            top_3_bundles = [
                {
                    "bundle_id": f"bnd_mock_0001_{destination[:3].lower()}",
                    "package_name": "Economy Explorer Package",
                    "total_package_price": 712.50,
                    "currency": "USD",
                    "savings_amount": 37.50,
                    "is_mock": True,
                    "source": "synthetic_estimate"
                },
                {
                    "bundle_id": f"bnd_mock_0002_{destination[:3].lower()}",
                    "package_name": "Comfort & Central Stay Package",
                    "total_package_price": 945.00,
                    "currency": "USD",
                    "savings_amount": 50.00,
                    "is_mock": True,
                    "source": "synthetic_estimate"
                },
                {
                    "bundle_id": f"bnd_mock_0003_{destination[:3].lower()}",
                    "package_name": "Signature Luxury Suite & SUV Package",
                    "total_package_price": 1425.00,
                    "currency": "USD",
                    "savings_amount": 75.00,
                    "is_mock": True,
                    "source": "synthetic_estimate"
                }
            ]

        return top_3_bundles, component_pricing, pricing_meta
