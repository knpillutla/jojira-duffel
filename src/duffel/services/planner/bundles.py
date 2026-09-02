from typing import Any, Optional
from .classifier import format_proper_title
from .titles import generate_contextual_bundle_title




def adapt_itinerary_for_tier(
    base_itinerary: list[dict[str, Any]],
    tier_id: str,
    mult: float,
    h_tier: str,
    c_tier: str,
    f_tier: str,
    cars_count: int,
) -> list[dict[str, Any]]:
    """Adapts item titles and pricing in daily itinerary for a specific package tier."""
    if not base_itinerary:
        return []
    adapted = []
    for day in base_itinerary:
        d_copy = {k: v for k, v in day.items() if k != "items"}
        d_items = []
        for it in day.get("items", []):
            it_copy = dict(it)
            it_type = (it_copy.get("type") or "").lower()
            it_cat = (it_copy.get("category") or "").lower()
            if it_type == "car":
                is_ret = it_copy.get("is_return") or "return" in (it_copy.get("name") or "").lower()
                it_copy["name"] = f"Rental Vehicle Return ({c_tier})" if is_ret else f"Rental Vehicle: {c_tier} ({cars_count} car)"
                it_copy["title"] = it_copy["name"]
                if not is_ret:
                    p_base = float(it_copy.get("price") or 180.0)
                    it_copy["price"] = round(p_base * (1.15 if tier_id == "luxury" else (0.85 if tier_id == "budget" else 1.0)), 2)
                    it_copy["price_display"] = f"USD {it_copy['price']:.2f}"
            elif it_type == "flight":
                it_copy["name"] = f"Flight: {f_tier}"
                it_copy["title"] = it_copy["name"]
                if not it_copy.get("is_return"):
                    p_base = float(it_copy.get("price") or 250.0)
                    it_copy["price"] = round(p_base * mult, 2)
                    it_copy["price_display"] = f"USD {it_copy['price']:.2f}"
            elif it_type == "hotel" or it_cat == "hotel":
                if "check-in" in (it_copy.get("name") or "").lower():
                    it_copy["description"] = f"Check-in at {h_tier}."
                p_base = float(it_copy.get("price") or 140.0)
                it_copy["price"] = round(p_base * mult, 2)
                it_copy["price_display"] = f"USD {it_copy['price']:.2f}"
            elif it_cat in ["attraction", "sightseeing", "shopping", "dining"]:
                p_base = float(it_copy.get("price") or (25.0 if it_cat != "dining" else 35.0))
                if p_base > 0:
                    it_copy["price"] = round(p_base * mult, 2)
                    it_copy["price_display"] = f"USD {it_copy['price']:.2f}"
            d_items.append(it_copy)
        d_copy["items"] = d_items
        adapted.append(d_copy)
    return adapted


