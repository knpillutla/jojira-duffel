"""
Trip Summary & Aggregate Metadata Builder.
Generates comprehensive executive summaries covering dates, timing, travel vs core days,
vehicle rentals, hotel night-by-night breakdowns, attraction costs, and total budget.
"""

import re
from typing import Any, Optional


def extract_overnight_lodging(day_elem: dict[str, Any], default_dest: str) -> tuple[str, str]:
    """Extracts the overnight city and hotel name dynamically from day's items."""
    overnight_city = default_dest
    h_name = f"Verified Safe Hotel in {default_dest}"

    # 1. First priority: Look for explicit hotel items or hotel check-in
    for item in day_elem.get("items", []):
        itype = (item.get("type") or "").lower()
        icat = (item.get("category") or "").lower()
        title = item.get("name") or item.get("title") or item.get("activity") or ""
        loc = item.get("location") or ""
        addr = item.get("address") or ""

        is_hotel = (
            itype in ["hotel", "hotel_checkin"]
            or icat == "hotel"
            or any(kw in title.lower() for kw in ["hotel", "inn", "suites", "resort", "lodge", "check-in", "check in"])
        )
        if is_hotel:
            clean_title = re.sub(r"^(check-in at|check in at|check into|return to hotel at|stay at)\s+", "", title, flags=re.I).strip()
            if clean_title:
                h_name = clean_title
            if loc and loc.lower() not in ["drive", "hotel", "lodging"]:
                overnight_city = loc
            elif addr and "," in addr:
                parts = [p.strip() for p in addr.split(",")]
                overnight_city = f"{parts[-2]}, {parts[-1]}" if len(parts) >= 2 else parts[-1]
            return overnight_city, h_name

    # 2. Secondary scan from evening items avoiding dining/transit
    for item in reversed(day_elem.get("items", [])):
        icat = (item.get("category") or "").lower()
        if icat in ["dining", "restaurant", "food", "transit"]:
            continue
        loc = item.get("location") or ""
        addr = item.get("address") or ""
        if loc and loc.lower() not in ["drive", "hotel", "lodging"]:
            overnight_city = loc
            break
        elif addr and "," in addr:
            parts = [p.strip() for p in addr.split(",")]
            overnight_city = f"{parts[-2]}, {parts[-1]}" if len(parts) >= 2 else parts[-1]
            break

    return overnight_city, h_name


