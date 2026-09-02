"""
Contextual Bundle Title Generator.
Generates dynamic, theme-aware bundle package titles based on destination,
origin, route characteristics, intent keywords, and real itinerary highlights.
"""

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
    Dynamically generates contextual package & bundle titles based on:
    - Road Trips: 'shortest' (Direct Highway), 'scenic' (Byways & Panoramas), 'longest' (Extended Explorer)
    - Flight Vacations: 'budget' (Budget Saver), 'balanced' (Balanced Choice), 'luxury' (Signature Luxury VIP)
    - Real Generated Itinerary Activities & Intent Keywords.
    """
    dest = format_proper_title(destination)
    orig = format_proper_title(origin) if origin else ""
    p_lower = (prompt or "").lower()
    acts = activities or []

    act1 = ""
    act2 = ""
    skip_keywords = [
        "check-in", "hotel", "airport", "flight", "rest", "start road trip", "depart", "departure",
        "drive from", "drive to", "arrive in", "arrival in", "travel to", "heading to", "rental", "pickup", "dropoff"
    ]
    for a in acts:
        a_clean = str(a).strip()
        a_lower = a_clean.lower()
        if not a_clean or any(w in a_lower for w in skip_keywords):
            continue
        if not act1:
            act1 = a_clean
        elif not act2 and a_clean != act1:
            act2 = a_clean
            break

    tier_clean = tier.lower()
    is_tier_cheap = "cheap" in tier_clean or "budget" in tier_clean or index == 0
    is_tier_lux = "lux" in tier_clean or index == 2
    user_wants_scenic = any(w in p_lower for w in ["scenic", "nature", "byway", "panoramic", "view", "views", "mountains", "trail", "trails"])

    # 1. Road Trip Bundle Titles (Budget, Balanced, Luxury)
    if is_road_trip or tier_clean in ["shortest", "scenic", "longest", "budget", "balanced", "luxury"]:
        route_header = f"{orig} to {dest}" if orig and orig.lower() != dest.lower() else dest
        if is_tier_cheap:
            prefix = "Budget Scenic Route" if user_wants_scenic else "Budget Saver"
            act_snippet = f" & {act1}" if act1 else ""
            return format_proper_title(f"{prefix}: {route_header} Road Trip{act_snippet}")
        elif is_tier_lux:
            prefix = "Signature Luxury Scenic VIP" if user_wants_scenic else "Signature Luxury VIP"
            act_snippet = f" & VIP {act1}" if act1 else ""
            return format_proper_title(f"{prefix}: {route_header} Premier Road Trip{act_snippet}")
        else:
            prefix = "Balanced Scenic Choice" if user_wants_scenic else "Balanced Choice"
            act_snippet = f" & {act1}" if act1 else ""
            return format_proper_title(f"{prefix}: {route_header} Road Trip{act_snippet}")

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