def build_top_3_bundles(
    dest_clean: str,
    origin_code: str,
    prompt: str,
    opt_highlights: list[str],
    is_road_trip: bool,
    is_cruise: bool,
    duration_days: int,
    passengers_count: int,
    rooms_count: int,
    cars_count: int,
    flight_cost: float,
    hotel_cost_per_night: float,
    car_cost_total: float,
    is_hotel_tbd: bool,
    is_car_tbd: bool,
    activities_total_cost: float = 0.0,
    base_itinerary: Optional[list[dict[str, Any]]] = None,
    start_date: str = "",
    end_date: str = "",
    outbound_dep: str = "",
    return_arr: str = "",
    include_flights: bool = True,
    include_hotels: bool = True,
    include_cars: bool = True,
) -> list[dict[str, Any]]:
    """Builds top 3 bundles: Budget, Balanced, Luxury with dedicated summary and data."""
    hotel_total = 0.0 if is_hotel_tbd else (hotel_cost_per_night * max(1, duration_days - 1))
    flight_total = flight_cost * passengers_count if not is_road_trip else 0.0
    car_total = 0.0 if is_car_tbd else car_cost_total

    tiers = [
        (
            "budget",
            "Budget Saver",
            0.80,
            "Best value route with 3-star lodging, compact rental vehicle, and self-guided iconic landmarks.",
            "3-Star Boutique Hotels & Historic Inns",
            "Economy / Compact Sedan",
            "Economy Value Airfare",
            "Casual Local Diners & Self-Guided Sightseeing",
        ),
        (
            "balanced",
            "Balanced Choice",
            1.00,
            "Optimal comfort with top-rated 4-star hotels, midsize SUV, curated dining, and priority landmark access.",
            "4-Star Downtown Boutique Hotels (Hilton / Marriott / Autograph)",
            "Midsize Sedan / Standard SUV",
            "Main Cabin Direct Flights with Seat Selection",
            "Top-Rated Regional Bistros & Guided Cultural Tours",
        ),
        (
            "luxury",
            "Signature Luxury VIP",
            1.50,
            "Ultimate indulgence featuring 5-star luxury suites, premium SUV, fine dining, and private concierge tours.",
            "5-Star Luxury Resort Suites (The Adolphus / Ritz-Carlton / Four Seasons)",
            "Premium Luxury Full-Size SUV (Cadillac Escalade / BMW X5)",
            "First Class / Business Class Direct Flights",
            "Michelin-Starred / Chef's Tasting Menus & Private VIP Guided Access",
        ),
    ]

    bundles = []
    for idx, (tier_id, tier_label, mult, tier_desc, h_tier, c_tier, f_tier, d_tier) in enumerate(tiers):
        t_flight = round(flight_total * (mult if not is_road_trip else 1.0), 2)
        t_hotel = round(hotel_total * mult, 2)
        t_car = round(car_total * (1.15 if idx == 2 else (0.85 if idx == 0 else 1.0)), 2)
        t_act = round(activities_total_cost * mult, 2)
        t_total = round(t_flight + t_hotel + t_car + t_act, 2)

        p_name = generate_contextual_bundle_title(
            destination=dest_clean,
            tier=tier_id,
            index=idx,
            prompt=prompt,
            activities=opt_highlights,
            is_road_trip=is_road_trip,
            origin=origin_code
        )

        tier_itinerary = adapt_itinerary_for_tier(
            base_itinerary=base_itinerary or [],
            tier_id=tier_id,
            mult=mult,
            h_tier=h_tier,
            c_tier=c_tier,
            f_tier=f_tier,
            cars_count=cars_count,
        )

        tier_pricing = {
            "flight_cost": round(flight_cost * mult, 2),
            "hotel_cost_per_night": round(hotel_cost_per_night * mult, 2),
            "car_cost_total": t_car,
            "outbound_departure_time": outbound_dep,
            "return_arrival_time": return_arr,
        }

        from .summary import build_trip_summary
        tier_summary = build_trip_summary(
            dest_clean=dest_clean,
            origin_code=origin_code,
            start_date=start_date,
            end_date=end_date,
            duration_days=duration_days,
            passengers_count=passengers_count,
            rooms_count=rooms_count,
            cars_count=cars_count,
            include_flights=include_flights,
            include_hotels=include_hotels,
            include_cars=include_cars,
            is_road_trip=is_road_trip,
            is_cruise=is_cruise,
            outbound_dep=outbound_dep,
            return_arr=return_arr,
            component_pricing=tier_pricing,
            daily_itinerary=tier_itinerary,
            top_3_bundles=[],
        )

        bundles.append({
            "bundle_id": f"bundle_{tier_id}",
            "tier": tier_id,
            "tier_label": tier_label,
            "title": p_name,
            "package_name": p_name,
            "name": p_name,
            "description": tier_desc,
            "hotel_tier": h_tier,
            "car_tier": c_tier if (is_road_trip or not is_cruise) else "N/A",
            "flight_tier": f_tier if not is_road_trip else "Ground Road Trip",
            "dining_and_activities_style": d_tier,
            "total_price": t_total,
            "price_per_person": round(t_total / max(1, passengers_count), 2),
            "currency": "USD",
            "is_price_tbd": bool(is_hotel_tbd or is_car_tbd),
            "price_breakdown": {
                "flights": t_flight,
                "hotels": t_hotel,
                "cars": t_car,
                "activities": t_act,
            },
            "highlights": opt_highlights[:4],
            "summary": tier_summary,
            "daily_itinerary": tier_itinerary,
            "data": {
                "summary": tier_summary,
                "daily_itinerary": tier_itinerary,
                "highlights": opt_highlights[:4],
            }
        })

    return bundles
