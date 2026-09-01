"""
Deterministic Temporal Enforcement Engine for AI Travel Itineraries.
Normalizes daily itineraries to strict operational boundaries:
- 08:00 AM Rule: Breakfast locked to 08:00 AM - 09:00 AM
- 22:00 (10:00 PM) Cutoff: All daily activities terminated strictly by 22:00
- Buffer Allocation: 15-30 minute relaxation/exploration buffers between activities
- Transport Mode Routing: 45-60 min airport/customs/car rental blocks vs 08:00 AM road departure
"""

from datetime import datetime
import re
from typing import Any, Optional


class TemporalEnforcementEngine:
    """
    Deterministic post-processing engine that normalizes travel itineraries to strict real-world hourly boundaries.
    """

    @staticmethod
    def parse_time_to_minutes(time_val: Any, default_val: int = 480) -> int:
        """Parses a time string or timestamp into minutes from midnight (0..1439)."""
        if not time_val:
            return default_val

        ts = str(time_val).upper().strip()
        if "T" in ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                return dt.hour * 60 + dt.minute
            except Exception:
                pass

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

        match24 = re.search(r"\b(\d{1,2}):(\d{2})\b", ts)
        if match24:
            h = int(match24.group(1))
            m = int(match24.group(2))
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h * 60 + m

        if "BREAKFAST" in ts or "MORNING" in ts:
            return 480  # 08:00 AM
        if "LUNCH" in ts or "NOON" in ts:
            return 720  # 12:00 PM
        if "AFTERNOON" in ts:
            return 840  # 02:00 PM
        if "EVENING" in ts:
            return 1020 # 05:00 PM
        if "DINNER" in ts or "NIGHT" in ts:
            return 1140 # 07:00 PM

        return default_val

    @staticmethod
    def format_minutes_to_time(minutes: int) -> str:
        """Formats minutes from midnight into 12-hour AM/PM string (e.g. 480 -> '08:00 AM')."""
        mins_clamped = max(0, min(1439, minutes))
        h = mins_clamped // 60
        m = mins_clamped % 60
        ampm = "AM" if h < 12 else "PM"
        disp_h = h if h <= 12 else h - 12
        if disp_h == 0:
            disp_h = 12
        return f"{disp_h:02d}:{m:02d} {ampm}"

    @classmethod
    def enforce_daily_temporal_boundaries(
        cls,
        day_number: int,
        total_days: int,
        raw_activities: list[dict[str, Any]],
        is_flight_mode: bool = True,
        outbound_dep: str = "06:30 AM",
        outbound_arr: str = "12:30 PM",
        return_dep: str = "05:00 PM",
        return_arr: str = "11:00 PM",
        include_cars: bool = True,
        dest_clean: str = "Destination",
        orig_clean: str = "Origin",
    ) -> list[dict[str, Any]]:
        """
        Applies deterministic temporal rules:
        1. 08:00 AM Rule: Breakfast locked to 08:00 AM - 09:00 AM (unless flight arrives later in afternoon/evening on Day 1).
        2. Transport Mode Logistics: Injects 45-60 min vehicle rental / customs / baggage / hotel check-in.
        3. Buffer Allocation: Programmatically injects 15-30 min exploration/relaxation buffers between activities.
        4. 22:00 Cutoff: Caps all activities strictly by 10:00 PM (1320 mins) with clean hotel return.
        """
        is_arrival_day = (day_number == 1)
        is_departure_day = (day_number == total_days and total_days > 1)

        arr_mins = cls.parse_time_to_minutes(outbound_arr, default_val=750) # 12:30 PM
        dep_mins = cls.parse_time_to_minutes(return_dep, default_val=1020)  # 05:00 PM

        enforced_activities = []
        cur_mins = 480  # 08:00 AM default start

        # -------------------------------------------------------------------------
        # DAY 1 ARRIVAL LOGISTICS
        # -------------------------------------------------------------------------
        if is_arrival_day and is_flight_mode:
            # Outbound Flight Card
            enforced_activities.append({
                "id": "act_1_flight_arr",
                "name": f"Outbound Flight: {orig_clean} to {dest_clean}",
                "title": f"Outbound Flight: {orig_clean} to {dest_clean}",
                "time_slot": f"{outbound_dep} - {outbound_arr}",
                "departure_time": outbound_dep,
                "arrival_time": outbound_arr,
                "category": "Flight",
                "description": f"Scheduled live flight from {orig_clean} to {dest_clean}.",
                "price_per_person": 0.0,
                "rating": 4.8,
                "reviews_count": 1200,
                "next_activity": {
                    "name": "Baggage Claim & Airport Terminal",
                    "travel_time_minutes": 15,
                    "travel_time_display": "15 mins",
                    "travel_mode": "walk",
                    "transit_summary": "Deplaning, customs clearance, and baggage retrieval"
                }
            })

            cur_mins = arr_mins + 20  # Flight landing + baggage retrieval

            # Lunch if landing >= 12:00 PM
            if arr_mins >= 720:
                lunch_end = cur_mins + 45
                enforced_activities.append({
                    "id": "act_1_lunch",
                    "name": f"Airport Terminal Lunch & Refreshments",
                    "title": f"Airport Terminal Lunch & Refreshments",
                    "time_slot": f"{cls.format_minutes_to_time(cur_mins)} - {cls.format_minutes_to_time(lunch_end)}",
                    "departure_time": cls.format_minutes_to_time(cur_mins),
                    "arrival_time": cls.format_minutes_to_time(lunch_end),
                    "category": "Dining",
                    "description": f"Enjoy quick lunch and refreshments upon landing in {dest_clean}.",
                    "price_per_person": 22.0,
                    "rating": 4.6,
                    "reviews_count": 340,
                    "next_activity": {
                        "name": "Vehicle Rental Facility" if include_cars else "Hotel Transit",
                        "travel_time_minutes": 15,
                        "travel_time_display": "15 mins",
                        "travel_mode": "walk" if include_cars else "drive",
                        "transit_summary": "Proceeding to rental desk" if include_cars else "Direct hotel transit"
                    }
                })
                cur_mins = lunch_end + 15

            # Rental Car Pickup Window (Allocating strict 45-60 min operational block)
            if include_cars:
                car_end = cur_mins + 45
                enforced_activities.append({
                    "id": "act_1_car_pickup",
                    "name": f"Rental Vehicle Pickup & Inspection in {dest_clean}",
                    "title": f"Rental Vehicle Pickup & Inspection in {dest_clean}",
                    "time_slot": f"{cls.format_minutes_to_time(cur_mins)} - {cls.format_minutes_to_time(car_end)}",
                    "departure_time": cls.format_minutes_to_time(cur_mins),
                    "arrival_time": cls.format_minutes_to_time(car_end),
                    "category": "Car Rental",
                    "description": f"Pick up rental vehicle at {dest_clean} Airport facility. Quick vehicle inspection and route setup.",
                    "price_per_person": 0.0,
                    "rating": 4.7,
                    "reviews_count": 480,
                    "next_activity": {
                        "name": "Central Hotel Check-In",
                        "travel_time_minutes": 25,
                        "travel_time_display": "25 mins",
                        "travel_mode": "drive",
                        "transit_summary": f"Scenic drive into downtown {dest_clean}"
                    }
                })
                cur_mins = car_end + 25

            # Hotel Check-in
            hotel_end = cur_mins + 30
            enforced_activities.append({
                "id": "act_1_hotel_checkin",
                "name": f"Hotel Check-in & Room Settling in {dest_clean}",
                "title": f"Hotel Check-in & Room Settling in {dest_clean}",
                "time_slot": f"{cls.format_minutes_to_time(cur_mins)} - {cls.format_minutes_to_time(hotel_end)}",
                "departure_time": cls.format_minutes_to_time(cur_mins),
                "arrival_time": cls.format_minutes_to_time(hotel_end),
                "category": "Hotel",
                "description": f"Check-in, unpack, and freshen up before exploring {dest_clean}.",
                "price_per_person": 0.0,
                "rating": 4.8,
                "reviews_count": 890,
                "next_activity": {
                    "name": "Afternoon Sightseeing Discovery",
                    "travel_time_minutes": 15,
                    "travel_time_display": "15 mins",
                    "travel_mode": "walk",
                    "transit_summary": f"Relaxed stroll into {dest_clean} historic district"
                }
            })
            cur_mins = hotel_end + 15

        elif is_arrival_day and not is_flight_mode:
            # Road Trip Mode: Day 1 departs at 08:00 AM sharp
            enforced_activities.append({
                "id": "act_1_road_start",
                "name": f"Road Trip Departure from {orig_clean}",
                "title": f"Road Trip Departure from {orig_clean}",
                "time_slot": "08:00 AM - 09:00 AM",
                "departure_time": "08:00 AM",
                "arrival_time": "09:00 AM",
                "category": "Road Trip",
                "description": f"Embark on scenic road trip corridor from {orig_clean} toward {dest_clean}.",
                "price_per_person": 0.0,
                "rating": 4.9,
                "reviews_count": 210,
                "next_activity": {
                    "name": "En-Route Highway Waypoint & Lookout",
                    "travel_time_minutes": 30,
                    "travel_time_display": "30 mins",
                    "travel_mode": "drive",
                    "transit_summary": "Scenic highway cruise with panoramic mountain/countryside views"
                }
            })
            cur_mins = 570 # 09:30 AM

        else:
            # -------------------------------------------------------------------------
            # 08:00 AM RULE: Standard Breakfast locked to 08:00 AM - 09:00 AM
            # -------------------------------------------------------------------------
            enforced_activities.append({
                "id": f"act_{day_number}_breakfast",
                "name": f"Artisanal Breakfast & Morning Coffee in {dest_clean}",
                "title": f"Artisanal Breakfast & Morning Coffee in {dest_clean}",
                "time_slot": "08:00 AM - 09:00 AM",
                "departure_time": "08:00 AM",
                "arrival_time": "09:00 AM",
                "category": "Dining",
                "description": f"Freshly baked pastries, local artisan breakfast, and specialty coffee in {dest_clean}.",
                "price_per_person": 18.0,
                "rating": 4.8,
                "reviews_count": 640,
                "next_activity": {
                    "name": "Morning Cultural Discovery",
                    "travel_time_minutes": 20,
                    "travel_time_display": "20 mins",
                    "travel_mode": "walk",
                    "transit_summary": f"Morning walk to first attraction in {dest_clean}"
                }
            })
            cur_mins = 560 # 09:20 AM (allowing 20 min morning walk buffer)

        # -------------------------------------------------------------------------
        # SCHEDULE CORE SIGHTSEEING & DINING ACTIVITIES WITH 15-30 MIN BUFFERS
        # -------------------------------------------------------------------------
        # Filter out redundant airport/check-in items from raw activities
        filtered_raw = []
        for act in raw_activities:
            aname = (act.get("name") or act.get("title") or "").lower()
            if any(k in aname for k in ["flight", "check-in", "check in", "rental car pickup", "vehicle pickup", "rest for the night", "hotel rest"]):
                continue
            if "breakfast" in aname and len(enforced_activities) > 0 and "breakfast" in enforced_activities[0]["name"].lower():
                continue
            filtered_raw.append(act)

        # Limit departure day activities to wrap up before departure
        max_allowable_mins = dep_mins - 150 if (is_departure_day and is_flight_mode) else 1320 # 22:00 (10:00 PM)

        for act_idx, act in enumerate(filtered_raw, start=len(enforced_activities) + 1):
            if cur_mins >= max_allowable_mins - 45:
                break # Respect departure window or 22:00 cutoff

            duration_mins = 90 # default 1.5h activity
            act_name = act.get("name") or act.get("title") or f"Sightseeing Highlight {act_idx}"
            act_cat = act.get("category") or "Sightseeing"

            if any(k in act_name.lower() or k in act_cat.lower() for k in ["lunch", "dinner", "dining", "bistro", "cafe"]):
                duration_mins = 75
            elif any(k in act_name.lower() or k in act_cat.lower() for k in ["museum", "gallery", "palace", "park"]):
                duration_mins = 105

            # Ensure activity ends before cutoff
            end_mins = min(max_allowable_mins, cur_mins + duration_mins)
            if end_mins <= cur_mins + 30:
                break

            # Clone activity and update temporal fields
            enforced_act = dict(act)
            enforced_act["id"] = f"act_{day_number}_{act_idx}"
            enforced_act["time_slot"] = f"{cls.format_minutes_to_time(cur_mins)} - {cls.format_minutes_to_time(end_mins)}"
            enforced_act["departure_time"] = cls.format_minutes_to_time(cur_mins)
            enforced_act["arrival_time"] = cls.format_minutes_to_time(end_mins)

            # Programmatically inject 15-30 min exploration buffer
            buffer_mins = 20
            enforced_act["next_activity"] = {
                "name": f"Transit & Relaxation Buffer",
                "travel_time_minutes": buffer_mins,
                "travel_time_display": f"{buffer_mins} mins",
                "travel_mode": "walk" if not is_arrival_day else "drive",
                "transit_summary": f"Relaxed {buffer_mins}-min transition buffer and neighborhood discovery"
            }

            enforced_activities.append(enforced_act)
            cur_mins = end_mins + buffer_mins

        # -------------------------------------------------------------------------
        # FINAL DAY DEPARTURE LOGISTICS
        # -------------------------------------------------------------------------
        if is_departure_day and is_flight_mode:
            # Vehicle Drop-off (45-60 min window)
            if include_cars:
                drop_start = max(cur_mins, dep_mins - 150)
                drop_end = drop_start + 45
                enforced_activities.append({
                    "id": f"act_{day_number}_car_return",
                    "name": f"Rental Vehicle Return & Final Drop-off",
                    "title": f"Rental Vehicle Return & Final Drop-off",
                    "time_slot": f"{cls.format_minutes_to_time(drop_start)} - {cls.format_minutes_to_time(drop_end)}",
                    "departure_time": cls.format_minutes_to_time(drop_start),
                    "arrival_time": cls.format_minutes_to_time(drop_end),
                    "category": "Car Rental",
                    "description": f"Return rental vehicle to {dest_clean} Airport car rental facility with inspection receipt.",
                    "price_per_person": 0.0,
                    "rating": 4.8,
                    "reviews_count": 390,
                    "next_activity": {
                        "name": "Airport Terminal & Security Check-In",
                        "travel_time_minutes": 15,
                        "travel_time_display": "15 mins",
                        "travel_mode": "walk",
                        "transit_summary": "Proceed to airline terminal and security screening"
                    }
                })

            # Return Flight Card
            enforced_activities.append({
                "id": f"act_{day_number}_return_flight",
                "name": f"Return Flight: {dest_clean} to {orig_clean}",
                "title": f"Return Flight: {dest_clean} to {orig_clean}",
                "time_slot": f"{return_dep} - {return_arr}",
                "departure_time": return_dep,
                "arrival_time": return_arr,
                "category": "Flight",
                "description": f"Scheduled return flight from {dest_clean} to {orig_clean}.",
                "price_per_person": 0.0,
                "rating": 4.8,
                "reviews_count": 1400,
                "next_activity": {
                    "name": f"Trip Completion in {orig_clean}",
                    "travel_time_minutes": 0,
                    "travel_time_display": "0 mins",
                    "travel_mode": "arrive",
                    "transit_summary": f"Arrival back home in {orig_clean}"
                }
            })

        elif not is_departure_day or not is_flight_mode:
            # -------------------------------------------------------------------------
            # 22:00 CUTOFF: Terminate day strictly by 10:00 PM (22:00) with nightly rest
            # -------------------------------------------------------------------------
            rest_start = min(1320, max(cur_mins, 1260)) # between 09:00 PM and 10:00 PM
            enforced_activities.append({
                "id": f"act_{day_number}_night_rest",
                "name": f"Return to Hotel & Rest for the Night in {dest_clean}",
                "title": f"Return to Hotel & Rest for the Night in {dest_clean}",
                "time_slot": f"{cls.format_minutes_to_time(rest_start)} - 10:00 PM",
                "departure_time": cls.format_minutes_to_time(rest_start),
                "arrival_time": "10:00 PM",
                "category": "Hotel",
                "description": f"Return to hotel, relax, and rest for the night in {dest_clean}.",
                "price_per_person": 0.0,
                "rating": 4.9,
                "reviews_count": 920,
                "next_activity": {
                    "name": "Overnight Rest",
                    "travel_time_minutes": 0,
                    "travel_time_display": "0 mins",
                    "travel_mode": "rest",
                    "transit_summary": "Night rest"
                }
            })

        return enforced_activities
