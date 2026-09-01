from typing import Any, Optional
from .classifier import format_proper_title


def generate_contextual_bundle_title(
    destination: str,
    tier: str = "moderate",
    index: int = 1,
    prompt: str = "",
    activities: Optional[list[str]] = None,
    is_road_trip: bool = False,
    origin: str = "",
) -> str:
    """
    Dynamically generates contextual, non-hardcoded package & bundle titles based on:
    - Road Trips: 'shortest' (Fast Direct Route), 'scenic' (Scenic Byways & Panoramas), 'longest' (Extended Explorer)
    - Flight Vacations: 'cheapest' (Budget Saver), 'moderate' (Balanced Choice), 'luxury' (Signature Luxury)
    - Real Generated Itinerary Activities & Intent Keywords.
    """
    dest = format_proper_title(destination)
    orig = format_proper_title(origin) if origin else ""
    p_lower = (prompt or "").lower()
    acts = activities or []

    act1 = ""
    act2 = ""
    for a in acts:
        a_clean = str(a).strip()
        if not a_clean or any(w in a_clean.lower() for w in ["check-in", "hotel", "airport", "flight", "rest"]):
            continue
        if not act1:
            act1 = a_clean
        elif not act2 and a_clean != act1:
            act2 = a_clean
            break

    tier_clean = tier.lower()

    # 1. Road Trip Bundle Titles (Shortest, Scenic, Longest)
    if is_road_trip or tier_clean in ["shortest", "scenic", "longest"]:
        route_header = f"{orig} to {dest}" if orig and orig.lower() != dest.lower() else dest
        if "short" in tier_clean or index == 0:
            act_snippet = f" & {act1}" if act1 else " & Express Waypoints"
            return format_proper_title(f"Shortest Route: Direct {route_header} Highway{act_snippet}")
        elif "scen" in tier_clean or index == 1:
            act_snippet = f" & {act1}" if act1 else " & Panoramic Lookouts"
            return format_proper_title(f"Scenic Route: {route_header} Byways & Nature Trails{act_snippet}")
        else:
            act_snippet = f" & {act1}" if act1 else " & Historic Towns"
            return format_proper_title(f"Longest Route: Extended {route_header} Regional Explorer{act_snippet}")

    # 2. Flight & Vacation Travel Thematic Titles (Cheapest, Moderate, Luxury)
    is_romantic = any(w in p_lower for w in ["romantic", "honeymoon", "couples", "anniversary", "romance", "intimate"])
    is_family = any(w in p_lower for w in ["family", "kids", "children", "child", "toddler", "family-friendly"])
    is_culinary = any(w in p_lower for w in ["food", "culinary", "wine", "dining", "gourmet", "tasting", "bistro", "sommelier", "gastronomy", "foodie"])
    is_adventure = any(w in p_lower for w in ["adventure", "hiking", "outdoor", "nature", "trails", "mountains", "beach", "surf", "ski", "kayak"])
    is_luxury_req = any(w in p_lower for w in ["luxury", "vip", "michelin", "five star", "5 star", "first class", "penthouse", "exclusive"])

    is_tier_cheap = "cheap" in tier_clean or "budget" in tier_clean or index == 0
    is_tier_lux = "lux" in tier_clean or index == 2

    if is_romantic:
        if is_tier_cheap:
            act_snippet = f" & {act1}" if act1 else " & Intimate Sunset Walks"
            return format_proper_title(f"Romantic Saver: Cozy {dest} Cafes{act_snippet}")
        elif is_tier_lux:
            act_snippet = f" at {act1}" if act1 else ""
            return format_proper_title(f"Signature Romance: VIP {dest} Champagne & Michelin Dining{act_snippet}")
        else:
            act_snippet = f" & {act1}" if act1 else " & Historic Promenade"
            return format_proper_title(f"Romantic Getaway: Scenic {dest} Sunset{act_snippet}")

    if is_family:
        if is_tier_cheap:
            act_snippet = f": {act1}" if act1 else " Parks & Iconic Sights"
            return format_proper_title(f"Family Budget Saver: Essential {dest}{act_snippet}")
        elif is_tier_lux:
            act_snippet = f" & Private {act1}" if act1 else " & Private Guided Discovery"
            return format_proper_title(f"Signature Family VIP: Luxury {dest} Suite{act_snippet}")
        else:
            act_snippet = f" & {act1}" if act1 else " & Interactive Landmarks"
            return format_proper_title(f"Classic Family Explorer: {dest} Highlights{act_snippet}")

    if is_culinary:
        if is_tier_cheap:
            return format_proper_title(f"Foodie Saver: Essential {dest} Street Food & Local Bistros")
        elif is_tier_lux:
            act_snippet = f" & {act1}" if act1 else ""
            return format_proper_title(f"Signature Gastronomy: Sommelier Wine Tour & Fine Dining in {dest}{act_snippet}")
        else:
            act_snippet = f" & {act1}" if act1 else " & Food Market Tour"
            return format_proper_title(f"Gourmet Journey: Classic {dest} Culinary Walk{act_snippet}")

    if is_adventure:
        if is_tier_cheap:
            act_snippet = f": {act1}" if act1 else " Trails & Lakes"
            return format_proper_title(f"Adventure Saver: Essential {dest}{act_snippet}")
        elif is_tier_lux:
            act_snippet = f" & {act1}" if act1 else ""
            return format_proper_title(f"Signature Luxury: Exclusive {dest} Mountain Panorama & Spa{act_snippet}")
        else:
            act_snippet = f" & {act1}" if act1 else " & Nature Trails"
            return format_proper_title(f"Scenic Explorer: {dest} Outdoor Highlights{act_snippet}")

    if is_tier_cheap:
        if act1 and act2:
            return format_proper_title(f"Budget Saver: Essential {dest} ({act1} & {act2})")
        elif act1:
            return format_proper_title(f"Budget Saver: Essential {dest} & {act1}")
        else:
            return format_proper_title(f"Budget Saver: Essential {dest} City Highlights")
    elif is_tier_lux or is_luxury_req:
        if act1:
            return format_proper_title(f"Signature Luxury: VIP {dest} Experience & Private {act1}")
        else:
            return format_proper_title(f"Signature Luxury: Exclusive {dest} VIP Experience & Fine Dining")
    else:
        if act1 and act2:
            return format_proper_title(f"Balanced Choice: {dest} Highlights ({act1} & {act2})")
        elif act1:
            return format_proper_title(f"Balanced Choice: Classic {dest} Culture & {act1}")
        else:
            return format_proper_title(f"Balanced Choice: Classic {dest} Culture & Sightseeing")


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
) -> list[dict[str, Any]]:
    """Builds top 3 bundles: Shortest/Scenic/Longest for road trips, Cheapest/Moderate/Luxury for flights."""
    hotel_total = 0.0 if is_hotel_tbd else (hotel_cost_per_night * max(1, duration_days - 1))
    flight_total = flight_cost * passengers_count if not is_road_trip else 0.0
    car_total = 0.0 if is_car_tbd else car_cost_total

    if is_road_trip:
        tiers = [
            ("shortest", "Shortest Route", 0.85, "Direct highway route with fastest travel time and express corridor waypoints."),
            ("scenic", "Scenic Route", 1.0, "Scenic byways, national/state parks, mountain lookouts, and panoramic viewpoints."),
            ("longest", "Longest Route", 1.25, "Comprehensive regional explorer covering historic towns and extended waypoints."),
        ]
    elif is_cruise:
        tiers = [
            ("interior_oceanview", "Value Cruise", 0.85, "Oceanview stateroom, full dining, and curated harbor walking tours."),
            ("balcony_veranda", "Balcony Cruise", 1.0, "Private balcony stateroom, shore excursion credits, and specialty dining."),
            ("suite_concierge", "Luxury Suite Cruise", 1.4, "Penthouse suite, concierge service, VIP shore tours, and premium beverage package."),
        ]
    else:
        tiers = [
            ("cheapest", "Budget Saver", 0.80, "Best value airfare, cozy 3-star hotel nearby attractions, and essential highlights."),
            ("moderate", "Balanced Choice", 1.0, "Premium direct flights, top-rated 4-star hotel, rental car, and prime activities."),
            ("luxury", "Signature Luxury VIP", 1.5, "First class / business flights, 5-star luxury resort suite, SUV rental, and VIP tours."),
        ]

    bundles = []
    for idx, (tier_id, tier_label, mult, tier_desc) in enumerate(tiers):
        t_flight = round(flight_total * (mult if not is_road_trip else 1.0), 2)
        t_hotel = round(hotel_total * mult, 2)
        t_car = round(car_total * (1.1 if idx == 2 else (0.9 if idx == 0 else 1.0)), 2)
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

        bundles.append({
            "bundle_id": f"bundle_{tier_id}",
            "tier": tier_id,
            "package_name": p_name,
            "name": p_name,
            "description": tier_desc,
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
        })

    return bundles