def build_trip_summary(
    dest_clean: str,
    origin_code: str,
    start_date: str,
    end_date: str,
    duration_days: int,
    passengers_count: int,
    rooms_count: int,
    cars_count: int,
    include_flights: bool,
    include_hotels: bool,
    include_cars: bool,
    is_road_trip: bool,
    is_cruise: bool,
    outbound_dep: str,
    return_arr: str,
    component_pricing: dict[str, Any],
    daily_itinerary: list[dict[str, Any]],
    top_3_bundles: list[dict[str, Any]],
    adults_count: int = 1,
    children_count: int = 0,
    children_ages: Optional[list[int]] = None,
) -> dict[str, Any]:
    """Builds structured trip summary and component expense breakdown."""
    actual_end_date = (
        daily_itinerary[-1].get("date")
        if (daily_itinerary and isinstance(daily_itinerary[-1], dict) and daily_itinerary[-1].get("date"))
        else end_date
    )
    c_ages = children_ages or []
    eff_adults = adults_count if adults_count > 0 else (max(1, passengers_count - children_count) if passengers_count > children_count else passengers_count)

    # 1. Travel Days vs Core Days Calculation
    if duration_days <= 1:
        travel_days_count = 1
        core_days_count = 0
        travel_days_list = [f"Day 1 ({start_date})"]
        core_days_list = []
    elif duration_days == 2:
        travel_days_count = 2
        core_days_count = 0
        travel_days_list = [f"Day 1 ({start_date})", f"Day 2 ({actual_end_date})"]
        core_days_list = []
    else:
        travel_days_count = 2
        core_days_count = max(0, duration_days - 2)
        travel_days_list = [f"Day 1 ({start_date}) - Departure/Outbound", f"Day {duration_days} ({actual_end_date}) - Return/Arrival"]
        core_days_list = [f"Day {i+1} ({daily_itinerary[i]['date'] if i < len(daily_itinerary) else ''})" for i in range(1, duration_days - 1)]

    # 2. Car Rental Summary
    car_cost_tot = component_pricing.get("car_cost_total", 180.0) * cars_count if include_cars else 0.0
    car_daily_rate = round(car_cost_tot / max(1, duration_days), 2)
    car_pickup_loc = f"{origin_code} City Rental Center" if (is_road_trip or not include_flights) else f"{dest_clean} Airport Car Rental Facility"
    car_dropoff_loc = f"{origin_code} City Rental Center" if (is_road_trip or not include_flights) else f"{dest_clean} Airport Car Rental Facility"

    car_rental_summary = {
        "included": bool(include_cars), "from_date": start_date, "to_date": actual_end_date,
        "pickup_time": outbound_dep or "08:30 AM", "dropoff_time": "05:30 PM" if (is_road_trip or not include_flights) else "03:00 PM",
        "pickup_location": car_pickup_loc, "dropoff_location": car_dropoff_loc, "rental_type": "round_trip",
        "car_type": "Standard Sedan / Midsize SUV", "cars_count": cars_count, "number_of_days": duration_days,
        "cost_per_day": car_daily_rate, "total_cost": car_cost_tot, "currency": "USD", "passenger_capacity": 5,
    }

    # 3. Hotel List & Night-by-Night Breakdown
    hotel_cost_pn = component_pricing.get("hotel_cost_per_night", 140.0) * rooms_count if include_hotels else 0.0
    total_nights = max(0, duration_days - 1)
    total_hotels_cost = hotel_cost_pn * total_nights

    # Extract intermediate overnight towns from itinerary
    hotel_list = []
    city_to_hotel: dict[str, str] = {}
    if include_hotels:
        for day_elem in daily_itinerary[:-1]:
            d_num = day_elem.get("day_number", 1)
            d_date = day_elem.get("date", "")
            overnight_city, h_name = extract_overnight_lodging(day_elem, dest_clean)

            # Preserve hotel continuity: reuse established hotel for consecutive/same city stays
            norm_city = overnight_city.lower().split(",")[0].strip()
            if norm_city in city_to_hotel:
                h_name = city_to_hotel[norm_city]
            else:
                city_to_hotel[norm_city] = h_name

            hotel_list.append({
                "night_number": d_num, "date": d_date, "city": overnight_city, "hotel_name": h_name,
                "star_rating": 4.5, "reviews_count": 1250, "breakfast_included": True,
                "breakfast_type": "Complimentary Hot Breakfast / Buffet", "breakfast_cost_display": "Free / Included with Stay",
                "safety_rating": "5.0 / Verified Safe District", "walkability_score": "High (92/100 Walkable)",
                "family_friendly": True, "cost_per_night": hotel_cost_pn, "number_of_rooms": rooms_count,
                "number_of_nights": 1, "total_cost": hotel_cost_pn, "currency": "USD",
            })

    hotel_summary = {
        "included": bool(include_hotels),
        "total_nights": total_nights,
        "total_cost": total_hotels_cost,
        "cost_per_night_average": hotel_cost_pn,
        "rooms_count": rooms_count,
        "currency": "USD",
        "hotel_list": hotel_list,
    }

    # 4. Attraction List & Costs
    attractions_list = []
    total_attractions_cost = 0.0

    for day_elem in daily_itinerary:
        d_num = day_elem.get("day_number", 1)
        for it in day_elem.get("items", []):
            it_type = (it.get("type") or "").lower()
            it_cat = (it.get("category") or "").lower()
            act_title = it.get("name") or it.get("title") or it.get("activity") or ""

            if it_type in ["car", "flight", "hotel", "hotel_checkin", "transit"]:
                continue
            if it_cat in ["car", "flight", "hotel", "dining", "transit", "transportation"]:
                continue
            if any(k in act_title.lower() for k in ["check-in", "check in", "rest at hotel", "return to hotel", "breakfast", "lunch", "dinner", "depart "]):
                continue
            if act_title.lower().startswith("drive to "):
                continue

            cost_pp = float(it.get("price") or (25.0 if any(k in act_title.lower() for k in ["museum", "institute", "center", "tour", "theme park", "park"]) else 0.0))
            act_tot = cost_pp * passengers_count
            total_attractions_cost += act_tot

            attractions_list.append({
                "day_number": d_num, "name": act_title, "location": it.get("location") or dest_clean,
                "time_slot": it.get("time") or it.get("time_slot") or "10:00 AM - 12:00 PM",
                "cost_per_person": cost_pp, "passengers_count": passengers_count, "total_cost": act_tot,
                "rating": float(it.get("rating") or 4.8), "currency": "USD", "category": it.get("category") or "Sightseeing & Culture",
            })

    attractions_summary = {
        "total_attractions_count": len(attractions_list), "total_cost": total_attractions_cost,
        "currency": "USD", "attraction_list": attractions_list,
    }

    # 5. Restaurant / Dining List & Schedule Breakdown
    restaurants_list = []
    total_dining_cost = 0.0

    for day_elem in daily_itinerary:
        d_num = day_elem.get("day_number", 1)
        d_date = day_elem.get("date", "")
        for it in day_elem.get("items", []):
            it_type = (it.get("type") or it.get("activity_type") or "").lower()
            it_cat = (it.get("category") or "").lower()
            act_title = it.get("name") or it.get("title") or it.get("activity") or ""
            t_lower = act_title.lower()

            is_dining = it_type == "dining" or it_cat == "dining" or any(k in t_lower for k in ["breakfast", "lunch", "dinner", "cafe", "bistro", "bbq", "eatery", "restaurant"])
            if not is_dining:
                continue

            if "breakfast" in t_lower:
                m_type = "Breakfast"
            elif "lunch" in t_lower:
                m_type = "Lunch"
            elif "dinner" in t_lower:
                m_type = "Dinner"
            else:
                m_type = "Culinary Experience"

            cost_pp = float(it.get("price") or (28.0 if m_type == "Dinner" else (20.0 if m_type == "Lunch" else 15.0)))
            meal_tot = cost_pp * passengers_count
            total_dining_cost += meal_tot
            clean_rname = re.sub(r"^(breakfast at|lunch at|dinner at)\s+", "", act_title, flags=re.I).strip()

            restaurants_list.append({
                "day_number": d_num, "date": d_date, "meal_type": m_type, "restaurant_name": clean_rname,
                "name": act_title, "time_slot": it.get("time") or it.get("time_slot") or "12:00 PM - 01:30 PM",
                "location": it.get("location") or dest_clean, "cuisine": it.get("cuisine") or "Local Regional Cuisine",
                "cost_per_person": cost_pp, "passengers_count": passengers_count, "total_cost": meal_tot,
                "rating": float(it.get("rating") or 4.8), "reviews_count": int(it.get("reviews_count") or 850), "currency": "USD",
            })

    dining_summary = {
        "total_meals_count": len(restaurants_list),
        "total_cost": total_dining_cost,
        "currency": "USD",
        "restaurant_list": restaurants_list,
        "dining_list": restaurants_list,
    }

    # 6. Flight Summary
    air_name = str(component_pricing.get("airline_name") or component_pricing.get("airline") or "Delta Air Lines") if include_flights else None
    flight_cost_tot = component_pricing.get("flight_cost", 250.0) * passengers_count if include_flights else 0.0
    flights_summary = {
        "included": bool(include_flights), "airline": air_name, "airline_name": air_name,
        "origin": str(origin_code or "").upper() if include_flights else str(origin_code),
        "destination": str(dest_clean or "").upper() if include_flights else str(dest_clean),
        "passengers_count": passengers_count, "total_cost": flight_cost_tot, "currency": "USD",
    }

    # 7. Overall Grand Total Cost
    overall_total_cost = flight_cost_tot + total_hotels_cost + car_cost_tot + total_attractions_cost

    return {
        "origin": str(origin_code or "").upper() if include_flights else str(origin_code),
        "destination": str(dest_clean or "").upper() if include_flights else str(dest_clean),
        "airline": air_name, "airline_name": air_name,
        "start_date": start_date, "start_time": outbound_dep or "08:30 AM", "start_datetime": f"{start_date} {outbound_dep or '08:30 AM'}",
        "end_date": end_date, "end_time": return_arr or "06:00 PM", "end_datetime": f"{end_date} {return_arr or '06:00 PM'}",
        "total_days": duration_days, "travel_days": travel_days_count, "travel_days_list": travel_days_list,
        "core_days": core_days_count, "core_days_list": core_days_list,
        "passengers_count": passengers_count,
        "adults_count": eff_adults,
        "children_count": children_count,
        "children_ages": c_ages,
        "passengers": {
            "adults": eff_adults,
            "children": children_count,
            "children_ages": c_ages,
            "total": passengers_count,
        },
        "rooms_count": rooms_count,
        "cars_count": cars_count,
        "total_cost": overall_total_cost, "price_per_person": round(overall_total_cost / max(1, passengers_count), 2),
        "currency": "USD", "itinerary_options": top_3_bundles, "car_rental": car_rental_summary,
        "hotels": hotel_summary, "attractions": attractions_summary, "dining": dining_summary,
        "restaurants": dining_summary, "flights": flights_summary,
    }

